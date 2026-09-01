"""Phase 3 — chunking (Dentex_RAG.md §7) + metadata schema (§8).

Target ~350 words per chunk, well under PubMedBERT's 512-token native limit (§1).
Phase 4 verifies real token counts with the model's own tokenizer; word count is
only a proxy here, deliberately conservative because dental terminology tokenizes
into more subwords than everyday English.

Per-document content units, each grounded in structure verified in Phase 0-2:
  Garg   @@H1@@/@@H2@@ sentinels carried from the font bands
  Caries the accepted manuscript's own [H1]/[H2]/[H3] markers
  ISO    numbered clauses: a bare-number line followed by a Capitalised title.
         NOT every bare-number line -- the quadrant codes have the same shape but
         are followed by lowercase ("1 / designates permanent teeth in upper right
         quadrant"), and splitting on those would shred the normative core.
  FDI    policy topic headings (question-form and the ALL-CAPS area-of-work labels)

Per Beau: trailing "(Table N.N)" cross-references are stripped here, since the
tables themselves were discarded in Phase 1 and the pointer would dangle.
"""
import json
import os
import re

IN = "/home/beaunix/Downloads/Dentex/rag/out/phase2_cleaned.json"
OUT = "/home/beaunix/Downloads/Dentex/rag/out/phase3_chunks.json"

TARGET_WORDS = 350
MAX_WORDS = 450
OVERLAP_WORDS = 75

# PubMedBERT is BERT-base: a hard 512-token window (§1). Word counts cannot
# enforce that -- measured tokens/word runs 1.33 on average but reaches 2.15 on
# dense dental terminology, so a 449-word chunk was producing 777 tokens and
# would have been silently truncated. Windows are therefore built against a real
# token budget, with the word target kept only as a secondary shaping hint.
TARGET_TOKENS = 400     # leaves headroom below 512 for [CLS]/[SEP] + section label
HARD_TOKEN_LIMIT = 500
_TOKENIZER = None
_WORD_TOKENS = {}


def _tokenizer():
    global _TOKENIZER
    if _TOKENIZER is None:
        from transformers import AutoTokenizer
        _TOKENIZER = AutoTokenizer.from_pretrained(
            "NeuML/pubmedbert-base-embeddings")
    return _TOKENIZER


def word_tokens(word):
    """Token cost of a single word, memoized (~20k unique words in this corpus)."""
    if word not in _WORD_TOKENS:
        _WORD_TOKENS[word] = len(
            _tokenizer()(word, add_special_tokens=False)["input_ids"])
    return _WORD_TOKENS[word]


def token_windows(words, label_cost):
    """Greedy windows under the token budget, with OVERLAP_WORDS of overlap."""
    budget = TARGET_TOKENS - label_cost - 2      # [CLS] / [SEP]
    windows, start = [], 0
    while start < len(words):
        used, end = 0, start
        while end < len(words) and used + word_tokens(words[end]) <= budget:
            used += word_tokens(words[end])
            end += 1
        if end == start:                          # single oversized token-dense word
            end = start + 1
        windows.append(words[start:end])
        if end >= len(words):
            break
        start = max(end - OVERLAP_WORDS, start + 1)
    return windows
MIN_WORDS = 25          # below this, a section is packed into its neighbour
# A short section that could not be packed (no same-parent neighbour) is still
# worth keeping if it carries real content: ISO's Clause 1 Scope is 19 words and
# is the most quotable normative sentence in the standard. Only true fragments
# are dropped.
MIN_CHUNK_WORDS = 12

EXCLUDE_FRONT_MATTER = {"ISO-3950-2009.pdf"}

SENT_H = re.compile(r"^@@(H[12])@@\s*(.*)$")
AM_H = re.compile(r"\[H([123])\]\s*")
NUM_ONLY = re.compile(r"^\d+(?:\.\d+)*$")
CLAUSE_TITLE = re.compile(r"^[A-Z][A-Za-z ]{2,40}$")
# Beau's approved mitigation: kill the dangling pointer, keep the sentence.
TABLE_REF = re.compile(r"\s*[（(]\s*(?:see\s+)?Tables?\s*\d+\.\d+\s*[)）]")
FDI_HEADING = re.compile(
    r"^(?:[A-Z][A-Za-z’' ]{4,60}\?|PROMOTION|LEGISLATION|FUNDRAISING|ADVOCACY|"
    r"SCIENCE|Target audience groups:|Areas of work[^\n]{0,60})$")


