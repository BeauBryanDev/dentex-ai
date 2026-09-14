
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from app.agent.prompts import NEW_XRAY_NOTICE
from app.core.budget import Spend
"""In-process session state, bridging the two HTTP requests that make up one consultation."""
DEFAULT_TTL_SECONDS = 60 * 60  # an hour of inactivity ends a consultation
DEFAULT_MAX_SESSIONS = 200    # hard ceiling so a loop of new IDs cannot exhaust RAM
# X-rays one consultation may cover. Two is the demo case ...
MAX_ANALYSES_PER_SESSION = 2


@dataclass
class ChatSession:
    """One consultation: the analysis it is about, plus the conversation so far."""

    session_id: str
    created_at: float
    last_seen: float
    # AnalyzeResponse as a plain dict. None until an X-ray is uploaded — which is the
    # signal that selects the no-analysis system prompt.
    analysis: dict[str, Any] | None = None
    # Anthropic message params, in wire order. The Messages API is stateless, so this is
    # the entire memory of the conversation.
    messages: list[dict[str, Any]] = field(default_factory=list)
    # Held for the whole of one agent turn. The store's own lock protects the *map*; this
    # protects one conversation's history, which the orchestrator appends to across several
    # round-trips (user turn, assistant turn, tool results, assistant turn). 
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)
    # Tokens and turns spent by this conversation, enforced against the per-session
    # ceilings in core/budget.py.
    spend: Spend = field(default_factory=Spend)
    # How many X-rays this consultation has covered, capped at MAX_ANALYSES_PER_SESSION.
    analysis_count: int = 0

    @property
    def has_analysis(self) -> bool:
        return self.analysis is not None


class SessionStore:
    """Thread-safe TTL map of session_id -> ChatSession.

    The lock is not optional: the analyze and chat routes are declared `def`, so FastAPI
    runs them in its threadpool and two requests genuinely execute at once. An unguarded
    dict mutated from several threads can drop a message or evict a live session mid-read.
    """

    def __init__(
        self,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        max_sessions: int = DEFAULT_MAX_SESSIONS,
    ) -> None:
        self._sessions: dict[str, ChatSession] = {}
        self._lock = threading.Lock()
        self.ttl_seconds = ttl_seconds
        self.max_sessions = max_sessions


    def _purge_expired(self, now: float) -> None:
        stale = [
            sid for sid, s in self._sessions.items() if now - s.last_seen > self.ttl_seconds
        ]
        for sid in stale:
            del self._sessions[sid]

    def _enforce_ceiling(self) -> None:
        # Evict least-recently-seen first: the session someone is actively using is the
        # last one that should be dropped.
        while len(self._sessions) > self.max_sessions:
            
            oldest = min(self._sessions.values(), key=lambda s: s.last_seen)
            
            del self._sessions[oldest.session_id]

    #  public API 

    def create(self) -> ChatSession:
        """Create a new session, and return it."""
        now = time.time()
        session = ChatSession(session_id=str(uuid.uuid4()), 
                              created_at=now, 
                              last_seen=now)
        
        with self._lock:
            self._purge_expired(now)
            self._sessions[session.session_id] = session
            self._enforce_ceiling()
            
        return session

    def get(self, session_id: str | None) -> ChatSession | None:
        """Fetch and refresh a session. Returns None for unknown or expired ids."""
        if not session_id:
            return None
        
        now = time.time()
        
        with self._lock:
            
            self._purge_expired(now)
            
            session = self._sessions.get(session_id)
            
            if session is not None:
                session.last_seen = now
                
            return session

    def get_or_create(self, 
                      session_id: str | None = None
                      ) -> ChatSession:
        """Resolve a session id, minting a new one if it is missing or has expired.
        """
        return self.get(session_id) or self.create()

    def set_analysis(self, 
                     session_id: str, 
                     analysis: dict[str, Any]
                     ) -> None:
        """Attach (or replace) the analysis for a session, and nothing else.
        """
        with self._lock:
            
            session = self._sessions.get(session_id)
            
            if session is not None:
                session.analysis = analysis
                session.last_seen = time.time()


    def attach_analysis(
        self,
        session_id: str | None,
        analysis: dict[str, Any],
    ) -> tuple[ChatSession, bool]:
        """
        Point a consultation at a freshly analysed X-ray. Returns (session, started_new).

        This is the whole of the multi-image policy, in one place + two halves
        only make sense together.
        """
        session = self.get(session_id)

        started_new = session is None or session.analysis_count >= MAX_ANALYSES_PER_SESSION

        if started_new:
            session = self.create()

        with self._lock:
            # Re-read under the lock: get()/create() released it, and a concurrent upload
            # on the same id could have moved the count in between.
            live = self._sessions.get(session.session_id)

            if live is None:  # evicted between create() and here; vanishingly rare
                return session, started_new

            if live.analysis is not None:
                live.messages.append({"role": "user", "content": NEW_XRAY_NOTICE})

            live.analysis = analysis
            live.analysis_count += 1
            live.last_seen = time.time()

            return live, started_new

    def append_message(self, 
                       session_id: str, 
                       message: dict[str, Any]
                       ) -> None:
        
        with self._lock:
            
            session = self._sessions.get(session_id)
            
            if session is not None:
                
                session.messages.append(message)
                session.last_seen = time.time()


    def reset_messages(self, 
                       session_id: str
                       ) -> None:
        """Clear the conversation but keep the analysis — 'start over on this X-ray'."""
        with self._lock:
            
            session = self._sessions.get(session_id)
            
            if session is not None:
                
                session.messages.clear()
                session.last_seen = time.time()

    def delete(self, 
               session_id: str
               ) -> None:
        
        with self._lock:
            
            self._sessions.pop(session_id, None)


    def __len__(self) -> int:
        
        with self._lock:
            return len(self._sessions)
