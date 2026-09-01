
from __future__ import annotations

from fastapi import APIRouter, Request

from app.schemas.analysis import HealthResponse

router = APIRouter(tags=["health"])

# Check for Livneh's health.

@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    state = request.app.state
    parts = {
        "lesion_model": getattr(state, "lesion_session", None) is not None,
        "fdi_model": getattr(state, "fdi_session", None) is not None,
        "faiss_index": getattr(state, "faiss_index", None) is not None,
        "embedding_model": getattr(state, "embedding_model", None) is not None,
    }
    # Always 200: this reports component state, and a body saying which part is missing is
    # more useful to a developer than an opaque 503.
    return HealthResponse(status="ok" if all(parts.values()) else "degraded", **parts)
