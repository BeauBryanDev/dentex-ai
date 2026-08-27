
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from app.core.budget import Spend
"""In-process session state, bridging the two HTTP requests that make up one consultation."""
DEFAULT_TTL_SECONDS = 60 * 60          # an hour of inactivity ends a consultation
DEFAULT_MAX_SESSIONS = 200             # hard ceiling so a loop of new IDs cannot exhaust RAM


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
    # round-trips (user turn, assistant turn, tool results, assistant turn). Two /chat
    # requests racing on one session would otherwise interleave those appends and produce a
    # history the API rejects — tool_result blocks separated from their tool_use.
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)
    # Tokens and turns spent by this conversation, enforced against the per-session
    # ceilings in core/budget.py.
    spend: Spend = field(default_factory=Spend)

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
        session = ChatSession(session_id=str(uuid.uuid4()), created_at=now, last_seen=now)
        
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

    def get_or_create(self, session_id: str | None = None) -> ChatSession:
        """Resolve a session id, minting a new one if it is missing or has expired.

        An expired id quietly becomes a *new* session rather than an error: the frontend
        holds the id in memory and a dentist returning after lunch should get a working
        chat, not a failure. The cost is that the old analysis is gone — which is correct,
        since the whole point of the TTL is that it no longer exists.
        """
        return self.get(session_id) or self.create()

    def set_analysis(self, session_id: str, analysis: dict[str, Any]) -> None:
        """Attach (or replace) the analysis for a session.

        Replacement is intentional: uploading a second X-ray re-points the conversation at
        the new one. The message history is kept, so the dentist can say "and this one?"
        and Claude still has the thread — but every later turn is grounded in the new
        findings, never a mix of both.
        """
        with self._lock:
            
            session = self._sessions.get(session_id)
            
            if session is not None:
                session.analysis = analysis
                session.last_seen = time.time()

    def append_message(self, session_id: str, message: dict[str, Any]) -> None:
        
        with self._lock:
            
            session = self._sessions.get(session_id)
            
            if session is not None:
                
                session.messages.append(message)
                session.last_seen = time.time()

    def reset_messages(self, session_id: str) -> None:
        """Clear the conversation but keep the analysis — 'start over on this X-ray'."""
        with self._lock:
            
            session = self._sessions.get(session_id)
            
            if session is not None:
                
                session.messages.clear()
                session.last_seen = time.time()

    def delete(self, session_id: str) -> None:
        
        with self._lock:
            
            self._sessions.pop(session_id, None)

    def __len__(self) -> int:
        
        with self._lock:
            return len(self._sessions)
