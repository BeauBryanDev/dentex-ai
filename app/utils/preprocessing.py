
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

PAD_VALUE = 114  # ultralytics' letterbox fill
# Letterbox + tensor prep. Must reproduce what ultralytics did at export time (imgsz=640).
# The exported graph has a fixed [1, 3, 640, 640] input, so a panoramic X-ray (often ~2:1)
# cannot simply be resized — that would distort tooth geometry and shift every box. It is
# scaled by a single ratio and centre-padded with 114-grey, exactly as ultralytics' LetterBox
# does during preditc.

@dataclass(frozen=True)
class Letterbox:
    """The forward transform, kept so postprocessing can undo it."""

    ratio: float       # uniform scale applied to the original image
    pad_x: int         # pixels of padding added on the LEFT
    pad_y: int         # pixels of padding added on the TOP
    orig_w: int
    orig_h: int
    
# this ithe the manual  way as we do not have Ultralytics locally
# to reproduce the exact same transform

def letterbox(
    img: np.ndarray, 
    imgsz: int = 640, 
    scaleup: bool = True
) -> tuple[np.ndarray, Letterbox]:
    """
    Resize preserving aspect ratio, then centre-pad to a square `imgsz`.

    scaleup=True matches ultralytics' inference default: images smaller than imgsz are
    enlarged. Turning it off would letterbox a small image into a tiny patch of grey and
    starve the detector of resolution.
    """
    h, w = img.shape[:2] # HWC
    r = min(imgsz / h, imgsz / w) # ratio of new/old
    
    if not scaleup:
        r = min(r, 1.0)

    new_w, new_h = round(w * r), round(h * r) # new dimensions
    dw, dh = (imgsz - new_w) / 2, (imgsz - new_h) / 2 # offset to centre

    if (w, h) != (new_w, new_h):
        # INTER_LINEAR on upscale, INTER_AREA on downscale — AREA avoids the aliasing that
        # LINEAR introduces when shrinking a high-resolution radiograph.
        interp = cv2.INTER_LINEAR if r > 1 else cv2.INTER_AREA
        img = cv2.resize(img, (new_w, new_h), interpolation=interp)

    # The -0.1/+0.1 rounding split is ultralytics', reproduced so odd-pixel remainders land
    # on the same side they did at export time.
    top, bottom = round(dh - 0.1), round(dh + 0.1)
    left, right = round(dw - 0.1), round(dw + 0.1)
    
    padded = cv2.copyMakeBorder(
        
        img, top, bottom, left, right, cv2.BORDER_CONSTANT,
        value=(PAD_VALUE, PAD_VALUE, PAD_VALUE),
    )

    return padded, Letterbox(ratio=r, pad_x=left, pad_y=top, orig_w=w, orig_h=h)


def to_tensor(img: np.ndarray) -> np.ndarray:
    """
    BGR HWC uint8 -> RGB NCHW float32 in [0, 1].

    ultralytics applies no mean/std normalisation — only a /255 scale — so neither do we.
    """
    x = img[:, :, ::-1]                       # BGR -> RGB
    x = x.transpose(2, 0, 1)[None]            # HWC -> NCHW
    
    return np.ascontiguousarray(x, dtype=np.float32) / 255.0


def prepare(img: np.ndarray, imgsz: int = 640) -> tuple[np.ndarray, Letterbox]:
    
    """Full path from a decoded BGR image to the model's input tensor."""
    
    padded, meta = letterbox(img, imgsz)
    
    return to_tensor(padded), meta
