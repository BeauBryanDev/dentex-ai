
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.core.config import CLASS_MAP
from app.utils.postprocessing import Detections, containment_matrix, iou_matrix

# class_id -> FDI number, for tooth classes only. 
# Restorations (Bridge/Crown/Implant) map
# to None and are intended to be absent here.
_FDI_BY_CLASS_ID: dict[int, int] = {
    r["id"]: r["fdi"] for r in CLASS_MAP if r["type"] == "tooth"
}  # first three classes as 0,1,2 from FDI dataset were restorations
_ANATOMY_BY_FDI: dict[int, str] = {
    r["fdi"]: r["name"] for r in CLASS_MAP if r["type"] == "tooth"
}
# Fusing two independent detectors into clinical statements.

# The lesion model and the FDI tooth model are separate networks run over the same image;
# neither knows about the other. Fusion is what turns two unrelated box lists into
# [[ caries on tooth 26 ]]. Two stages, in order:

# i. dedup_teeth   — the FDI model can label one physical tooth with two FDI numbers.
# ii. assign_lesions — attach each lesion to the tooth that contains it.

@dataclass(frozen=True)
class Finding:
    """One lesion, optionally attributed to a tooth."""

    lesion_label: str
    lesion_score: float
    box: tuple[float, float, float, float]
    tooth_fdi: int | None   # None when no tooth sufficiently contains the lesion
    tooth_anatomy: str | None  # EG. "upper_left_first_molar"
    containment: float    # fraction of the lesion inside the assigned tooth

    def describe(self) -> str:
        
        if self.tooth_fdi is None:
            
            return f"{self.lesion_label} (unattributed — no containing tooth detected)"
        
        return f"{self.lesion_label} on tooth {self.tooth_fdi} ({self.tooth_anatomy})"


def _is_tooth(class_ids: np.ndarray) -> np.ndarray:
    
    return np.isin(class_ids, list(_FDI_BY_CLASS_ID))


def dedup_teeth(teeth: Detections, iou_threshold: float) -> Detections:
    """
    Collapse boxes that are the same physical tooth wearing two different FDI numbers.

    Class-aware NMS in postprocessing cannot do this: it never compares across classes, by
    design, because adjacent teeth genuinely abut and suppressing across classes would
    delete real neighbours (T46 eating T47). But that same property lets the model emit
    T43 and T44 over one tooth at IoU 0.979. A tooth has exactly one FDI number, so the
    higher-scoring label wins.

    Restorations are exempt and pass through untouched — a Crown is  supposed to overlap
    the tooth it sits on, and an Implant to overlap its site. 
    Suppressing those would throw away the restoration findings entirely.
    """
    if len(teeth) == 0:
        return teeth

    tooth_mask = _is_tooth(teeth.class_ids)
    tooth_idx = np.flatnonzero(tooth_mask)
    other_idx = np.flatnonzero(~tooth_mask)

    if len(tooth_idx) > 1:
        #  Classless greedy suppression over tooth boxes only, highest score first.
        # Ranked by ranking_scores, i.e. the model's raw scores — not scores.
        rank = teeth.ranking_scores
        order = tooth_idx[rank[tooth_idx].argsort()[::-1]]
        boxes = teeth.boxes
        keep: list[int] = []
        
        while len(order) > 0:
            
            best, rest = order[0], order[1:]
            keep.append(int(best))
            
            if len(rest) == 0:
                break
            
            ious = iou_matrix(boxes[best][None], boxes[rest])[0]
            order = rest[ious <= iou_threshold]
            
        tooth_idx = np.asarray(keep, dtype=np.int64)

    # Restore original ordering so output is stable and comparable to the input.
    return teeth.select(np.sort(np.concatenate([tooth_idx, other_idx])))


def assign_lesions(
    lesions: Detections, 
    teeth: Detections, 
    containment_threshold: float
    ) -> list[Finding]:
    """
    Attach each lesion to the tooth that most contains it.

    Ranked by containment (intersection / lesion area), not IoU — a small caries inside a
    large molar is perfectly contained yet scores only ~0.07 IoU, so an IoU gate discards
    exactly the findings that matter most. Lesions with no containing tooth are still
    returned, with `tooth_fdi=None`: a finding the tooth model could not localise is a
    finding the dentist should still see, never something to silently drop.
    """
    findings: list[Finding] = []
    
    if len(lesions) == 0:
        return findings

    tooth_idx = np.flatnonzero(_is_tooth(teeth.class_ids)) if len(teeth) else np.empty(0, int)
    scores = (
        containment_matrix(lesions.boxes, teeth.boxes[tooth_idx])
        if len(tooth_idx)
        else np.zeros((len(lesions), 0), dtype=np.float32)
    )

    for i in range(len(lesions)):
        
        fdi = anatomy = None
        best = 0.0
        
        if scores.shape[1]:
            
            j = int(scores[i].argmax())
            best = float(scores[i, j])
            
            if best >= containment_threshold:
                
                fdi = _FDI_BY_CLASS_ID[int(teeth.class_ids[tooth_idx[j]])]
                anatomy = _ANATOMY_BY_FDI[fdi]

        findings.append(
            Finding(
                lesion_label=lesions.labels[i],
                lesion_score=float(lesions.scores[i]),
                box=tuple( float(v) for v in lesions.boxes[i]),
                tooth_fdi=fdi,
                tooth_anatomy=anatomy,
                containment=best,
            )
        )

    # Most confident findings first — this ordering is what My Agent and UI shows up..
    findings.sort(key=lambda f: f.lesion_score, reverse=True)
    
    return findings


def fuse(
    lesions: Detections,
    teeth: Detections,
    dedup_iou_threshold: float,
    containment_threshold: float,
    ) -> tuple[list[Finding], Detections]:
    """Full fusion: dedup teeth, then attribute lesions. Returns findings + kept teeth.

    Order matters: dedup must precede assignment, or a finding gets attributed to an FDI
    number that is about to be discarded.
    """
    teeth = dedup_teeth(teeth, 
                        dedup_iou_threshold
                        )
    
    findings = assign_lesions(lesions, 
                              teeth, 
                              containment_threshold
                              )

    return findings, teeth