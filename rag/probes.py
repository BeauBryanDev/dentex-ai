"""Phase 0 document-specific probes (Dentex_RAG.md §4).

ISO   -> watermark removal strategy, determined empirically in the spec's priority order
FDI   -> linear text flow vs infographic/callout layout
Garg  -> real Chapter 1 start, page-number position
"""
import collections
import os
import re

import pymupdf

DOCS = "/home/beaunix/Downloads/Dentex/Docs4RAG"


def hdr(t):
    print(f"\n{'=' * 72}\n{t}\n{'=' * 72}")


def iso_watermark():
    hdr("ISO-3950-2009.pdf — watermark strategy")
    doc = pymupdf.open(os.path.join(DOCS, "ISO-3950-2009.pdf"))

    # Step 1 of the spec's priority order: is the watermark rotated?
    dirs = collections.Counter()
    rotated_samples = []
    for pno in range(doc.page_count):
        for block in doc[pno].get_text("dict")["blocks"]:
            if block.get("type") != 0:
                continue
            for line in block["lines"]:
                d = tuple(round(x, 2) for x in line["dir"])
                txt = "".join(s["text"] for s in line["spans"]).strip()
                if not txt:
                    continue
                dirs[d] += 1
                if d != (1.0, 0.0):
                    rotated_samples.append((pno + 1, d, txt[:70]))
    print(f"  line direction vectors: {dict(dirs)}")
    print(f"  non-horizontal lines  : {len(rotated_samples)}")
    for s in rotated_samples[:5]:
        print(f"      p{s[0]} dir={s[1]} {s[2]!r}")

    # Step 2: cross-page repetition frequency
    print("\n  --- cross-page repetition (9 pages; near-universal text = background) ---")
    freq = collections.Counter()
    for pno in range(doc.page_count):
        seen = set()
        for line in doc[pno].get_text().splitlines():
            t = line.strip()
            if t:
                seen.add(t)
        for t in seen:
            freq[t] += 1
    for text, count in freq.most_common(14):
        if count >= 3:
            print(f"      {count}/9 pages  {text[:78]!r}")

    # What a frequency>=50% filter would remove, and what it would cost
    thresh = doc.page_count * 0.5
    removed = [t for t, c in freq.items() if c >= thresh]
    print(f"\n  lines appearing on >=50% of pages (removal candidates): {len(removed)}")
    for t in removed:
        print(f"      {t[:78]!r}")
    doc.close()


def fdi_layout():
    hdr("FDI_Policy_Statements_Toolkit.pdf — layout / reading order")
    doc = pymupdf.open(os.path.join(DOCS, "FDI_Policy_Statements_Toolkit.pdf"))
    total_img_bytes = 0
    for pno in range(doc.page_count):
        page = doc[pno]
        blocks = [b for b in page.get_text("blocks") if b[4].strip()]
        for xref, *_ in page.get_images(full=True):
            try:
                total_img_bytes += len(doc.extract_image(xref)["image"])
            except Exception:
                pass
        print(f"\n  --- page {pno + 1}: {len(blocks)} text blocks, "
              f"{len(page.get_images(full=True))} images, "
              f"page {page.rect.width:.0f}x{page.rect.height:.0f} ---")
        for b in blocks[:8]:
            x0, y0, x1, y1, text = b[0], b[1], b[2], b[3], b[4]
            flat = " ".join(text.split())
            print(f"      x{x0:6.1f}-{x1:6.1f} y{y0:6.1f}  {flat[:66]!r}")
        if len(blocks) > 8:
            print(f"      ... +{len(blocks) - 8} more blocks")
    size = os.path.getsize(os.path.join(DOCS, "FDI_Policy_Statements_Toolkit.pdf"))
    print(f"\n  embedded image bytes: {total_img_bytes / 1e6:.2f} MB of "
          f"{size / 1e6:.2f} MB file ({100 * total_img_bytes / size:.0f}%)")
    doc.close()


def garg_structure():
    hdr("Operative_Dentistry_Garg_3rd_ed.pdf — front matter / chapter 1 / page numbers")
    doc = pymupdf.open(os.path.join(DOCS, "Operative_Dentistry_Garg_3rd_ed.pdf"))

    print("  --- scanning first 60 pages for the real Chapter 1 start ---")
    for pno in range(min(60, doc.page_count)):
        text = doc[pno].get_text()
        flat = " ".join(text.split())
        if not flat:
            print(f"      p{pno + 1:3d}  <empty>")
            continue
        marker = ""
        if re.search(r"\b(Preface|Dedication|Acknowledg|Contents|Foreword)\b", flat[:200], re.I):
            marker = "  <-- FRONT MATTER"
        if re.search(r"^\s*(Chapter\s*1\b|1\s*\n)", text, re.I | re.M):
            marker = "  <== CHAPTER 1 CANDIDATE"
        print(f"      p{pno + 1:3d}  {flat[:72]!r}{marker}")

    print("\n  --- page-number position: top/bottom-most short numeric spans, sample body pages ---")
    for pno in (80, 120, 200, 300, 400):
        page = doc[pno]
        h, w = page.rect.height, page.rect.width
        cands = []
        for block in page.get_text("dict")["blocks"]:
            if block.get("type") != 0:
                continue
            for line in block["lines"]:
                for span in line["spans"]:
                    t = span["text"].strip()
                    if re.fullmatch(r"\d{1,4}", t):
                        x0, y0, x1, y1 = span["bbox"]
                        where = ("top" if y0 < 0.12 * h else
                                 "bottom" if y1 > 0.88 * h else "body")
                        side = ("left" if x1 < 0.35 * w else
                                "right" if x0 > 0.65 * w else "centre")
                        if where != "body":
                            cands.append(f"{t!r}@{where}-{side}(y={y0:.0f},x={x0:.0f})")
        print(f"      p{pno + 1:3d}: {cands if cands else 'no margin page-number span found'}")
    doc.close()


if __name__ == "__main__":
    iso_watermark()
    fdi_layout()
    garg_structure()
