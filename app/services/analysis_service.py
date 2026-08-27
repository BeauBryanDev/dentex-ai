
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

import onnxruntime as ort
# Orchestration: one uploaded X-ray -> the chart and findings the agent reasons over.
from app.core.config import CLASS_MAP, Settings
from app.services.detector import Detector
from app.services.fusion import Finding, fuse
from app.utils.image_utils import load_image
from app.utils.postprocessing import Detections
from app.utils.preprocessing import prepare

# This is the only place the two detectors and fusion meet. Routers call `analyze_image` and
# do no vision work themselves; the agent consumes `AnalysisResult`, never raw boxes.

@dataclass(frozen=True)
class ToothEntry:
    """One tooth on the chart."""

    fdi: int
    anatomy: str
    confidence: float
    box: tuple[float, float, float, float]


@dataclass(frozen=True)
class RestorationEntry:
    """Crown / Bridge / Implant. Carries no FDI number — the model does not assign one.
    """

    kind: str
    confidence: float
    box: tuple[float, float, float, float]


@dataclass(frozen=True)
class AnalysisResult:
    image_width: int
    image_height: int
    teeth: list[ToothEntry]
    restorations: list[RestorationEntry]
    findings: list[Finding]
    # FDI numbers claimed by more than one tooth box. Surfaced, never silently resolved:
    # no IoU test can catch two non-overlapping boxes sharing a number, and the anatomical
    # priors that could (<=8 per quadrant, left-to-right ordering) break on supernumerary and
    # transposed dentition.  
    ambiguous_fdi: list[int] = field(default_factory=list)

    @property
    def attributed(self) -> list[Finding]:
        
        return [f for f in self.findings if f.tooth_fdi is not None]

    def summary(self) -> str:
        
        """Compact text form — the grounding block handed to the agent."""
        
        lines = [
            f"{len(self.teeth)} teeth detected"
            + (f"; restorations: {', '.join(r.kind for r in self.restorations)}"
               if self.restorations else "")
        ]
        for f in self.findings:
            
            lines.append("- " + f.describe())
            
        if self.ambiguous_fdi:
            
            lines.append(
                "- NOTE: FDI numbering is ambiguous for "
                + ", ".join(str(n) for n in self.ambiguous_fdi)
                + " (more than one tooth carries this number)"
            )
            
        return "\n".join(lines)


def _split(teeth: Detections) -> tuple[list[ToothEntry], list[RestorationEntry]]:
    
    fdi_by_id = {r["id"]: r["fdi"] for r in CLASS_MAP if r["type"] == "tooth"}
    anatomy_by_fdi = {r["fdi"]: r["name"] for r in CLASS_MAP if r["type"] == "tooth"}

    chart: list[ToothEntry] = []
    restorations: list[RestorationEntry] = [] # Bridge/Crown/Implant
    
    for i in range(len(teeth)):
        
        box = tuple(float(v) for v in teeth.boxes[i])
        
        conf = float(teeth.scores[i])
        
        fdi = fdi_by_id.get(int(teeth.class_ids[i]))
        
        if fdi is None:
            
            restorations.append(RestorationEntry(teeth.labels[i], conf, box))
            
        else:
            chart.append(ToothEntry(fdi, anatomy_by_fdi[fdi], conf, box))

    chart.sort(key=lambda t: t.fdi)
    
    return chart, restorations


def analyze_image(
    data: bytes,
    lesion_session: ort.InferenceSession,
    fdi_session: ort.InferenceSession,
    settings: Settings,
) -> AnalysisResult:
    """Decode, run both detectors, fuse, and assemble the chart.

    Sessions are passed in from `app.state` (populated in core/lifespan.py) rather than
    created here — see detector.Detector for why that matters.
    """
    img = load_image(data)
    height, width = img.shape[:2]

    # Both graphs take byte-identical input, so letterbox once and feed the same tensor to both
    tensor, meta = prepare(img, settings.inference_imgsz)

    lesion_detector = Detector(
        lesion_session,
        settings.lesion_class_names,
        settings.confidence_threshold,
        settings.iou_threshold,
        settings.inference_imgsz,
    )
    fdi_detector = Detector(
        fdi_session,
        settings.fdi_class_names,
        settings.confidence_threshold,
        settings.iou_threshold,
        settings.inference_imgsz,
    )

    lesions = lesion_detector.run_tensor(tensor, meta)
    raw_teeth = fdi_detector.run_tensor(tensor, meta)

    findings, teeth = fuse(
        lesions,
        raw_teeth,
        settings.tooth_dedup_iou_threshold,
        settings.lesion_containment_threshold,
    )

    chart, restorations = _split(teeth)
    
    ambiguous = sorted(
        
        n for n, c in Counter(t.fdi for t in chart).items() if c > 1
    )

    return AnalysisResult(
        image_width=width,
        image_height=height,
        teeth=chart,
        restorations=restorations,
        findings=findings,
        ambiguous_fdi=ambiguous,
    )