def scrub(text):
    text = TABLE_REF.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


def lines_with_pages(doc):
    """Flatten to (line, page) so a chunk can report the pages it spans."""
    out = []
    for page in doc["pages"]:
        pno = page.get("printed_page", page["page"])
        for line in page["text"].split("\n"):
            if line.strip():
                out.append((line.strip(), pno))
    return out


def emit(sections, doc, chunks):
    """Turn (section_label, [(line,page)]) units into schema-conformant chunks."""
    slug = re.sub(r"[^a-z0-9]+", "-", doc["source_file"].lower().replace(".pdf", ""))
    for label, body in sections:
        # ISO carries its own reference list; excluded on the same grounds as
        # Garg's per-chapter bibliographies and the Caries reference section.
        if re.match(r"(Clause \d+ )?(Bibliography|References)\b", label or ""):
            continue
        # ISO front matter is pure boilerplate -- copyright office address, the
        # Adobe PDF disclaimer, and the foreword on ISO committee procedure. It
        # answers nothing, but it was 3 of only 7 ISO chunks and outscored real
        # clauses on vague queries, crowding them out of the normative slots.
        # Scoped to ISO: the Caries front matter carries title/authors.
        if doc["source_file"] in EXCLUDE_FRONT_MATTER and label == "Front matter":
            continue
        text = scrub(" ".join(l for l, _ in body))
        if not text:
            continue
        pages = [p for _, p in body]
        words = text.split()

        label_cost = len(_tokenizer()(f"{label}. ", add_special_tokens=False)
                         ["input_ids"]) if label else 0
        windows = token_windows(words, label_cost)

        for part, window in enumerate(windows):
            if len(window) < MIN_CHUNK_WORDS:   # true fragment, not embeddable
                continue
            body_text = " ".join(window)
            # Prefix the section label so an isolated chunk still says what it is
            full = f"{label}. {body_text}" if label else body_text
            chunks.append({
                "text": full,
                "chunk_id": f"{slug}#{len(chunks):04d}",
                "document_title": doc["document_title"],
                "source_file": doc["source_file"],
                "epistemic_status": doc["epistemic_status"],
                "section": label or None,
                "page_start": min(pages),
                "page_end": max(pages),
                "chunk_type": "narrative",
                "_part": part,
                "_words": len(window),
            })


# ------------------------------------------------------------------ per-document
def sections_garg(doc):
    sections, chapter, label, body = [], "", "", []
    pending_h1 = []
    for line, page in lines_with_pages(doc):
        m = SENT_H.match(line)
        if not m:
            body.append((line, page))
            continue
        level, text = m.group(1), m.group(2).strip()
        if not text:
            continue
        if level == "H1":
            # 'Chapter' renders as its own large-font line; glue it to the title
            if text.lower() == "chapter" or text.isdigit():
                pending_h1.append(text)
                continue
            if body:
                sections.append((f"{chapter} — {label}".strip(" —"), body))
                body = []
            chapter, label, pending_h1 = text, "", []
        else:
            if body:
                sections.append((f"{chapter} — {label}".strip(" —"), body))
                body = []
            label = text
    if body:
        sections.append((f"{chapter} — {label}".strip(" —"), body))
    return sections


def sections_caries(doc):
    """Split on the manuscript's own [H1]/[H2]/[H3] tags."""
    sections, label, body = [], "Front matter", []
    for line, page in lines_with_pages(doc):
        parts = AM_H.split(line)
        if len(parts) == 1:
            body.append((line, page))
            continue
        # parts alternates: text, level, text, level, ...
        if parts[0].strip():
            body.append((parts[0].strip(), page))
        for i in range(1, len(parts) - 1, 2):
            if body:
                sections.append((label, body))
                body = []
            rest = parts[i + 1].strip()
            head = rest.split(". ")[0] if ". " in rest[:80] else rest
            words = head.split()
            label = " ".join(words[:6])
            remainder = rest[len(label):].strip()
            if remainder:
                body.append((remainder, page))
    if body:
        sections.append((label, body))
    return sections


