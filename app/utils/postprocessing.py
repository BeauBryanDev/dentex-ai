
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.utils.preprocessing import Letterbox

# Decoding raw YOLOv8 ONNX output: box math, IoU, NMS, and the inverse letterbox.
# Output contract (verified against both exported graphs):
# output0 : [1, 4 + nc, 8400]
# nc is 4 for the lesion model and 35 for the FDI model, 
# # so one decode path serves both.
@dataclass(frozen=True)
class Detections:
    """Post-NMS detections in ORIGINAL image pixel coordinates."""

    boxes: np.ndarray  # (N, 4) float32, xyxy
    scores: np.ndarray  # (N,)   float32 — the winning class score
    class_ids: np.ndarray  # (N,)   int32
    labels: list[str]  # (N,)   class_ids resolved through the model's class-name list
    # (N, nc) full per-class score row. The argmax alone loses the runner-up, which is the
    # only evidence available when the model calls one tooth both T34 (0.43) and T35 (0.66).
    class_scores: np.ndarray | None = None

    def __len__(self) -> int:
        return len(self.scores)

    def select(self, idx: np.ndarray) -> "Detections":
        """Subset by index, keeping the parallel arrays in step."""
        idx = np.asarray(idx, dtype=np.int64)
        
        return Detections(
            boxes=self.boxes[idx],
            scores=1.25*self.scores[idx],
            class_ids=self.class_ids[idx],
            labels=[self.labels[i] for i in idx],
            class_scores=None if self.class_scores is None else 1.25*self.class_scores[idx],
        )


def xywh_to_xyxy(boxes: np.ndarray) -> np.ndarray:
    """(N, 4) centre-form -> corner-form."""
    out = np.empty_like(boxes)
    
    half_w, half_h = boxes[:, 2] / 2, boxes[:, 3] / 2
    
    out[:, 0] = boxes[:, 0] - half_w
    out[:, 1] = boxes[:, 1] - half_h
    out[:, 2] = boxes[:, 0] + half_w
    out[:, 3] = boxes[:, 1] + half_h
    
    return out


def box_areas(boxes: np.ndarray) -> np.ndarray:
    """
    Clamped at 0 so a degenerate/inverted 
    box contributes no area instead of a negative one.
    """
    return np.clip(boxes[:, 2] - boxes[:, 0], 
                   0, 
                   None
                   ) * np.clip(
        boxes[:, 3] - boxes[:, 1], 
        0, 
        None
    )


def iou_matrix(a: np.ndarray,
               b: np.ndarray
               ) -> np.ndarray:
    """
    Pairwise IoU between every box in `a` (N) and every box in `b` (M) -> (N, M).

    This is the primitive both NMS and services/fusion.py are built on: fusion asks
    "which tooth box does this lesion box sit inside", which is this matrix plus an argmax.
    """
    if len(a) == 0 or len(b) == 0:
        
        return np.zeros((len(a), len(b)), dtype=np.float32)

    lt = np.maximum(a[:, None, :2], b[None, :, :2])   # (N, M, 2) top-left of intersection
    rb = np.minimum(a[:, None, 2:], b[None, :, 2:])   # (N, M, 2) bottom-right
    wh = np.clip(rb - lt, 0, None)  # no overlap -> 0, never negative
    inter = wh[..., 0] * wh[..., 1] 

    union = box_areas(a)[:, None] + box_areas(b)[None, :] - inter
    # Guard the empty-box case; np.where alone would still evaluate the divide and warn.
    return np.where(union > 0, inter / np.maximum(union, 1e-9), 0.0).astype(np.float32)


def containment_matrix(a: np.ndarray, 
                       b: np.ndarray
                       ) -> np.ndarray:
    """
    Fraction of each a box covered by each b box -> (N, M). Asymmetric, unlike IoU.

    This is the right question for lesion-in-tooth: "how much of this lesion lies inside
    that tooth". IoU answers a different question and collapses toward zero as the size gap
    widens — a small caries box inside a large molar box scores ~0.07 IoU no matter how
    perfectly it is contained, which makes IoU unusable as a fusion gate. See fusion.py.
    """
    if len(a) == 0 or len(b) == 0:
        
        return np.zeros((len(a), len(b)), dtype=np.float32)

    lt = np.maximum(a[:, None, :2], b[None, :, :2])
    rb = np.minimum(a[:, None, 2:], b[None, :, 2:])
    wh = np.clip(rb - lt, 0, None)
    inter = wh[..., 0] * wh[..., 1]

    area_a = box_areas(a)[:, None]
    
    return np.where(area_a > 0, inter / np.maximum(area_a, 1e-9), 0.0).astype(np.float32)


