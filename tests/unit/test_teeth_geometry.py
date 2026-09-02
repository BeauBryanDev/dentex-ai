"""FDI anatomy and the chart the frontend draws."""
from __future__ import annotations

from app.utils.teeth_geometry import (
    annotate,
    fdi_from_class_name,
    patient_side_of,
    viewer_side_of,
)


def test_patient_right_quadrants_render_on_the_viewer_left():
    assert patient_side_of(16) == "right"
    assert viewer_side_of(16) == "left"
    assert viewer_side_of(46) == "left"
    assert viewer_side_of(26) == "right"


def test_fdi_from_class_name_ignores_restoration_labels():
    assert fdi_from_class_name("T26") == 26
    assert fdi_from_class_name("Crown") is None
    assert fdi_from_class_name("T99") is None


def test_annotate_marks_presence_findings_and_ambiguity_per_slot():
    rows = annotate([26, 37], {26: ["Cavities"]}, ambiguous_fdi=[37])
    by_fdi = {row["fdi"]: row for row in rows}
    assert len(rows) == 32
    assert by_fdi[26]["present"] is True
    assert by_fdi[26]["findings"] == ["Cavities"]
    assert by_fdi[37]["ambiguous"] is True
    assert by_fdi[11]["present"] is False
