"""Phase 2 — cleaning (Dentex_RAG.md §6).

Phase 1 already removed the structural artifacts (watermark, running headers,
page numbers, captions, tables, bibliographies) because those had to be cut
before linearization. What is left for Phase 2 is text quality:

  1. whitespace / newline normalization (Garg alone carries 2,198 tab chars)
  2. line-break hyphenation repair ("evidence- based" -> "evidence-based"), 86
     occurrences in Garg -- these would otherwise tokenize as broken words
  3. paragraph unwrapping: PDF text arrives hard-wrapped at the line, which
     makes for poor chunk prose and worse embeddings
  4. the per-document residue Phase 0 flagged, applied per-document only:
       Dental_Caries  drop p1 (King's repository boilerplate, not the paper),
                      strip standalone page-number lines
       ISO            NOTHING numeric may be stripped -- the bare lines '1'-'4'
                      are the quadrant codes, the normative heart of the standard
       FDI / Garg     no repeated header/footer lines survive Phase 1 (verified)

Note per Beau: dangling "(Table N.N)" cross-references are NOT handled here;
they are mitigated at Phase 3 with a trailing-parenthetical regex.
"""
import json
import os
import re

IN = "/home/beaunix/Downloads/Dentex/rag/out/phase1_extracted.json"
OUT = "/home/beaunix/Downloads/Dentex/rag/out/phase2_cleaned.json"

BULLET_START = re.compile(r"^\s*(?:[•▪‣]|\d+\.\s|\d+\)\s|[a-z]\)\s|[-–—]\s)")
SENT_END = re.compile(r"[.!?:;]['\"’”]?\s*$")
HEADING_LIKE = re.compile(r"^[A-Z][A-Z \-/&,()0-9]{2,}$")
# A line that is only a number is structural, never prose: ISO clause numbers and
# the bare quadrant codes 1-4 (the normative core of ISO 3950). Unwrapping these
# into the neighbouring sentence would destroy the clause structure Phase 3 chunks on.
NUM_ONLY = re.compile(r"^\d+(?:\.\d+)*$")
# Heading sentinels emitted by Phase 1 from Garg's font bands; must stay on their
# own line so Phase 3 can chunk on them.
SENTINEL = re.compile(r"^@@H[12]@@|^\[H\d\]")


def normalize_ws(text):
    text = text.replace("\t", " ").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[   - ]+", " ", text)
    lines = [ln.strip() for ln in text.split("\n")]
    return "\n".join(ln for ln in lines if ln)


HYPHEN_BREAK = re.compile(r"(\w+)-[ \t]*\n[ \t]*([a-z]\w*)|(\w+)-[ \t]+([a-z]\w*)")


def build_vocab(texts):
    """Count how the corpus spells things where it is NOT line-broken, so a
    hyphen break can be resolved from evidence instead of a blanket rule."""
    solid, hyph = {}, {}
    for text in texts:
        flat = " ".join(text.split())
        for token in re.findall(r"[A-Za-z]+(?:-[A-Za-z]+)+", flat):
            hyph[token.lower()] = hyph.get(token.lower(), 0) + 1
        for token in re.findall(r"[A-Za-z]{4,}", flat):
            solid[token.lower()] = solid.get(token.lower(), 0) + 1
    return solid, hyph


def repair_hyphenation(text, vocab, stats):
    """Resolve a line-break hyphen by asking which form the corpus actually uses.

    'treat-\\nment'    -> 'treatment'     (syllable break, hyphen is an artifact)
    'evidence-\\nbased' -> 'evidence-based' (real compound, hyphen is meaningful)

    A blanket rule gets one of these wrong every time; Garg contains both.
    """
    solid, hyph = vocab

    def decide(match):
        left = match.group(1) or match.group(3)
        right = match.group(2) or match.group(4)
        joined, hyphenated = (left + right).lower(), f"{left}-{right}".lower()
        if hyph.get(hyphenated, 0) > solid.get(joined, 0):
            stats["kept_hyphen"] += 1
            return f"{left}-{right}"
        stats["removed_hyphen"] += 1
        return left + right

    return HYPHEN_BREAK.sub(decide, text)