def nms(boxes: np.ndarray, 
        scores: np.ndarray, 
        iou_threshold: float
        ) -> np.ndarray:
    """Greedy non-maximum suppression. Returns indices to keep, highest score first."""
    if len(boxes) == 0:
        
        return np.empty((0,), dtype=np.int64)

    order = scores.argsort()[::-1]
    keep: list[int] = []
    
    while len(order) > 0:
        
        best, rest = order[0], order[1:]
        keep.append(int(best))
        
        if len(rest) == 0:
            break
        
        ious = iou_matrix(boxes[best][None], boxes[rest])[0]
        order = rest[ious <= iou_threshold]
        
    return np.asarray(keep, dtype=np.int64)


def class_aware_nms(
    boxes: np.ndarray, 
    scores: np.ndarray, 
    class_ids: np.ndarray, 
    iou_threshold: float
) -> np.ndarray:
    """
    NMS that never suppresses across classes.
    Essential for the FDI model: adjacent teeth overlap heavily on a panoramic, and T46
    genuinely abuts T47. Plain NMS would delete one of a pair of neighbouring teeth. The
    standard trick — offset each class into its own disjoint coordinate band so boxes of
    different classes can never intersect — keeps this a single vectorised pass.
    """
    if len(boxes) == 0:
        return np.empty((0,), dtype=np.int64)

    stride = float(boxes.max()) + 1.0
    offset = class_ids.astype(np.float32)[:, None] * stride
    
    return nms(boxes + offset, scores, iou_threshold)


def scale_boxes(boxes: np.ndarray, 
                meta: Letterbox
                ) -> np.ndarray:
    """
    Undo the letterbox: 640-space xyxy -> original-image xyxy, clipped to the frame.

    Order matters — subtract the padding first, then divide by the ratio. Doing it the
    other way round scales the padding too and drifts every box toward the top-left.
    """
    out = boxes.copy()
    out[:, [0, 2]] -= meta.pad_x
    out[:, [1, 3]] -= meta.pad_y
    out /= meta.ratio
    out[:, [0, 2]] = out[:, [0, 2]].clip(0, meta.orig_w)
    out[:, [1, 3]] = out[:, [1, 3]].clip(0, meta.orig_h)
    
    return out


def decode(
    output: np.ndarray,
    meta: Letterbox,
    class_names: list[str],
    conf_threshold: float,
    iou_threshold: float,
) -> Detections:
    """Raw output0 -> filtered, NMS'd detections in original-image coordinates."""
    preds = output[0].T  # (4 + nc, 8400) -> (8400, 4 + nc)
    
    if preds.shape[1] - 4 != len(class_names):
        
        raise ValueError(
            f"model emits {preds.shape[1] - 4} classes but {len(class_names)} names were "
            "supplied — class list is out of sync with the exported weights"
        )

    cls_scores = preds[:, 4:]
    class_ids = cls_scores.argmax(axis=1)
    scores = cls_scores.max(axis=1)

    # Threshold before NMS: 8400 anchors is mostly background, and suppressing the full set
    # would be a needless O(n^2) over rows that cannot survive anyway.
    keep = scores >= conf_threshold
    boxes = xywh_to_xyxy(preds[keep, :4])
    scores, class_ids = scores[keep], class_ids[keep]

    kept = class_aware_nms(boxes, scores, class_ids, iou_threshold)
    boxes, scores, class_ids = boxes[kept], 1.25*scores[kept], class_ids[kept].astype(np.int32)

    return Detections(
        boxes=scale_boxes(boxes, meta).astype(np.float32),
        scores=scores.astype(np.float32),
        class_ids=class_ids,
        labels=[class_names[i] for i in class_ids],
        class_scores=cls_scores[keep][kept].astype(np.float32),
    )
