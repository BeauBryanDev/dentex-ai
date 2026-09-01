
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


MAX_CHARS_PER_HIT = 600
DEFAULT_HITS = 4


@dataclass(frozen=True)
class RagToolResult:
    """What the tool returned, plus what the UI needs to show it was consulted."""

    text: str
    hit_count: int


def _format_hit(hit: dict[str, Any], 
                rank: int
                ) -> str:
    
    pages = hit.get("page_start")
    page_end = hit.get("page_end")
    page_ref = f"p{pages}" if pages == page_end or page_end is None else f"pp{pages}-{page_end}"

    body = (hit.get("text") or "").strip()
    
    if len(body) > MAX_CHARS_PER_HIT:
        
        body = body[:MAX_CHARS_PER_HIT].rsplit(" ", 1)[0] + " […]"

    return (
        
        f"[{rank}] {hit.get('source_file', 'unknown')} — {hit.get('section', '')} ({page_ref})\n"
        f"    status: {hit.get('epistemic_status', 'unknown')} | similarity: {hit.get('score', 0):.3f}\n"
        f"{body}"
    )

#  Search_dental_reference
def run_search(retriever: Any, 
               query: str, 
               total: int = DEFAULT_HITS
               ) -> RagToolResult:
    """
    Run one retrieval and render it for Claude.

    An empty result is returned as an explicit statement rather than an empty string: a
    blank tool_result reads as a malfunction and invites the model to fall back on memory,
    which is the one thing the grounding is there to prevent.
    """
    hits = retriever.search(query, total=total)

    if not hits:
        
        return RagToolResult(
            
            text=(
                f"No passages in the corpus matched: {query!r}\n"
                "The corpus covers operative dentistry, dental caries, FDI policy and "
                "ISO 3950 only. Say that it does not cover this rather than answering "
                "from memory — in the dentist's own language, as always.\n"
                "If the query above was not in English, that alone may be why nothing "
                "matched: the corpus is English. Retry once with an English query before "
                "concluding the corpus has nothing."
            ),
            hit_count=0,
        )

    header = f"{len(hits)} passages for: {query!r}\n"
    
    return RagToolResult(
        
        text=header + "\n\n".join(_format_hit(h, i) for i, h in enumerate(hits, 1)),
        hit_count=len(hits),
    )
