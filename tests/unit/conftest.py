"""Offline fixtures. No Anthropic calls, no ONNX weights, no embedding model."""
from __future__ import annotations

import os

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test-0000000000")

from contextlib import asynccontextmanager
from types import SimpleNamespace

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.core.budget import BudgetGuard
from app.core.config import CLASS_MAP, Settings
from app.core.session_store import SessionStore
from app.utils.postprocessing import Detections

NUM_ANCHORS = 8400
TOOTH_ID_BY_FDI = {r["fdi"]: r["id"] for r in CLASS_MAP if r["type"] == "tooth"}


def yolo_output(specs: list[tuple], num_classes: int) -> np.ndarray:
    """Synthetic output0 of shape [1, 4 + nc, 8400] from (cx, cy, w, h, cls, score)."""
    out = np.zeros((1, 4 + num_classes, NUM_ANCHORS), dtype=np.float32)
    for anchor, (cx, cy, w, h, cls, score) in enumerate(specs):
        out[0, 0:4, anchor] = (cx, cy, w, h)
        out[0, 4 + cls, anchor] = score
    return out


class FakeOnnxSession:
    """Stands in for ort.InferenceSession. Records the tensor it was fed."""

    def __init__(self, output: np.ndarray) -> None:
        self.output = output
        self.last_tensor: np.ndarray | None = None

    def get_inputs(self):
        return [SimpleNamespace(name="images")]

    def run(self, _outputs, feed):
        self.last_tensor = feed["images"]
        return [self.output]


def make_detections(boxes, scores, class_ids, labels=None, raw_scores=None) -> Detections:
    """Hand-built Detections, bypassing decode."""
    boxes = np.asarray(boxes, dtype=np.float32).reshape(-1, 4)
    scores = np.asarray(scores, dtype=np.float32)
    class_ids = np.asarray(class_ids, dtype=np.int32)
    return Detections(
        boxes=boxes,
        scores=scores,
        class_ids=class_ids,
        labels=labels if labels is not None else [f"c{i}" for i in class_ids],
        raw_scores=None if raw_scores is None else np.asarray(raw_scores, dtype=np.float32),
    )


def text_block(text: str):
    return SimpleNamespace(type="text", text=text)


def tool_use_block(block_id: str, name: str, payload: dict):
    return SimpleNamespace(type="tool_use", id=block_id, name=name, input=payload)


def fake_response(content, stop_reason="end_turn", input_tokens=100, output_tokens=20):
    """One Messages API response, shaped like the SDK object the orchestrator reads."""
    return SimpleNamespace(
        content=content,
        stop_reason=stop_reason,
        model="fake-model",
        _request_id="req_test",
        usage=SimpleNamespace(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_input_tokens=0,
            cache_creation_input_tokens=0,
        ),
    )


class FakeMessages:
    def __init__(self, script) -> None:
        self.script = list(script)
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self.script:
            raise AssertionError("fake client called more times than scripted")
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class FakeAnthropicClient:
    def __init__(self, script=()) -> None:
        self.messages = FakeMessages(script)


class FakeRetriever:
    """Spy over rag.retrieve.Retriever. Never loads FAISS or PubMedBERT."""

    def __init__(self, hits=None) -> None:
        self.hits = hits if hits is not None else [sample_hit()]
        self.queries: list[str] = []

    def search(self, query, total=4):
        self.queries.append(query)
        return self.hits[:total]


def sample_hit(text="Proximal caries are managed by selective removal.", **overrides):
    hit = {
        "text": text,
        "source_file": "Operative_Dentistry_Garg_3rd_ed.pdf",
        "section": "Caries Management",
        "page_start": 120,
        "page_end": 121,
        "epistemic_status": "educational_textbook",
        "score": 0.712,
    }
    hit.update(overrides)
    return hit


def png_bytes(image: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".png", image)
    assert ok
    return buf.tobytes()


@pytest.fixture
def test_settings() -> Settings:
    """Settings with pinned thresholds so tuning .env cannot move the tests."""
    return Settings(
        anthropic_api_key="sk-ant-test-0000000000",
        confidence_threshold=0.2,
        iou_threshold=0.8,
        tooth_dedup_iou_threshold=0.7,
        lesion_containment_threshold=0.15,
        inference_imgsz=640,
        keep_full_tool_results=1,
    )


@pytest.fixture
def fake_retriever() -> FakeRetriever:
    return FakeRetriever()


@pytest.fixture
def session_store() -> SessionStore:
    return SessionStore()


@pytest.fixture
def budget() -> BudgetGuard:
    return BudgetGuard(
        session_token_budget=1000,
        process_token_budget=5000,
        max_turns_per_session=3,
    )


@pytest.fixture
def app_client(monkeypatch):
    """TestClient over the real app with app.state populated by fakes."""

    def build(**state):
        from app.main import app

        defaults = {
            "lesion_session": FakeOnnxSession(yolo_output([], 4)),
            "fdi_session": FakeOnnxSession(yolo_output([], 35)),
            "faiss_index": object(),
            "embedding_model": object(),
            "retriever": FakeRetriever(),
            "anthropic_client": FakeAnthropicClient(),
            "sessions": SessionStore(),
            "budget": BudgetGuard(200_000, 2_000_000, 25),
        }
        defaults.update(state)

        @asynccontextmanager
        async def fake_lifespan(_app):
            for key, value in defaults.items():
                setattr(_app.state, key, value)
            yield

        monkeypatch.setattr(app.router, "lifespan_context", fake_lifespan)
        return TestClient(app)

    return build
