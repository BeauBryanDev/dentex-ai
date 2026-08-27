import json
from contextlib import asynccontextmanager

import anthropic
import faiss
import onnxruntime as ort
from fastapi import FastAPI
from sentence_transformers import SentenceTransformer

from app.core.budget import BudgetGuard
from app.core.config import settings
from app.core.session_store import SessionStore
from rag.retrieve import Retriever


@asynccontextmanager
async def lifespan(app: FastAPI):

    app.state.lesion_session = ort.InferenceSession(
        str(settings.lesion_model_path), providers=["CPUExecutionProvider"]
    )
    app.state.fdi_session = ort.InferenceSession(
        str(settings.fdi_model_path), providers=["CPUExecutionProvider"]
    )

    app.state.faiss_index = faiss.read_index(str(settings.faiss_index_path))
    app.state.embedding_model = SentenceTransformer(settings.embedding_model_name)
    app.state.chunk_metadata = json.loads(settings.faiss_metadata_path.read_text())

    # The retriever from rag/retrieve.py, handed the artifacts already loaded above rather
    # than loading its own — its default constructor would pull PubMedBERT off disk again.
    app.state.retriever = Retriever(
        index=app.state.faiss_index,
        meta=app.state.chunk_metadata,
        model=app.state.embedding_model,
    )

    # One client, one connection pool, one retry policy. The SDK already retries connection
    # errors, 408/409/429 and 500xxx twice — see core/exception.py before adding another layer.
    app.state.anthropic_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    # Bridges POST /analyze and POST /chat, which are separate requests. See
    # core/session_store.py for why this being an in-process dict pins us to one worker.
    app.state.sessions = SessionStore()

    # Process-wide spend ceiling. Deliberately not persisted: it bounds one run of the
    # server, and clearing it is a deliberate restart rather than an automatic reset.
    app.state.budget = BudgetGuard(
        
        session_token_budget=settings.session_token_budget,
        process_token_budget=settings.process_token_budget,
        max_turns_per_session=settings.max_turns_per_session,
    )

    yield

    app.state.lesion_session = None
    app.state.fdi_session = None
    app.state.faiss_index = None
    app.state.embedding_model = None
    app.state.retriever = None
    app.state.anthropic_client = None
