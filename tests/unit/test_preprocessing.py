"""Letterboxing and tensor prep, which must match what Colab did at export time."""
from __future__ import annotations

import numpy as np
import pytest

from app.utils.postprocessing import scale_boxes
from app.utils.preprocessing import PAD_VALUE, letterbox, prepare


def test_letterbox_pads_a_panoramic_to_square_without_distorting_it():
    img = np.zeros((400, 800, 3), dtype=np.uint8)
    padded, meta = letterbox(img, 640)
    assert padded.shape == (640, 640, 3)
    assert meta.ratio == pytest.approx(0.8)
    assert meta.pad_x == 0 and meta.pad_y == 160
    assert padded[0, 0].tolist() == [PAD_VALUE] * 3


def test_letterbox_metadata_round_trips_a_box_back_to_original_pixels():
    img = np.zeros((400, 800, 3), dtype=np.uint8)
    _, meta = letterbox(img, 640)
    original = np.array([[100.0, 50.0, 300.0, 250.0]])
    boxed = original * meta.ratio
    boxed[:, [0, 2]] += meta.pad_x
    boxed[:, [1, 3]] += meta.pad_y
    assert scale_boxes(boxed, meta)[0].tolist() == pytest.approx(original[0].tolist())


def test_prepare_emits_the_tensor_shape_both_graphs_declare():
    img = np.full((400, 800, 3), 255, dtype=np.uint8)
    tensor, _ = prepare(img, 640)
    assert tensor.shape == (1, 3, 640, 640)
    assert tensor.dtype == np.float32
    assert tensor.max() <= 1.0


