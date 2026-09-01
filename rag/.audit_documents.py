"""Phase 0 — per-document audit for the DentaVision RAG (see Dentex_RAG.md §4).

Measures structure empirically; writes nothing but a report. Extraction logic
(Phase 1) must be written against these findings, not against assumptions.
"""
import collections
import json
import os
import statistics
import sys

import pymupdf

DOCS = "/home/beaunix/Downloads/Dentex/Docs4RAG"
FILES = [
    "Dental_Caries.pdf",
    "ISO-3950-2009.pdf",
    "FDI_Policy_Statements_Toolkit.pdf",
    "Operative_Dentistry_Garg_3rd_ed.pdf",
]


def spans(page):
    """Yield (text, bbox, size, font, dir) for every span on the page."""
    d = page.get_text("dict")
    for block in d["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block["lines"]:
            for span in line["spans"]:
                yield (span["text"], span["bbox"], round(span["size"], 1),
                       span["font"], tuple(round(x, 3) for x in line["dir"]))


def column_heuristic(doc, sample_pages):
    """Two-column iff text-block left edges cluster into two bands and the
    page's horizontal midline is mostly free of block crossings."""
    lefts, crossings, total = [], 0, 0
    for pno in sample_pages:
        page = doc[pno]
        w = page.rect.width
        mid = w / 2
        for block in page.get_text("blocks"):
            x0, y0, x1, y1, text = block[0], block[1], block[2], block[3], block[4]
            if not text.strip() or (x1 - x0) < 20:
                continue
            lefts.append(x0 / w)
            total += 1
            if x0 < mid - 0.05 * w and x1 > mid + 0.05 * w:
                crossings += 1
    if not lefts:
        return "no text blocks", 0.0, []
    left_band = [v for v in lefts if v < 0.45]
    right_band = [v for v in lefts if 0.45 <= v < 0.9]
    cross_ratio = crossings / max(total, 1)
    right_ratio = len(right_band) / len(lefts)
    if right_ratio > 0.2 and cross_ratio < 0.35:
        verdict = "TWO-COLUMN"
    elif cross_ratio > 0.5:
        verdict = "single-column"
    else:
        verdict = "single-column (or irregular)"
    return verdict, cross_ratio, [round(statistics.median(b), 3)
                                  for b in (left_band, right_band) if b]


def audit(path):
    name = os.path.basename(path)
    doc = pymupdf.open(path)
    n = doc.page_count
    texts = [doc[i].get_text() for i in range(n)]
    total_chars = sum(len(t) for t in texts)
    empty = sum(1 for t in texts if len(t.strip()) < 20)

    # sample interior pages, avoiding front matter and back matter
    lo, hi = int(n * 0.25), int(n * 0.75)
    sample = list(range(lo, min(hi, lo + 12))) or list(range(min(n, 5)))
    verdict, cross_ratio, bands = column_heuristic(doc, sample)

    images = sum(len(doc[i].get_images(full=True)) for i in range(n))

    print(f"\n{'=' * 72}\n{name}\n{'=' * 72}")
    print(f"  page_count      : {n}")
    print(f"  file_size       : {os.path.getsize(path) / 1e6:.1f} MB")
    print(f"  total_chars     : {total_chars:,}")
    print(f"  chars_per_page  : {total_chars / n:,.0f}")
    print(f"  near-empty pages: {empty}  "
          f"({'SCANNED? investigate' if empty > n * 0.3 else 'ok — text layer present'})")
    print(f"  embedded images : {images}")
    print(f"  column layout   : {verdict}  (midline-crossing ratio {cross_ratio:.2f}, "
          f"left-edge bands {bands})")
    print(f"  pdf metadata    : title={doc.metadata.get('title')!r} "
          f"author={doc.metadata.get('author')!r}")
    print(f"  toc entries     : {len(doc.get_toc())}")
    print("\n  --- first 400 chars of page 1 (front-matter check) ---")
    print("  " + texts[0][:400].replace("\n", "\n  "))
    doc.close()
    return {"file": name, "pages": n, "chars": total_chars, "images": images,
            "columns": verdict}


if __name__ == "__main__":
    results = [audit(os.path.join(DOCS, f)) for f in FILES]
    print(f"\n\n{'=' * 72}\nSUMMARY\n{'=' * 72}")
    print(json.dumps(results, indent=2))
