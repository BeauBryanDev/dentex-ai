
from __future__ import annotations

import logging

from fastapi import ( APIRouter,
                     File, 
                     Form, 
                     HTTPException,
                     Request,
                     UploadFile, 
                     status )

from app.core.config import settings
from app.core.exception import ModelNotLoadedError
from app.core.session_store import MAX_ANALYSES_PER_SESSION
from app.schemas.analysis import AnalyzeResponse
from app.services.analysis_service import analyze_image

logger = logging.getLogger(__name__)

router = APIRouter(tags=["analysis"])
# POST /analyze — upload an X-ray, get the tooth chart and findings.

@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(
    request: Request,
    file: UploadFile = File(...),
    session_id: str | None = Form(default=None),
) -> AnalyzeResponse:
    """
    Run both detectors over one X-ray and fuse the results.

    Declared def, not async def, on purpose. Inference is CPU-bound and takes ~350-470 ms
    for the two models; in an async def it would run on the event loop and block every other
    request for that whole time. A sync endpoint is handed to FastAPI's threadpool instead, so
    the loop stays responsive. onnxruntime releases the GIL during run.
    """
    state = request.app.state
    lesion_session = getattr(state, "lesion_session", None)
    fdi_session = getattr(state, "fdi_session", None)
    
    if lesion_session is None or fdi_session is None:
        # Only reachable if lifespan failed.
        raise ModelNotLoadedError("lesion_session or fdi_session missing from app.state")

    # Bounded read: await file.read() with no limit would buffer whatever was sent.
    data = file.file.read(settings.max_upload_bytes + 1)
    
    if len(data) > settings.max_upload_bytes:
        
        raise HTTPException(
            
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"file exceeds {settings.max_upload_bytes // (1024 * 1024)} MB",
        )
        
    if not data:
        
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "empty upload")

    # ImageDecodeError propagates to the DentaVisionError handler in main.py, which returns
    # 415. Content-Type is not trustworthy — decodability is the real test.
    result = analyze_image(data, 
                           lesion_session, 
                           fdi_session, 
                           settings
                           )

    # Put the findings against a session so POST /chat can pick them up. Passing an
    # existing session_id uploads a new X-ray into the running conversation.
    response = AnalyzeResponse.from_result(result, session_id="")
    store = request.app.state.sessions

    session, started_new = store.attach_analysis(
        session_id,
        response.model_dump(exclude={"session_id"}),
    )

    if started_new and session_id:
        logger.info(
            "session %s is full (%s X-rays); started %s for this upload",
            session_id,
            MAX_ANALYSES_PER_SESSION,
            session.session_id,
        )

    return response.model_copy(update={"session_id": session.session_id})
