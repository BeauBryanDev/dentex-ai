"""Decoding uploaded bytes, which are frequently single channel."""
from __future__ import annotations

import numpy as np
import pytest

from app.core.exception import ImageDecodeError
from app.utils.image_utils import load_image
from tests.unit.conftest import png_bytes


def test_grayscale_radiograph_becomes_three_channel_bgr():
    img = load_image(png_bytes(np.full((32, 64), 120, dtype=np.uint8)))
    assert img.shape == (32, 64, 3)
    assert img.dtype == np.uint8


def test_png_with_alpha_loses_its_alpha_channel():
    rgba = np.zeros((16, 16, 4), dtype=np.uint8)
    rgba[..., 3] = 255
    assert load_image(png_bytes(rgba)).shape == (16, 16, 3)


def test_undecodable_bytes_raise_image_decode_error():
    with pytest.raises(ImageDecodeError):
        load_image(b"this is not an image")
