
from __future__ import annotations

import numpy as np
import onnxruntime as ort

from app.utils.postprocessing import Detections, decode
from app.utils.preprocessing import Letterbox, prepare

# Running one exported YOLO graph end to end: tensor in, decoded detections out

# The session is always injected, never constructed here. Both ONNX graphs are loaded once in
# core/lifespan.py onto app.state; building an InferenceSession per request would reload ~38 MB
# of weights each time.

class Detector:
    """One model. Call it with a BGR image, or with a pre-built tensor to share preprocessing."""

    def __init__(
        self,
        session: ort.InferenceSession,
        class_names: list[str],
        conf_threshold: float,
        iou_threshold: float,
        imgsz: int = 640,
    ) -> None:
        self.session = session
        self.class_names = class_names
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.imgsz = imgsz
        self._input_name = session.get_inputs()[0].name

    def run_tensor(self, 
                   tensor: np.ndarray, 
                   meta: Letterbox
                   ) -> Detections:
        """
        Infer from an already-letterboxed tensor.

        Split out from  detect  because the lesion and FDI graphs take byte-identical input
        ([1,3,640,640], same letterbox), so analysis_service preprocesses once and feeds both.
        """
        output = self.session.run(None, {self._input_name: tensor})[0]
        
        return decode(
            output, 
            meta, 
            self.class_names, 
            self.conf_threshold, 
            self.iou_threshold
        )

    def detect(self, img: np.ndarray) -> Detections:
        """Full path for a single model: BGR image -> detections in original coordinates."""
        tensor, meta = prepare(img, self.imgsz)
        
        return self.run_tensor(tensor, meta)
