"""Phase 1 — extraction (Dentex_RAG.md §5), written against Phase 0's measurements.

Per-document strategy, all of it grounded in what phase0_audit/phase0_probes found:

  Dental_Caries  plain get_text(), pages 1-34 (References heading sits on p35)
  ISO-3950       exact-full-line frequency filter; watermark is horizontal, so the
                 spec's rotation method (§4 step 1) does not apply -- 0/224 lines
                 were rotated. Watermark and real running header are tracked
                 separately because 'ISO 3950:2009' is a strict PREFIX of the real
                 header 'ISO 3950:2009(E)' -- substring matching would corrupt it.
  FDI            linear blocks; page 3's infographic dropped per Beau; page footer
                 'FDI Policy Statement Toolkit PAGE n' stripped
  Garg           pages 21-534 (ch.1 starts p21, Index starts p535), two-column
                 bbox-ordered, with a font-size gate doing the region cutting:
                 captions + table cells + panel letters all live at <=8.5pt and are
                 cut BEFORE linearization so fragments cannot bleed into adjacent
                 prose (the OryzaMind lesson, §3.4). Per-chapter BIBLIOGRAPHY blocks
                 excluded per Beau's decision.

Writes rag/out/phase1_extracted.json plus a per-document cut report for review.
"""
import json
import os
import re
import unicodedata

import pymupdf

DOCS = "/home/beaunix/Downloads/Dentex/Docs4RAG"
OUT = "/home/beaunix/Downloads/Dentex/rag/out"

# Garg font bands, measured in Phase 0 (see table in the audit report)
GARG_JUNK_MAX = 8.8      # captions, table cells, figure panel letters
GARG_HEADER_MAX = 9.3    # running header
GARG_BODY_MAX = 10.5     # body prose (9.5)
GARG_HEADING_MAX = 11.8  # section headings (11.0)

CAPTION_RE = re.compile(r"^\s*(Figures?|Tables?|Flowcharts?|Box)\s*\d+\.\d+", re.I)

# Heading sentinels: the font-size band is the only reliable heading signal in
# Garg, and it is lost once text is linearized. Tag it here, consume it in Phase 3.
H1 = "@@H1@@ "   # chapter title (17/24pt)
H2 = "@@H2@@ "   # section heading (11pt)


def norm(text):
    """Phase 2 will do full cleaning; here we only kill control chars and exotic
    spaces so that downstream counts are stable (Phase 0 found 111 \\x07 in Garg)."""
    text = text.replace(" ", " ").replace(" ", " ").replace("\xa0", " ")
    text = "".join(ch for ch in text if ch >= " " or ch in "\n\t")
    return unicodedata.normalize("NFKC", text)


# ---------------------------------------------------------------- Dental_Caries
def extract_caries():
    doc = pymupdf.open(os.path.join(DOCS, "Dental_Caries.pdf"))
    pages = []
    for pno in range(0, 34):  # p35 is the References heading; body is 1-34
        pages.append({"page": pno + 1, "text": norm(doc[pno].get_text())})
    doc.close()
    return {"source_file": "Dental_Caries.pdf",
            "document_title": "Dental caries (Pitts et al., Nature Reviews Disease "
                              "Primers 3:17030, 2017; accepted manuscript)",
            "epistemic_status": "peer_reviewed_research",
            "pages": pages,
            "notes": ["pages 35-49 excluded: References + figure plates"]}


# -------------------------------------------------------------------- ISO 3950
def extract_iso():
    path = os.path.join(DOCS, "ISO-3950-2009.pdf")
    doc = pymupdf.open(path)
    n = doc.page_count

    # measure exact-line frequency across pages
    freq = {}
    for pno in range(n):
        for line in {l.strip() for l in doc[pno].get_text().splitlines() if l.strip()}:
            freq[line] = freq.get(line, 0) + 1

    watermark_seeds = ("iteh", "standards.iteh.ai", "iso-3950-2009")
    watermark, running = set(), set()
    for line, count in freq.items():
        if count < n * 0.5:
            continue
        low = line.lower()
        if any(s in low for s in watermark_seeds) or line == "ISO 3950:2009":
            watermark.add(line)
        else:
            running.add(line)

    pages, cut_samples = [], []
    for pno in range(n):
        kept = []
        for raw in doc[pno].get_text().splitlines():
            line = raw.strip()
            if not line:
                continue
            if line in watermark:            # EXACT match only, never substring
                cut_samples.append(("watermark", pno + 1, line))
                continue
            if line in running:
                cut_samples.append(("running_header", pno + 1, line))
                continue
            kept.append(line)
        pages.append({"page": pno + 1, "text": norm("\n".join(kept))})
    doc.close()
    return {"source_file": "ISO-3950-2009.pdf",
            "document_title": "ISO 3950:2009(E) Dentistry - Designation system for "
                              "teeth and areas of the oral cavity (third edition, 2009-05-15)",
            "epistemic_status": "normative_standard",
            "pages": pages,
            "watermark_lines": sorted(watermark),
            "running_header_lines": sorted(running),
            "cut_samples": cut_samples[:12]}


# ------------------------------------------------------------------ FDI toolkit
FDI_FOOTER_RE = re.compile(r"^FDI Policy Statement Toolkit\s+PAGE\s*\d+$", re.I)


