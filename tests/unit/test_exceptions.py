"""Translating SDK failures into the statuses the frontend acts on."""
from __future__ import annotations

import anthropic
import httpx
import pytest

from app.core.exception import (
    AgentRateLimitError,
    AgentTimeoutError,
    translate_anthropic_error,
)

REQUEST = httpx.Request("POST", "https://api.anthropic.com/v1/messages")


def response(status, headers=None):
    return httpx.Response(status, headers=headers or {}, request=REQUEST)


def test_timeout_is_matched_before_its_connection_error_parent():
    translated = translate_anthropic_error(anthropic.APITimeoutError(request=REQUEST))
    assert isinstance(translated, AgentTimeoutError)
    assert translated.status_code == 504
    assert translated.retryable is True


def test_rate_limit_carries_retry_after_from_the_header():
    exc = anthropic.RateLimitError(
        "slow down", response=response(429, {"retry-after": "7"}), body=None
    )
    translated = translate_anthropic_error(exc)
    assert isinstance(translated, AgentRateLimitError)
    assert translated.retry_after == 7


def test_an_error_that_is_not_ours_is_reraised_rather_than_relabelled():
    with pytest.raises(ValueError):
        translate_anthropic_error(ValueError("a bug in our own code"))
