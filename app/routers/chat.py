
from __future__ import annotations

from fastapi import APIRouter, Request

from app.agent.orchestrator import run_turn
from app.core.config import settings
from app.core.exception import ModelNotLoadedError
from app.schemas.chat import ChatRequest, ChatResponse

router = APIRouter(tags=["chat"])

# POST /chat — one conversational turn,
# with the agent in the analysis from a previous /analyze or /chat turn.

@router.post("/chat", response_model=ChatResponse)
def chat(request: Request, 
         payload: ChatRequest
         ) -> ChatResponse:
    """
    Run the agent for one turn.

    def , not async def, for the same reason as /analyze: the Claude call blocks for
    seconds — longer when it makes two retrievals — and on the event loop that would stall
    every other request for the duration. FastAPI hands sync endpoints to its threadpool.

    """
    state = request.app.state
    client = getattr(state, "anthropic_client", None)
    retriever = getattr(state, "retriever", None)
    sessions = getattr(state, "sessions", None)

    # The retriever is required, not optional. Without it the agent would still answer —
    # fluently, and from memory and I want o show RAG Researchers how to use it.
    if client is None or retriever is None or sessions is None:
        missing = [
            name
            for name, obj in (
                ("anthropic_client", client),
                ("retriever", retriever),
                ("sessions", sessions),
            )
            if obj is None
        ]
        raise ModelNotLoadedError(f"app.state missing: {', '.join(missing)}")

    # An unknown or expired id transparently starts a new session rather than erroring; the
    # reply will then ask for an upload, since the analysis went with it.
    session = sessions.get_or_create(payload.session_id)

    # Held across the whole turn so two requests on one session cannot interleave their
    # appends to the history. See ChatSession.lock.
    with session.lock:
        
        reply = run_turn(
            session,
            payload.message,
            client=client,
            retriever=retriever,
            settings=settings,
            budget=getattr(state, "budget", None),
        )

    return ChatResponse.from_reply(reply)