def extract_fdi():
    doc = pymupdf.open(os.path.join(DOCS, "FDI_Policy_Statements_Toolkit.pdf"))
    pages, dropped = [], []
    for pno in range(doc.page_count):
        page = doc[pno]
        blocks = [b for b in page.get_text("blocks") if b[4].strip()]
        blocks.sort(key=lambda b: (round(b[1] / 10), b[0]))  # reading order, y then x
        kept = []
        for b in blocks:
            text = " ".join(b[4].split())
            if FDI_FOOTER_RE.match(text):
                continue
            # p3 holds the PS-adoption flow diagram; Beau: drop the diagram, keep prose.
            # Its labels are short fragments sitting left of the x=214 body margin.
            if pno == 2 and (b[0] < 200 or len(text) < 60):
                dropped.append((pno + 1, text))
                continue
            kept.append(text)
        pages.append({"page": pno + 1, "text": norm("\n".join(kept))})
    doc.close()
    return {"source_file": "FDI_Policy_Statements_Toolkit.pdf",
            "document_title": "FDI Policy Statement Toolkit: How National Dental "
                              "Associations Can Use FDI Policy Statements to Promote "
                              "Oral Health (2019)",
            "epistemic_status": "policy_position",
            "pages": pages,
            "notes": ["publication date 2019 taken from original filename "
                      "(FDI-Policy_Statement_Toolkit-2019_EN.pdf); no date appears "
                      "anywhere in the document body"],
            "dropped_diagram_fragments": dropped}


# ------------------------------------------------------------------------ Garg
def extract_garg():
    doc = pymupdf.open(os.path.join(DOCS, "Operative_Dentistry_Garg_3rd_ed.pdf"))
    pages = []
    cut_counts = {"caption_or_table": 0, "running_header": 0, "page_number": 0,
                  "bibliography": 0}
    in_biblio = False

    for pno in range(20, 534):  # ch.1 starts at pdf p21; Index starts at pdf p535
        page = doc[pno]
        mid = page.rect.width / 2
        items = []
        for block in page.get_text("dict")["blocks"]:
            if block.get("type") != 0:
                continue
            for line in block["lines"]:
                text = "".join(s["text"] for s in line["spans"]).strip()
                if not text:
                    continue
                size = round(line["spans"][0]["size"], 1)
                x0, y0 = line["bbox"][0], line["bbox"][1]
                col = 0 if x0 < mid else 1
                items.append((col, y0, x0, size, text))
        items.sort(key=lambda t: (t[0], t[1], t[2]))  # column, then down the column

        kept, page_started_in_biblio = [], in_biblio
        for _col, _y, _x, size, text in items:
            if size >= GARG_HEADING_MAX:
                if re.fullmatch(r"\d{1,4}", text):
                    cut_counts["page_number"] += 1
                    continue
                in_biblio = False           # chapter title ends any bibliography run
                # Tag headings so the font signal survives into Phase 3, which
                # chunks on it. Without the tag, title-case headings are
                # indistinguishable from prose once linearized and get swallowed
                # ("Dental Caries It is defined as multifactorial...").
                kept.append(H1 + text)
                continue
            if size > GARG_BODY_MAX:        # 11pt heading band
                if text.strip().upper().startswith("BIBLIOGRAPHY"):
                    in_biblio = True
                    cut_counts["bibliography"] += 1
                    continue
                in_biblio = False           # a new real heading ends the reference list
                kept.append(H2 + text)
                continue
            if size <= GARG_JUNK_MAX:       # captions + table cells + panel letters
                cut_counts["caption_or_table"] += 1
                continue
            if size <= GARG_HEADER_MAX:     # running header
                cut_counts["running_header"] += 1
                continue
            if in_biblio:
                cut_counts["bibliography"] += 1
                continue
            if CAPTION_RE.match(text):      # belt-and-braces, caught pre-linearization
                cut_counts["caption_or_table"] += 1
                continue
            kept.append(text)

        pages.append({"page": pno + 1, "printed_page": pno - 19,
                      "text": norm("\n".join(kept)),
                      "biblio_page": page_started_in_biblio})
    doc.close()
    return {"source_file": "Operative_Dentistry_Garg_3rd_ed.pdf",
            "document_title": "Textbook of Operative Dentistry, 3rd edition "
                              "(Nisha Garg & Amit Garg, Jaypee Brothers Medical "
                              "Publishers, New Delhi)",
            "epistemic_status": "educational_textbook",
            "pages": pages,
            "cut_counts": cut_counts,
            "notes": ["pdf p1-20 front matter and p535-544 Index excluded",
                      "figure captions, tables and panel letters cut by font band "
                      "before linearization",
                      "per-chapter BIBLIOGRAPHY blocks excluded"]}


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    docs = [extract_caries(), extract_iso(), extract_fdi(), extract_garg()]
    with open(os.path.join(OUT, "phase1_extracted.json"), "w") as f:
        json.dump(docs, f, indent=1)

    print(f"{'document':38} {'pages':>6} {'words':>10}")
    print("-" * 58)
    total = 0
    for d in docs:
        words = sum(len(p["text"].split()) for p in d["pages"])
        total += words
        print(f"{d['source_file']:38} {len(d['pages']):>6} {words:>10,}")
    print("-" * 58)
    print(f"{'TOTAL':38} {'':>6} {total:>10,}")

    iso = docs[1]
    print("\nISO watermark lines removed (exact match):")
    for line in iso["watermark_lines"]:
        print(f"   WM   {line[:72]!r}")
    print("ISO running-header lines removed (kept separate on purpose):")
    for line in iso["running_header_lines"]:
        print(f"   HDR  {line[:72]!r}")

    print("\nGarg cut counts:", docs[3]["cut_counts"])
    print(f"FDI diagram fragments dropped from p3: "
          f"{len(docs[2]['dropped_diagram_fragments'])}")
