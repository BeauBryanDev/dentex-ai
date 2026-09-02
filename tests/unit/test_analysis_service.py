"""The one place the two detectors and fusion meet."""
from __future__ import annotations

import numpy as np

from app.services.analysis_service import analyze_image
from tests.unit.conftest import (
    TOOTH_ID_BY_FDI,
    FakeOnnxSession,
    png_bytes,
    yolo_output,
)

CROWN_ID = 1


def square_image_bytes():
    ## 640 square so the letterbox is identity and box coordinates map straight through
    return png_bytes(np.full((640, 640, 3), 90, dtype=np.uint8))


def test_analyze_image_sorts_teeth_and_splits_restorations(test_settings):
    fdi_out = yolo_output(
        [
            (300, 300, 40, 80, TOOTH_ID_BY_FDI[37], 0.8),
            (100, 300, 40, 80, TOOTH_ID_BY_FDI[11], 0.7),
            (500, 300, 40, 80, CROWN_ID, 0.6),
        ],
        35,
    )
    result = analyze_image(
        square_image_bytes(),
        FakeOnnxSession(yolo_output([], 4)),
        FakeOnnxSession(fdi_out),
        test_settings,
    )
    assert [t.fdi for t in result.teeth] == [11, 37]
    assert [r.kind for r in result.restorations] == ["Crown"]
    assert result.image_width == 640 and result.image_height == 640


def test_analyze_image_reports_duplicated_fdi_numbers(test_settings):
    fdi_out = yolo_output(
        [
            (150, 300, 40, 80, TOOTH_ID_BY_FDI[37], 0.8),
            (450, 300, 40, 80, TOOTH_ID_BY_FDI[37], 0.7),
        ],
        35,
    )
    result = analyze_image(
        square_image_bytes(),
        FakeOnnxSession(yolo_output([], 4)),
        FakeOnnxSession(fdi_out),
        test_settings,
    )
    assert result.ambiguous_fdi == [37]
    assert "ambiguous" in result.summary()


def test_analyze_image_fuses_a_lesion_onto_its_tooth(test_settings):
    fdi_out = yolo_output([(300, 300, 100, 200, TOOTH_ID_BY_FDI[26], 0.9)], 35)
    lesion_out = yolo_output([(300, 300, 20, 20, 0, 0.6)], 4)
    result = analyze_image(
        square_image_bytes(),
        FakeOnnxSession(lesion_out),
        FakeOnnxSession(fdi_out),
        test_settings,
    )
    assert len(result.findings) == 1
    assert result.findings[0].tooth_fdi == 26
    assert result.attributed == result.findings
    assert "on tooth 26" in result.summary()