def sections_iso(doc):
    sections, label, body = [], "Front matter", []
    pending_num = None
    expected = 1        # clause numbers run 1,2,3,... in order
    for line, page in lines_with_pages(doc):
        if NUM_ONLY.match(line):
            pending_num = line
            continue
        # A clause boundary needs BOTH: an uppercase follower (a lowercase one is
        # a tooth/quadrant code, which must stay in the body) AND the next number
        # in sequence -- otherwise the cover page's '3950' and the repeated page
        # header '1' get mistaken for clauses.
        # The standard's own title line ("Dentistry — Designation system for...")
        # repeats as a page header and would otherwise be read as clause 1.
        if pending_num and line[:1].isupper() and pending_num == str(expected) \
                and "—" not in line[:60]:
            if body:
                sections.append((label, body))
                body = []
            words = line.split()
            # A clause title is its first word plus any following all-lowercase
            # words ("Designation of areas of the oral cavity"); it ends where the
            # body sentence starts ("Scope | This International Standard...") or
            # where an enumerator begins ("Designation of teeth | a) First digit").
            title_words = [words[0]]
            for w in words[1:]:
                if w.isalpha() and w.islower():
                    title_words.append(w)
                else:
                    break
            title = " ".join(title_words)
            label = f"Clause {pending_num} {title}"
            expected += 1
            rest = line[len(title):].strip()
            if rest:
                body.append((rest, page))
            pending_num = None
            continue
        if pending_num:                 # quadrant/tooth code, NOT a clause boundary
            body.append((f"{pending_num} {line}", page))
            pending_num = None
            continue
        body.append((line, page))
    if body:
        sections.append((label, body))
    return sections


def sections_fdi(doc):
    sections, label, body = [], "Introduction", []
    for line, page in lines_with_pages(doc):
        if FDI_HEADING.match(line):
            if body:
                sections.append((label, body))
                body = []
            label = line.rstrip(":")
            continue
        body.append((line, page))
    if body:
        sections.append((label, body))
    return sections


BUILDERS = {
    "Operative_Dentistry_Garg_3rd_ed.pdf": sections_garg,
    "Dental_Caries.pdf": sections_caries,
    "ISO-3950-2009.pdf": sections_iso,
    "FDI_Policy_Statements_Toolkit.pdf": sections_fdi,
}


def pack_sections(sections):
    """Pack consecutive short sections up toward the ~350-word target.

    Garg carries 2,152 H2 headings over 176k words -- roughly 80 words each. One
    chunk per heading would bury real content in title-heavy fragments and blow
    the chunk count past 1,500. Sections are merged only while they share a
    parent (chapter for Garg), so a chunk never straddles a chapter boundary.
    """
    packed = []
    for label, body in sections:
        words = sum(len(l.split()) for l, _ in body)
        if packed:
            prev_label, prev_body = packed[-1]
            prev_words = sum(len(l.split()) for l, _ in prev_body)
            same_parent = (prev_label.split(" — ")[0] == label.split(" — ")[0])
            if same_parent and (prev_words + words <= TARGET_WORDS
                                or words < MIN_WORDS):
                # Keep the absorbed section's heading inside the body. Only the
                # first label survives as `section`, and dropping the rest would
                # lose real query terms ("Cariology", "DEFINITIONS") from ~1,376
                # merged headings.
                sub = label.split(" — ")[-1]
                head = [(f"{sub}:", body[0][1])] if sub and body else []
                packed[-1] = (prev_label, prev_body + head + body)
                continue
        packed.append((label, body))
    return packed


if __name__ == "__main__":
    docs = json.load(open(IN))
    chunks = []
    print(f"{'document':38} {'sections':>9} {'chunks':>8} {'w/chunk':>9}")
    print("-" * 68)
    for doc in docs:
        before = len(chunks)
        sections = pack_sections(BUILDERS[doc["source_file"]](doc))
        emit(sections, doc, chunks)
        made = chunks[before:]
        avg = sum(c["_words"] for c in made) / max(len(made), 1)
        print(f"{doc['source_file']:38} {len(sections):>9} {len(made):>8} {avg:>9.0f}")
    print("-" * 68)
    print(f"{'TOTAL':38} {'':>9} {len(chunks):>8}")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(chunks, f, indent=1)
    print(f"\nwrote {OUT}")
