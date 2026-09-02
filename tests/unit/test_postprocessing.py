"""Box math, NMS and the inverse letterbox."""
from __future__ import annotations

import numpy as np
import pytest

from app.utils.postprocessing import (
    class_aware_nms,
    containment_matrix,
    decode,
    iou_matrix,
    scale_boxes,
)
from app.utils.preprocessing import Letterbox
from tests.unit.conftest import yolo_output


def test_containment_sees_lesion_that_iou_would_discard():
    ## a small caries fully inside a molar: containment 1.0, IoU well under the old 0.1 gate
    lesion = np.array([[10.0, 10.0, 20.0, 20.0]], dtype=np.float32)
    tooth = np.array([[0.0, 0.0, 100.0, 100.0]], dtype=np.float32)
    assert containment_matrix(lesion, tooth)[0, 0] == pytest.approx(1.0, abs=1e-6)
    assert iou_matrix(lesion, tooth)[0, 0] < 0.1


def test_class_aware_nms_keeps_neighbours_but_drops_same_class_duplicate():
    boxes = np.array(
        [
            [0.0, 0.0, 10.0, 10.0],
            [1.0, 0.0, 11.0, 10.0],
            [1.0, 0.0, 11.0, 10.0],
        ],
        dtype=np.float32,
    )
    scores = np.array([0.9, 0.8, 0.7], dtype=np.float32)
    kept_across = class_aware_nms(boxes[:2], scores[:2], np.array([5, 6]), 0.5)
    kept_within = class_aware_nms(boxes[1:], scores[1:], np.array([6, 6]), 0.5)
    assert sorted(kept_across.tolist()) == [0, 1]
    assert kept_within.tolist() == [0]


def test_scale_boxes_removes_padding_before_dividing_and_clips():
    meta = Letterbox(ratio=0.5, pad_x=10, pad_y=20, orig_w=1000, orig_h=800)
    boxes = np.array([[110.0, 120.0, 210.0, 220.0], [0.0, 0.0, 9000.0, 9000.0]])
    scaled = scale_boxes(boxes, meta)
    assert scaled[0].tolist() == [200.0, 200.0, 400.0, 400.0]
    assert scaled[1].tolist() == [0.0, 0.0, 1000.0, 800.0]


def test_decode_rejects_class_list_out_of_sync_with_weights():
    meta = Letterbox(ratio=1.0, pad_x=0, pad_y=0, orig_w=640, orig_h=640)
    output = yolo_output([(100, 100, 40, 40, 0, 0.9)], 4)
    with pytest.raises(ValueError, match="out of sync"):
        decode(output, meta, ["Cavities", "Damage"], 0.2, 0.8)


def test_decode_keeps_raw_scores_alongside_boosted_ones():
    meta = Letterbox(ratio=1.0, pad_x=0, pad_y=0, orig_w=640, orig_h=640)
    output = yolo_output([(100, 100, 40, 40, 2, 0.9)], 4)
    dets = decode(output, meta, ["Cavities", "Damage", "Infection", "Wisdom"], 0.2, 0.8)
    assert dets.scores[0] == pytest.approx(1.0)
    assert dets.raw_scores[0] == pytest.approx(0.9, abs=1e-5)
    assert dets.labels == ["Infection"]
