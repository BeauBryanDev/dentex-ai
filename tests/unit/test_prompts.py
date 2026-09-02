"""Prompt assembly, where most of the token cost is bought back."""
from __future__ import annotations

from app.agent.prompts import build_system_blocks, compact_analysis

ANALYSIS = {
    "teeth": [{"fdi": 37, "box": {"x1": 1, "y1": 2, "x2": 3, "y2": 4}}, {"fdi": 11}],
    "restorations": [{"kind": "Crown", "box": {"x1": 9}}],
    "findings": [
        {
            "label": "Cavities",
            "confidence": 0.6234,
            "box": {"x1": 1, "y1": 2, "x2": 3, "y2": 4},
            "tooth_fdi": 37,
            "tooth_anatomy": "lower_left_second_molar",
            "containment": 0.5211,
        },
        {"label": "Damage", "confidence": 0.4, "tooth_fdi": None},
    ],
    "ambiguous_fdi": [44],
}


def test_compact_analysis_drops_every_pixel_coordinate():
    compact = compact_analysis(ANALYSIS)
    assert "box" not in repr(compact)
    assert compact["teeth_present"] == [11, 37]
    assert compact["restorations"] == ["Crown"]
    assert compact["ambiguous_fdi"] == [44]


def test_build_system_blocks_splits_the_cacheable_half():
    blocks = build_system_blocks(ANALYSIS)
    assert len(blocks) == 2
    assert all(b["cache_control"] == {"type": "ephemeral"} for b in blocks)
    assert "37" in blocks[1]["text"]


def test_analysis_json_is_byte_stable_under_key_reordering():
    reordered = dict(reversed(list(ANALYSIS.items())))
    assert build_system_blocks(ANALYSIS)[1] == build_system_blocks(reordered)[1]
