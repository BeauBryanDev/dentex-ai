
from __future__ import annotations

import logging
import re
import sys
from typing import Any

LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
DATE_FORMAT = "%H:%M:%S"

# Anthropic key shape. Matched independently of the configured value so a key from the
# environment, a traceback, or a pasted curl is redacted too.
_KEY_PATTERN = re.compile(r"sk-ant-[A-Za-z0-9_\-]{8,}")
_REDACTED = "sk-ant-***REDACTED***"


class SecretRedactingFilter(logging.Filter):
    """
    Scrub API keys from log records — message, args, and exception text alike.

    Runs as a filter rather than a formatter so it applies to every handler, including any
    added later by uvicorn or a future file handler.
    """

    def __init__(self, extra_secrets: tuple[str, ...] = ()) -> None:
        super().__init__()
        # Only redact secrets long enough to be real; a short or empty value would match
        # everywhere and turn the logs into noise.
        self._secrets = tuple(s for s in extra_secrets if s and len(s) >= 8)

    def _scrub(self, value: Any) -> Any:
        #  The SDK logs full request/response bodies at DEBUG (ANTHROPIC_LOG=debug). Those
        #  bodies contain the X-ray-derived findings and the whole chat history, so keep it
        #  at INFO unless someone is actively debugging.
        if not isinstance(value, str):
            return value
        
        for secret in self._secrets:
            value = value.replace(secret, _REDACTED)
            
        return _KEY_PATTERN.sub(_REDACTED, value)

    def filter(self, record: logging.LogRecord) -> bool:
        
        record.msg = self._scrub(record.msg)
        
        if record.args:
            
            if isinstance(record.args, dict):
                record.args = {k: self._scrub(v) for k, v in record.args.items()}
                
            else:
                record.args = tuple(self._scrub(a) for a in record.args)
                
        return True  # a filter that redacts must never drop the record


def configure_logging(level: int | str = logging.INFO) -> None:
    """
    Install one handler, one format, and the redaction filter — including on uvicorn.

    Safe to call more than once (``--reload`` re-imports the app); handlers are replaced
    rather than appended, so lines are not duplicated on every reload.
    """
    try:
        from app.core.config import settings

        secrets = (settings.anthropic_api_key,)
    except Exception:  # noqa: BLE001 - logging must survive a broken/missing config
        secrets = ()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    handler.addFilter(SecretRedactingFilter(secrets))

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

    # uvicorn ships its own handlers; hand its loggers to ours so access lines and
    # application lines share a format, and so redaction covers them too.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uv = logging.getLogger(name)
        uv.handlers = []
        uv.propagate = True

    # The SDK logs full request/response bodies at DEBUG (ANTHROPIC_LOG=debug). Those
    # bodies contain the X-ray-derived findings and the whole chat history, so keep it at
    # INFO unless someone is actively debugging.
    logging.getLogger("anthropic").setLevel(logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def log_agent_usage(logger: logging.Logger, 
                    response: Any, *, 
                    model: str | None = None
                    ) -> None:
    """
    Log token usage and the provider request id for one Claude response.

    request_id is what Anthropic support needs to trace a failed or slow call, and it is
    otherwise thrown away. `cache_read_input_tokens` is the one number that tells you
    whether prompt caching is actually working — if it stays 0 across turns of the same
    conversation, something upstream is invalidating the cached prefix.
    """
    usage = getattr(response, "usage", None)
    if usage is None:
        return

    logger.info(
        "claude model=%s request_id=%s in=%s out=%s cache_read=%s cache_write=%s stop=%s",
        model or getattr(response, "model", "?"),
        getattr(response, "_request_id", None),
        getattr(usage, "input_tokens", 0),
        getattr(usage, "output_tokens", 0),
        getattr(usage, "cache_read_input_tokens", 0),
        getattr(usage, "cache_creation_input_tokens", 0),
        getattr(response, "stop_reason", None),
    )