def unwrap(text):
    """Join hard-wrapped lines into paragraphs; keep bullets and headings apart."""
    out = []
    for line in text.split("\n"):
        if not out:
            out.append(line)
            continue
        prev = out[-1]
        if (BULLET_START.match(line) or HEADING_LIKE.match(line)
                or SENTINEL.match(line) or SENTINEL.match(prev)
                or NUM_ONLY.match(line) or NUM_ONLY.match(prev)
                or BULLET_START.match(prev) and SENT_END.search(prev)
                or HEADING_LIKE.match(prev) or SENT_END.search(prev)):
            out.append(line)
        else:
            out[-1] = prev + " " + line
    return "\n".join(out)


def clean_text(text, vocab, stats):
    return unwrap(repair_hyphenation(normalize_ws(text), vocab, stats)).strip()


def clean_doc(doc, vocab, stats):
    src = doc["source_file"]
    pages, dropped = [], []
    for page in doc["pages"]:
        text = page["text"]

        if src == "Dental_Caries.pdf":
            if page["page"] == 1:            # repository deposit boilerplate
                dropped.append((1, "King's Research Portal boilerplate"))
                continue
            # bare page-number lines; safe here, NEVER applied to the ISO standard
            text = "\n".join(ln for ln in text.split("\n")
                             if not re.fullmatch(r"\s*\d{1,3}\s*", ln))

        cleaned = clean_text(text, vocab, stats)
        if not cleaned:
            dropped.append((page["page"], "empty after cleaning"))
            continue
        new_page = dict(page)
        new_page["text"] = cleaned
        pages.append(new_page)

    out = dict(doc)
    out["pages"] = pages
    out["dropped_pages"] = dropped
    return out


# --------------------------------------------------------------- spot checks
def spot_checks(before, after):
    print(f"\n{'=' * 74}\nPER-DOCUMENT SPOT CHECKS\n{'=' * 74}")
    for b, a in zip(before, after):
        src = a["source_file"]
        btxt = "\n".join(p["text"] for p in b["pages"])
        atxt = "\n".join(p["text"] for p in a["pages"])
        print(f"\n--- {src} ---")
        print(f"   pages {len(b['pages'])} -> {len(a['pages'])}"
              f"   words {len(btxt.split()):,} -> {len(atxt.split()):,}"
              f"   chars {len(btxt):,} -> {len(atxt):,}")
        if a["dropped_pages"]:
            print(f"   dropped: {a['dropped_pages'][:4]}"
                  f"{' ...' if len(a['dropped_pages']) > 4 else ''}")

        # residue assertions
        checks = {
            "tab chars": atxt.count("\t"),
            "control chars": sum(1 for c in atxt if ord(c) < 32 and c != "\n"),
            "double spaces": len(re.findall(r"  ", atxt)),
            "blank lines": len(re.findall(r"\n\s*\n", atxt)),
            "'word- word' splits": len(re.findall(r"\w-\s\w", atxt)),
        }
        if src == "ISO-3950-2009.pdf":
            checks["watermark residue"] = sum(
                atxt.count(s) for s in ("iTeh", "standards.iteh", "STANDARD PREVIEW"))
            quad = [ln for p in a["pages"] for ln in p["text"].split("\n")
                    if ln.strip() in {"1", "2", "3", "4"}]
            checks["quadrant codes preserved (must be >0)"] = len(quad)
        print("   " + "  ".join(f"{k}={v}" for k, v in checks.items()))

        print(f"   sample: {' '.join(a['pages'][len(a['pages']) // 2]['text'].split())[:150]!r}")


if __name__ == "__main__":
    before = json.load(open(IN))
    vocab = build_vocab([p["text"] for d in before for p in d["pages"]])
    stats = {"kept_hyphen": 0, "removed_hyphen": 0}
    after = [clean_doc(d, vocab, stats) for d in before]
    print(f"hyphen-break decisions: {stats}")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(after, f, indent=1)
    spot_checks(before, after)
    total = sum(len(p["text"].split()) for d in after for p in d["pages"])
    print(f"\n{'=' * 74}\nTOTAL CORPUS: {total:,} words across "
          f"{sum(len(d['pages']) for d in after)} pages -> {OUT}")
