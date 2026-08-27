
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from app.core.config import CLASS_MAP
# FDI anatomy and chart layout for the tooth diagram the frontend draws.
# quadrant digit -> (arch, patient's side). Permanent dentition only; the FDI model has no
# deciduous classes (5-8), so those quadrants never appear.
_QUADRANTS: dict[int, tuple[str, str]] = {
    1: ("upper", "right"),
    2: ("upper", "left"),
    3: ("lower", "left"),
    4: ("lower", "right"),
}

# position digit -> tooth type. 1-2 incisors, 3 canine, 4-5 premolars, 6-8 molars.
_TOOTH_TYPES: dict[int, str] = {
    1: "incisor", 2: "incisor", 3: "canine",
    4: "premolar", 5: "premolar",
    6: "molar", 7: "molar", 8: "molar",
}

_ANATOMY_BY_FDI: dict[int, str] = { # classes 0,1,3 are tooth restorations
    r["fdi"]: r["name"] for r in CLASS_MAP if r["type"] == "tooth"
}


@dataclass(frozen=True)
class ToothSlot:
    """One position on the chart. 
    Exists whether or not a tooth was detected there."""

    fdi: int
    anatomy: str # something like "upper_left_first_molar"
    quadrant: int
    position: int   # 1 = central incisor .. 8 = third molar
    arch: str   # "upper" | "lower"
    patient_side: str # "right" | "left" — what the FDI number means
    viewer_side: str  # "left" | "right" — where it appears in the image
    tooth_type: str    # "incisor" | "canine" | "premolar" | "molar"

    @property
    def is_third_molar(self) -> bool:
        """Wisdom teeth are routinely absent, so 'missing' here is usually unremarkable."""
        return self.position == 8
    
# Comply with FDI  numbering scheme

def quadrant_of(fdi: int) -> int:
    return fdi // 10


def position_of(fdi: int) -> int:
    return fdi % 10


def arch_of(fdi: int) -> str:
    return _QUADRANTS[quadrant_of(fdi)][0]


def patient_side_of(fdi: int) -> str:
    """The side the FDI number refers to — the patient's own left or right."""
    return _QUADRANTS[quadrant_of(fdi)][1]
# TODO: I Think it is still not working, i had better double check in real image boxes 

def viewer_side_of(fdi: int) -> str:
    """Which half of the image the tooth appears in — the radiographic mirror.

    The patient's right is the viewer's left. Anything deriving a side from a box's
    x-coordinate must go through this, not assume left-of-image means "left".
    """
    return "left" if patient_side_of(fdi) == "right" else "right"


def tooth_type_of(fdi: int) -> str:
    return _TOOTH_TYPES[position_of(fdi)]


def fdi_from_class_name(name: str) -> int | None:
    """`"T26"` -> 26. Returns None for the restoration classes, which carry no FDI number."""
    if len(name) == 3 and name.startswith("T") and name[1:].isdigit():
        
        fdi = int(name[1:])
        
        return fdi if fdi in _ANATOMY_BY_FDI else None
    
    return None


def _slot(fdi: int) -> ToothSlot:
    
    return ToothSlot(
        fdi=fdi,
        anatomy=_ANATOMY_BY_FDI[fdi],
        quadrant=quadrant_of(fdi),
        position=position_of(fdi),
        arch=arch_of(fdi),
        patient_side=patient_side_of(fdi),
        viewer_side=viewer_side_of(fdi),
        tooth_type=tooth_type_of(fdi),
    )

# Viewer order, left to right. Quadrants 1 and 4 come first because the patient's right
# renders on the viewer's left; within a quadrant the third molar is furthest from the
# midline, so positions count down 8..1 on the left half and up 1..8 on the right.
UPPER_ROW: list[int] = [10 + p for p in range(8, 0, -1)] + [20 + p for p in range(1, 9)]
LOWER_ROW: list[int] = [40 + p for p in range(8, 0, -1)] + [30 + p for p in range(1, 9)]
# TODO: I Think it is still not working, i had better double check in real image boxes 
CHART: dict[int, ToothSlot] = {fdi: _slot(fdi) for fdi in UPPER_ROW + LOWER_ROW}
#  this is the critical part , complying with FDI numbering scheme

def chart_rows() -> tuple[list[ToothSlot], list[ToothSlot]]:
    """(upper, lower), each already in viewer order — draw them as given."""
    return ([CHART[f] for f in UPPER_ROW], [CHART[f] for f in LOWER_ROW])


def annotate(
    detected_fdi: Iterable[int],
    findings_by_fdi: dict[int, list[str]] | None = None,
    ambiguous_fdi: Iterable[int] = (),
) -> list[dict[str, Any]]:
    """Merge one analysis onto the static chart, in viewer order.

    Everything the diagram needs per position: the anatomy, whether a tooth was detected
    there, what was found on it, and whether its number is contested. A slot that is
    `present: False` is a tooth the FDI model did not find — which for anything but a third
    molar usually means it is missing, and is worth rendering differently from a healthy one.
    """
    detected = set(detected_fdi)
    findings = findings_by_fdi or {}
    ambiguous = set(ambiguous_fdi)

    return [
        {
            "fdi": slot.fdi,
            "anatomy": slot.anatomy,
            "arch": slot.arch,
            "quadrant": slot.quadrant,
            "position": slot.position,
            "tooth_type": slot.tooth_type,
            "viewer_side": slot.viewer_side,
            "patient_side": slot.patient_side,
            "present": slot.fdi in detected,
            "findings": findings.get(slot.fdi, []),
            "ambiguous": slot.fdi in ambiguous,
            "is_third_molar": slot.is_third_molar,
        }
        for slot in (CHART[f] for f in UPPER_ROW + LOWER_ROW)
    ]
