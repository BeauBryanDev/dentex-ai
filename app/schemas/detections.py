
from __future__ import annotations

from pydantic import BaseModel, Field

from app.services.analysis_service import RestorationEntry, ToothEntry
from app.services.fusion import Finding
# Wire format for detections. Pydantic lives here only 
# # to validate the wire format, not to generate it.

class BoundingBox(BaseModel):
    """Pixel coordinates in the ORIGINAL uploaded image, not the 640x640 model space."""
    x1: float
    y1: float
    x2: float
    y2: float

    @classmethod
    def from_tuple(cls, 
                   box: tuple[float, float, float, float]
                   ) -> "BoundingBox":
        
        return cls(
                   x1=box[0], 
                   y1=box[1],
                   x2=box[2], 
                   y2=box[3]
                   )


class ToothOut(BaseModel):
    
    fdi: int = Field(description="FDI number, e.g. 26. Quadrants 1/4 are the PATIENT's right, "
                                 "which renders on the viewer's LEFT half of the image.")
    anatomy: str = Field(description="e.g. upper_left_first_molar")
    confidence: float
    box: BoundingBox

    @classmethod
    def from_entry(cls, t: ToothEntry) -> "ToothOut":
        
        return cls(
                   fdi=t.fdi, 
                   anatomy=t.anatomy, 
                   confidence=t.confidence,
                   box=BoundingBox.from_tuple(t.box)
                   )


class RestorationOut(BaseModel):
    
    kind: str = Field(description="Crown, Bridge or Implant")
    confidence: float
    box: BoundingBox

    @classmethod
    def from_entry(cls, r: RestorationEntry) -> "RestorationOut":
        
        return cls(
                   kind=r.kind, 
                   confidence=r.confidence, 
                   box=BoundingBox.from_tuple(r.box)
                   )


class FindingOut(BaseModel):
    """A lesion, optionally attributed to a tooth."""

    label: str = Field(description="Cavities, Damage, Infection or Wisdom. "
                                   "'Damage' denotes a missing tooth.")
    confidence: float
    box: BoundingBox
    
    tooth_fdi: int | None = Field(
        default=None,
        description="null when no tooth sufficiently contains the lesion — expected for "
                    "'Damage', since a missing tooth has no box to sit inside.",
    )
    tooth_anatomy: str | None = None
    
    containment: float = Field(
        description="Fraction of the lesion inside the assigned tooth. This is the evidence "
                    "for the attribution, not an IoU."
    )

    @classmethod
    def from_finding(cls, f: Finding) -> "FindingOut":
        
        return cls(
                label=f.lesion_label,
                confidence=f.lesion_score,
                box=BoundingBox.from_tuple(f.box),
                tooth_fdi=f.tooth_fdi,
                tooth_anatomy=f.tooth_anatomy,
                containment=f.containment,
        )
