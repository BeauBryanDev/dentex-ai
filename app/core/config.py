import json
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Single source of truth for the FDI model's class list: id :: anatomy. Derive the raw
# class-name list from it rather than restating it, so the two cannot drift after a retrain.
CLASS_MAP_PATH = PROJECT_ROOT / "app" / "utils" / "CLASS_MAP.json"
CLASS_MAP: list[dict] = json.loads(CLASS_MAP_PATH.read_text())


def _fdi_class_names() -> list[str]:
    """
    Raw ONNX output labels, ordered by class id  
    must match the training data.yaml exactly."""
    rows = sorted(CLASS_MAP, key=lambda r: r["id"])
    
    if [r["id"] for r in rows] != list(range(len(rows))):
        
        raise ValueError(f"{CLASS_MAP_PATH.name}: class ids must be contiguous from 0")
    
    return [
        f"T{r['fdi']}" if r["type"] == "tooth" else r["name"].capitalize()
        for r in rows
    ]


class Settings(BaseSettings):

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    project_root: Path = PROJECT_ROOT
    lesion_model_path: Path = project_root / "models" / "lesion_yolov8small.onnx"
    # FDI vision YOLOV8model path
    fdi_model_path: Path = project_root / "models" / "FDI_Teeth_model.onnx"
    
    # Lession vision model class names
    lesion_class_names: list[str] = ["Cavities", "Damage", "Infection", "Wisdom"]
    # FDI vision model class names — derived from CLASS_MAP.json, never edited by hand.
    fdi_class_names: list[str] = _fdi_class_names()
 
    inference_imgsz: int = 640
    confidence_threshold: float = 0.2
    iou_threshold: float = 0.8
    # Two different questions, so two different metrics — see fusion.py.
    # Dedup: "are these two boxes the same physical tooth?" -> symmetric IoU, high bar.
    tooth_dedup_iou_threshold: float = 0.7
    # NOT IoU: a small caries fully inside a molar scores ~0.07 IoU purely because of the
    # size gap, so the old fusion_iou_threshold=0.1 dropped genuine findings (measured: a
    # lesion 52% contained in T37 scored 0.090 IoU and was rejected).
    lesion_containment_threshold: float = 0.15
 
    faiss_index_path: Path = project_root / "RAG_STORE" / "dentex.faiss"
    faiss_metadata_path: Path = project_root / "RAG_STORE" / "chunk_metadata.json"
    embedding_model_name: str = "NeuML/pubmedbert-base-embeddings"
    rag_top_k: int = 4
 
    anthropic_api_key: str
    anthropic_model: str = "claude-sonnet-5"
    
    session_token_budget: int = 120_000     # ~one long consultation
    process_token_budget: int = 1_500_000   # backstop; resets only on restart
    max_turns_per_session: int = 25
    # Thinking depth. claude-sonnet-5 defaults to "high"; "medium" is ample for reading a
    # findings JSON and citing a corpus, and cuts thinking tokens — which are billed as
    # output at 5x the input rate.
    agent_effort: str = "medium"
    # Retrieval history: how many past tool_results keep their full text. Older ones are
    # stubbed, because a retrieval already consumed is resent verbatim on every later turn.
    keep_full_tool_results: int = 1

    # max_tokens caps thinking AND response text together, and claude-sonnet-5 runs
    # adaptive thinking by default (omitting the `thinking` param does not disable it).
    # At 1024 a grounded answer that reasons over the findings can spend the budget
    # thinking and get truncated mid-sentence with stop_reason="max_tokens".
    agent_max_tokens: int = 2048
 
    cors_allow_origins: list[str] = ["http://localhost:5173"]

    # Panoramic X-rays are large (the test set runs to ~2870px wide); 20 MB covers a 16-bit
    # PNG panoramic with room to spare while bounding what a single request can buffer.
    max_upload_bytes: int = 20 * 1024 * 1024
 
 
settings = Settings()
 
 
 