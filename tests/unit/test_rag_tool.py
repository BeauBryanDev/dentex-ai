"""Rendering retrieval for Claude. The retriever itself is a spy."""
from __future__ import annotations

from app.tools.rag_tool import MAX_CHARS_PER_HIT, run_search
from tests.unit.conftest import FakeRetriever, sample_hit


def test_run_search_renders_source_section_and_page_range():
    result = run_search(FakeRetriever(), "management of proximal caries")
    assert result.hit_count == 1
    assert "Operative_Dentistry_Garg_3rd_ed.pdf" in result.text
    assert "pp120-121" in result.text
    assert "educational_textbook" in result.text


def test_long_passages_are_truncated_on_a_word_boundary():
    retriever = FakeRetriever([sample_hit("word " * 400)])
    body = run_search(retriever, "caries").text
    assert "[...]" in body.replace("[…]", "[...]")
    assert len(body) < MAX_CHARS_PER_HIT + 400


def test_empty_retrieval_states_the_corpus_gap_instead_of_returning_nothing():
    result = run_search(FakeRetriever([]), "orthodontic bracket bonding")
    assert result.hit_count == 0
    assert "No passages in the corpus matched" in result.text
    assert result.text.strip() != ""


