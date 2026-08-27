"""Application exceptions, and the translation layer for Anthropic SDK failures.
"""
from __future__ import annotations

from typing import Any

try:
    import anthropic
    
except ImportError:  # pragma: no cover - until `pip install -r requirements.txt` is run
    anthropic = None  # type: ignore[assignment]


class DentaVisionError(Exception):
    """Base for every error this application raises deliberately.

    `client_message` is what the user sees; `str(exc)` stays free to carry detail meant
    only for the log.
    """

    status_code: int = 500
    client_message: str = "internal server error"
    retryable: bool = False

    def __init__(self, detail: str = "", *, request_id: str | None = None) -> None:
        super().__init__(detail or self.client_message)
        self.detail = detail or self.client_message
        self.request_id = request_id


class ImageDecodeError(DentaVisionError):
    """Uploaded bytes are not a decodable image. Content-Type is not evidence — this is."""

    status_code = 415
    client_message = "could not decode image"


class ModelNotLoadedError(DentaVisionError):
    """app.state is missing an ONNX session or the FAISS index — lifespan failed."""

    status_code = 503
    client_message = "models are not loaded — check startup logs and GET /health"


#  Agent / Anthropic - 

class AgentError(DentaVisionError):
    """Any failure of the Claude call. Subclasses carry the status the client should see."""

    status_code = 502
    client_message = "the assistant is temporarily unavailable"


class AgentConfigurationError(AgentError):
    """Bad or missing API key, or a key without access to the configured model.

    Deliberately surfaces as 503, not 401: the *client* is authenticated fine — it is this
    server's upstream credential that is wrong. Returning 401 would tell the frontend to
    re-authenticate the dentist, which fixes nothing.
    """

    status_code = 503
    client_message = "the assistant is not configured correctly"


class AgentRateLimitError(AgentError):
    """429 from Anthropic. `retry_after` comes from the response header when present."""

    status_code = 429
    client_message = "the assistant is busy — please retry shortly"
    retryable = True

    def __init__(
        self, detail: str = "", *, request_id: str | None = None, retry_after: int | None = None
    ) -> None:
        super().__init__(detail, request_id=request_id)
        self.retry_after = retry_after


class AgentOverloadedError(AgentError):
    """529 `overloaded_error`, or any 5xx. Anthropic-side capacity, not our bug."""

    status_code = 503
    client_message = "the assistant is temporarily overloaded — please retry"
    retryable = True


class AgentTimeoutError(AgentError):
    """The request exceeded the client timeout. Long RAG-grounded answers can be slow."""

    status_code = 504
    client_message = "the assistant took too long to respond"
    retryable = True


class AgentConnectionError(AgentError):
    """Network failure before any response — DNS, TLS, no route."""

    status_code = 502
    client_message = "could not reach the assistant"
    retryable = True


class AgentRequestError(AgentError):
    """400 from Anthropic: our request was malformed. A bug here, never the user's fault.

    Most likely causes in this app: a tool schema that does not validate, or a message
    history assembled in the wrong order by session_store.
    """

    status_code = 500
    client_message = "the assistant request was malformed"


class AgentRefusalError(AgentError):
    """`stop_reason == "refusal"` — a successful HTTP 200 with no usable content.

    Not an SDK exception: the API returns 200 and `content` is empty or partial, so code
    that reads `content[0]` breaks unless `stop_reason` is checked first. Raised by the
    orchestrator so the chat route has one thing to catch.
    """

    status_code = 422
    client_message = "the assistant declined to answer this request"

    def __init__(
        self, detail: str = "", *, request_id: str | None = None, category: str | None = None
    ) -> None:
        super().__init__(detail, request_id=request_id)
        self.category = category


class AgentBudgetError(AgentError):
    """A spend ceiling was reached. Not retryable — retrying is the thing being prevented."""

    status_code = 429
    client_message = (
        "this demo has reached its usage limit for now — start a new consultation, "
        "or restart the backend"
    )

def _request_id(exc: Any) -> str | None:
    return getattr(exc, "request_id", None)


def _retry_after(exc: Any) -> int | None:
    """Seconds to wait, from the `retry-after` header. Absent or unparseable -> None."""
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    
    if headers is None:
        return None
    try:
        return int(headers.get("retry-after"))
    except (TypeError, ValueError):
        return None


def translate_anthropic_error(exc: Exception) -> AgentError:
    """Map an SDK exception onto an `AgentError`. The only place `anthropic.*` is named.

    Ordered most-specific first, which is required rather than stylistic: `APITimeoutError`
    subclasses `APIConnectionError`, and every status error subclasses `APIStatusError`, so
    a broad clause placed early would swallow the specific ones and lose the retryability
    distinction the caller needs.

    Note the SDK already retries connection errors, 408/409/429 and 5xx twice on its own
    (`max_retries=2`). By the time an exception reaches here those retries are spent — do
    not add another retry loop around this without lowering `max_retries` first, or the
    effective attempt count multiplies.
    """
    if anthropic is None:
        # Without the package there can be no SDK exception, so nothing here is ours.
        # Re-raise rather than returning a generic AgentError — labelling an arbitrary
        # bug "the assistant is unavailable" hides it behind a plausible-looking 502.
        raise exc

    rid = _request_id(exc)

    if isinstance(exc, anthropic.APITimeoutError):
        return AgentTimeoutError(str(exc), request_id=rid)
    
    if isinstance(exc, anthropic.APIConnectionError):
        return AgentConnectionError(str(exc), request_id=rid)
    
    if isinstance(exc, anthropic.RateLimitError):
        return AgentRateLimitError(str(exc), request_id=rid, retry_after=_retry_after(exc))
    
    if isinstance(exc, (anthropic.AuthenticationError, anthropic.PermissionDeniedError)):
        return AgentConfigurationError(str(exc), request_id=rid)
    
    if isinstance(exc, anthropic.NotFoundError):
        # Almost always a bad `anthropic_model` in config, not a missing endpoint.
        return AgentConfigurationError(f"unknown model or endpoint: {exc}", request_id=rid)
    
    if isinstance(exc, (anthropic.BadRequestError, anthropic.UnprocessableEntityError)):
        return AgentRequestError(str(exc), request_id=rid)
    
    if isinstance(exc, anthropic.InternalServerError):
        return AgentOverloadedError(str(exc), request_id=rid)
    
    if isinstance(exc, anthropic.APIStatusError):
        # Anything else with a status. `overloaded_error` (529) arrives here on SDK
        # versions that do not map it to a dedicated class.
        if getattr(exc, "type", None) == "overloaded_error" or exc.status_code >= 500:
            return AgentOverloadedError(str(exc), request_id=rid)
        
        return AgentError(str(exc), request_id=rid)
    
    if isinstance(exc, anthropic.APIError):
        return AgentError(str(exc), request_id=rid)

    raise exc  # not ours — let it surface rather than mislabelling it
