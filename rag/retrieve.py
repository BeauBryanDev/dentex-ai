"""Retrieval for the DentaVision RAG — per-epistemic_status top-k.

Why not a single global top-k: the corpus is heavily lopsided (890 of 963 chunks
are the Garg textbook, 7 are the ISO standard). A global search lets the textbook
saturate every slot on any dental question, so "what does tooth notation 18 mean
in the FDI system" returned five textbook chunks and pushed the actual normative
standard to rank 6 -- despite ISO scoring only ~0.08 lower.

Allocating slots per epistemic_status fixes that and matches the design intent of
Dentex_RAG.md §7: a normative clause, a policy position, a research finding and a
textbook explanation are different KINDS of answer that Claude must frame
differently, so they should not compete for the same slots.

FAISS has no native metadata filter. With only 963 vectors an exact full search
is essentially free, so we search everything once and bucket the ranked results
by status -- no approximate filtering, no IDSelector plumbing.
"""
import json
from collections import defaultdict
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

MODEL = "NeuML/pubmedbert-base-embeddings"
# RAG_STORE/ is the single serving copy of the index, and what the backend reads through
# settings — so the CLI queries exactly what the app queries. (Previously this was an
# absolute path into ~/Downloads/Dentex/, which stopped existing when the project moved.)
# rag/out/ is now pipeline scratch output only: phase4 writes there, and you copy
# dentex.faiss + chunk_metadata.json across to RAG_STORE/ to publish a rebuilt index.
OUT = str(Path(__file__).resolve().parents[1] / "RAG_STORE")

# Ordered by authority for tie-breaking in presentation, not for scoring.
STATUS_ORDER = ["normative_standard", "peer_reviewed_research",
                "policy_position", "educational_textbook"]


class Retriever:
    def __init__(self, out_dir=OUT, *, index=None, meta=None, model=None):
        """Loads from `out_dir` by default; the backend injects instead.

        The CLI path below is unchanged. The keyword args exist so the FastAPI app can
        hand over the FAISS index, metadata and SentenceTransformer it already loaded once
        in core/lifespan.py -- constructing a SentenceTransformer here per request would
        reload PubMedBERT from disk on every question the dentist asks.
        """
        self.model = model if model is not None else SentenceTransformer(MODEL)
        self.index = index if index is not None else faiss.read_index(f"{out_dir}/dentex.faiss")
        self.meta = meta if meta is not None else json.load(
            open(f"{out_dir}/chunk_metadata.json")
        )

    def embed(self, query):
        return self.model.encode([query], convert_to_numpy=True,
                                 normalize_embeddings=True).astype("float32")

    def search_global(self, query, k=5):
        """Plain top-k, kept for comparison against the per-status path."""
        scores, ids = self.index.search(self.embed(query), k)
        return [self._hit(s, i) for s, i in zip(scores[0], ids[0]) if i != -1]

    def search(self, query, per_status=2, total=8):
        """Top-`per_status` chunks from each epistemic_status, merged by score.

        Every status that has any material at all is guaranteed representation;
        remaining slots up to `total` are filled by global score order, so a
        question genuinely about one document still gets depth on that document.
        """
        scores, ids = self.index.search(self.embed(query), self.index.ntotal)
        buckets, ranked = defaultdict(list), []
        for score, idx in zip(scores[0], ids[0]):
            if idx == -1:
                continue
            hit = self._hit(score, idx)
            ranked.append(hit)
            if len(buckets[hit["epistemic_status"]]) < per_status:
                buckets[hit["epistemic_status"]].append(hit)

        chosen = [h for status in STATUS_ORDER for h in buckets.get(status, [])]
        chosen_ids = {h["id"] for h in chosen}
        for hit in ranked:                      # backfill by global score
            if len(chosen) >= total:
                break
            if hit["id"] not in chosen_ids:
                chosen.append(hit)
                chosen_ids.add(hit["id"])
        return sorted(chosen, key=lambda h: -h["score"])[:total]

    def _hit(self, score, idx):
        rec = dict(self.meta[str(int(idx))])
        rec["id"] = int(idx)
        rec["score"] = float(score)
        return rec


if __name__ == "__main__":
    import sys
    r = Retriever()
    query = " ".join(sys.argv[1:]) or "what does tooth notation 18 mean in the FDI system"
    print(f"query: {query!r}\n")
    for h in r.search(query):
        print(f"  {h['score']:.3f}  [{h['epistemic_status']:22}] "
              f"{h['source_file'][:32]:32} p{h['page_start']}")
        print(f"      {h['section']}")
