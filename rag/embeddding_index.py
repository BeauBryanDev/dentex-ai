"""Phase 4 + 5 — embeddings and FAISS ingestion (Dentex_RAG.md §9, §10).

Embedding model: NeuML/pubmedbert-base-embeddings, chosen for biomedical/dental
domain fit (§1). Embeddings are L2-normalized so that IndexFlatIP's inner product
IS cosine similarity -- without normalization the scores are meaningless.

FAISS stores vectors and IDs, nothing else. The chunk text and all §8 metadata
live in a sidecar JSON keyed by the same integer ID used in IndexIDMap. That
pairing is the core architectural difference from the DB-backed RAGs in this
portfolio (§10) and is treated as a first-class artifact, not an afterthought:
at query time FAISS returns (id, score) and the caller resolves everything else
through the sidecar.

Integer IDs are the position in a stable, explicitly ordered chunk_id list --
never insertion order taken on faith (§10).
"""
import json
import os

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer

MODEL = "NeuML/pubmedbert-base-embeddings"
CHUNKS = "/home/beaunix/Downloads/Dentex/rag/out/phase3_chunks.json"
OUT = "/home/beaunix/Downloads/Dentex/rag/out"
INDEX_PATH = os.path.join(OUT, "dentex.faiss")
SIDECAR_PATH = os.path.join(OUT, "chunk_metadata.json")

SCHEMA_FIELDS = ["text", "chunk_id", "document_title", "source_file",
                 "epistemic_status", "section", "page_start", "page_end",
                 "chunk_type"]


def main():
    chunks = json.load(open(CHUNKS))
    # Stable, explicit ordering: sorted by chunk_id, so integer IDs are
    # reproducible across rebuilds rather than dependent on load order.
    chunks.sort(key=lambda c: c["chunk_id"])
    print(f"chunks: {len(chunks)}")

    # --- Phase 4: token verification against the model's own tokenizer (§9) ---
    tok = AutoTokenizer.from_pretrained(MODEL)
    counts = [len(tok(c["text"], add_special_tokens=True)["input_ids"])
              for c in chunks]
    over = sum(1 for t in counts if t > 512)
    print(f"tokens: max {max(counts)}  mean {sum(counts) / len(counts):.0f}  "
          f"over-512 {over}")
    if over:
        raise SystemExit(f"ABORT: {over} chunks exceed PubMedBERT's 512-token "
                         f"window and would be silently truncated.")

    # --- Phase 4: embeddings ---
    model = SentenceTransformer(MODEL)
    dim = model.get_sentence_embedding_dimension()
    print(f"model loaded: dim={dim}")
    vectors = model.encode([c["text"] for c in chunks],
                           batch_size=16, convert_to_numpy=True,
                           normalize_embeddings=True,   # required for IndexFlatIP
                           show_progress_bar=False)
    vectors = np.asarray(vectors, dtype="float32")
    norms = np.linalg.norm(vectors, axis=1)
    print(f"vectors: {vectors.shape}  norm min {norms.min():.4f} "
          f"max {norms.max():.4f}  (must be ~1.0 for cosine)")
    assert np.allclose(norms, 1.0, atol=1e-3), "embeddings are not normalized"

    # --- Phase 5: FAISS ingestion ---
    index = faiss.IndexIDMap(faiss.IndexFlatIP(dim))
    ids = np.arange(len(chunks), dtype="int64")
    index.add_with_ids(vectors, ids)
    faiss.write_index(index, INDEX_PATH)

    sidecar = {}
    for i, chunk, n_tokens in zip(ids.tolist(), chunks, counts):
        record = {f: chunk[f] for f in SCHEMA_FIELDS}
        record["token_count"] = n_tokens
        sidecar[str(i)] = record
    with open(SIDECAR_PATH, "w") as f:
        json.dump(sidecar, f, indent=1)

    # --- reconciliation (§10): index == sidecar == chunks ---
    reloaded = faiss.read_index(INDEX_PATH)
    print(f"\nindex.ntotal      : {reloaded.ntotal}")
    print(f"sidecar entries   : {len(sidecar)}")
    print(f"phase 3 chunks    : {len(chunks)}")
    ok = reloaded.ntotal == len(sidecar) == len(chunks)
    print(f"reconciled        : {'OK' if ok else 'MISMATCH'}")
    missing = [k for k, v in sidecar.items()
               if any(f not in v for f in SCHEMA_FIELDS)]
    print(f"schema complete   : {not missing}")
    print(f"\nwrote {INDEX_PATH} ({os.path.getsize(INDEX_PATH) / 1e6:.1f} MB)")
    print(f"wrote {SIDECAR_PATH} ({os.path.getsize(SIDECAR_PATH) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
