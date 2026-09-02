"""HTTP surface, with app.state fully faked."""
from __future__ import annotations

import anthropic
import httpx
import numpy as np

from app.core.session_store import SessionStore
from tests.unit.conftest import (
    TOOTH_ID_BY_FDI,
    FakeAnthropicClient,
    FakeOnnxSession,
    fake_response,
    png_bytes,
    text_block,
    yolo_output,
)


def xray_upload():
    image = png_bytes(np.full((640, 640, 3), 90, dtype=np.uint8))
    return {"file": ("xray.png", image, "image/png")}


def test_health_reports_which_component_is_missing(app_client):
    with app_client(faiss_index=None) as client:
        body = client.get("/health").json()
    assert body["status"] == "degraded"
    assert body["faiss_index"] is False
    assert body["lesion_model"] is True


def test_analyze_returns_findings_and_stores_them_on_the_session(app_client):
    fdi_out = yolo_output([(300, 300, 100, 200, TOOTH_ID_BY_FDI[26], 0.9)], 35)
    lesion_out = yolo_output([(300, 300, 20, 20, 0, 0.6)], 4)
    store = SessionStore()
    with app_client(
        lesion_session=FakeOnnxSession(lesion_out),
        fdi_session=FakeOnnxSession(fdi_out),
        sessions=store,
    ) as client:
        body = client.post("/analyze", files=xray_upload()).json()

    assert body["findings"][0]["tooth_fdi"] == 26
    assert body["teeth"][0]["confidence"] <= 1.0
    stored = store.get(body["session_id"]).analysis
    assert "session_id" not in stored
    assert stored["findings"][0]["tooth_fdi"] == 26


def test_undecodable_bytes_become_a_415_through_the_global_handler(app_client):
    with app_client() as client:
        response = client.post("/analyze", files={"file": ("x.png", b"nope", "image/png")})
    assert response.status_code == 415
    assert response.json() == {"detail": "could not decode image", "retryable": False}


def test_chat_starts_a_new_session_for_an_unknown_id(app_client):
    agent = FakeAnthropicClient([fake_response([text_block("Upload an X-ray first.")])])
    with app_client(anthropic_client=agent) as client:
        body = client.post(
            "/chat", json={"message": "what do you see", "session_id": "expired-id"}
        ).json()
    assert body["session_id"] != "expired-id"
    assert body["grounded_in_analysis"] is False
    assert body["reply"] == "Upload an X-ray first."


def test_chat_passes_upstream_backoff_through_as_retry_after(app_client):
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    error = anthropic.RateLimitError(
        "slow down",
        response=httpx.Response(429, headers={"retry-after": "9"}, request=request),
        body=None,
    )
    with app_client(anthropic_client=FakeAnthropicClient([error])) as client:
        response = client.post("/chat", json={"message": "hello"})
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "9"
    assert response.json()["retryable"] is True


