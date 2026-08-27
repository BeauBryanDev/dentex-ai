
from __future__ import annotations

import cv2
import numpy as np
"""Decoding uploaded X-ray bytes into the BGR uint8 array the rest of the pipeline assumes."""
# Re-exported so callers can keep importing it from here, but defined in core/exception.py
# so it inherits the app-wide status code and is caught by the one global handler.
from app.core.exception import ImageDecodeError

__all__ = ["ImageDecodeError", "load_image"]


def load_image(data: bytes) -> np.ndarray:
    """
    Decode image bytes to a 3-channel BGR uint8 array.

    Dental X-rays are frequently single-channel: several files in images2test/ decode to
    shape (H, W) with no channel axis at all. The ONNX graph has a fixed [1, 3, 640, 640]
    input, so every path here has to end at 3 channels. 16-bit PNGs (common for raw
    radiographs) are scaled down to 8-bit rather than truncated.
    """
    buf = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(buf, cv2.IMREAD_UNCHANGED)
    
    if img is None:
        
        raise ImageDecodeError("bytes are not a decodable image")

    if img.dtype == np.uint16:
        
        img = cv2.convertScaleAbs(img, alpha=255.0 / 65535.0)
        
    elif img.dtype != np.uint8:
        
        img = cv2.normalize(img, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)

    if img.ndim == 2:                       # grayscale radiograph
        
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        
    elif img.shape[2] == 4:                 # PNG with alpha
        
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        
    elif img.shape[2] == 1:
        
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

    return np.ascontiguousarray(img)
