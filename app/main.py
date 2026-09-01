import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.exception import AgentRateLimitError, DentaVisionError
from app.core.lifespan import lifespan
from app.core.logging import configure_logging
from app.routers import analysis, chat, health

configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="DentaVision API",
    description="Dental X-ray analysis: lesion + FDI tooth detection, fused and explained.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(DentaVisionError)
async def dentavision_error_handler(request: Request, 
                                    exc: DentaVisionError
                                    ) -> JSONResponse:
    """
    One place where our errors become HTTP responses.

    """
    log = logger.warning if exc.status_code < 500 else logger.error
    log(
        "%s -> %s | %s%s",
        type(exc).__name__,
        exc.status_code,
        exc.detail,
        f" | anthropic request_id={exc.request_id}" if exc.request_id else "",
    )

    headers = {}
    if isinstance(exc, AgentRateLimitError) and exc.retry_after is not None:
        # Pass the upstream backoff through so the frontend can wait the right amount
        # instead of guessing.
        headers["Retry-After"] = str(exc.retry_after)

    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.client_message, 
                 "retryable": exc.retryable},
        headers=headers,
    )


# Endpoints
app.include_router(health.router)
app.include_router(analysis.router)
app.include_router(chat.router)
