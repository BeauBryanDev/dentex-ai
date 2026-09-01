"""Phase 6 — test retrieval / validation (Dentex_RAG.md §11).

Runs each §11 query through BOTH retrieval paths so the effect of the
per-epistemic_status allocation is visible rather than asserted:

  global      plain top-k over the whole index
  per-status  top-n per epistemic_status, merged by score (rag/retrieve.py)

Query 5 is the watermark leakage probe -- the most important check in this RAG,
since watermark text surfacing inside a Claude answer would read as a citation
error in a live demo.
"""
from retrieve import Retriever

WATERMARK = ["iTeh", "STANDARD PREVIEW", "standards.iteh.ai", "iso-3950-2009",
             "5458e3b35302"]

QUERIES = [
    ("what does tooth notation 18 mean in the FDI system",
     "ISO-3950-2009.pdf", "normative_standard"),
    ("how are caries treated and managed clinically",
     "Dental_Caries.pdf", "peer_reviewed_research"),
    ("professional policy position on promoting oral health",
     "FDI_Policy_Statements_Toolkit.pdf", "policy_position"),
    ("how is a class II amalgam cavity preparation performed",
     "Operative_Dentistry_Garg_3rd_ed.pdf", "educational_textbook"),
    ("dental standard documentation", None, None),
]


def rank_of(hits, source_file):
    for rank, hit in enumerate(hits, 1):
        if hit["source_file"] == source_file:
            return rank
    return None


def main():
    r = Retriever()
    print(f"index: {r.index.ntotal} vectors | sidecar: {len(r.meta)} records")
    passes = 0

    for n, (query, want_file, want_status) in enumerate(QUERIES, 1):
        glob = r.search_global(query, k=5)
        per = r.search(query, per_status=2, total=8)
        print("\n" + "=" * 78)
        print(f"QUERY {n}: {query!r}")
        if want_file:
            print(f"expected: {want_file}  ({want_status})")
        print("=" * 78)

        g_rank = rank_of(glob, want_file) if want_file else None
        print(f"-- global top-5 --   expected at rank: {g_rank or 'NOT IN TOP 5'}")
        for i, h in enumerate(glob, 1):
            print(f"   {i}. {h['score']:.3f} [{h['epistemic_status'][:20]:20}] "
                  f"{h['source_file'][:30]:30} {h['section'][:34]}")

        p_rank = rank_of(per, want_file) if want_file else None
        print(f"-- per-status (2 each, 8 total) --   expected at rank: "
              f"{p_rank or 'NOT PRESENT'}")
        for i, h in enumerate(per, 1):
            mark = "  <==" if want_file and h["source_file"] == want_file else ""
            print(f"   {i}. {h['score']:.3f} [{h['epistemic_status'][:20]:20}] "
                  f"{h['source_file'][:30]:30} {h['section'][:34]}{mark}")

        if want_file:
            ok = p_rank is not None
            passes += ok
            print(f"   RESULT: {'PASS' if ok else 'FAIL'}"
                  f"  (global {g_rank or 'miss'} -> per-status {p_rank or 'miss'})")
        else:
            leaked = [(h["chunk_id"], w) for h in per
                      for w in WATERMARK if w in h["text"]]
            passes += not leaked
            print(f"   RESULT: {'PASS - no watermark' if not leaked else f'FAIL {leaked}'}")

    print("\n" + "=" * 78)
    print(f"§11 VALIDATION: {passes}/{len(QUERIES)} passed")


if __name__ == "__main__":
    main()
