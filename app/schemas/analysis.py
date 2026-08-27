
from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.detections import FindingOut, RestorationOut, ToothOut
from app.services.analysis_service import AnalysisResult

#version of the model that is used for the UI

class AnalyzeResponse(BaseModel):
    session_id: str = Field(
        description="Send this back on POST /chat. It is how the conversation finds this "
                    "analysis — the agent is handed the findings, it never asks for them."
    )
    image_width: int
    image_height: int
    teeth: list[ToothOut]
    restorations: list[RestorationOut]
    findings: list[FindingOut]
    ambiguous_fdi: list[int] = Field(
        default_factory=list,
        description="FDI numbers claimed by more than one tooth box. Reported rather than "
                    "silently resolved. Only worth surfacing to the user when a finding's "
                    "tooth_fdi appears in this list; otherwise it concerns a tooth with no "
                    "finding on it.",
    )
    summary: str = Field(description="Compact text form, the grounding block for the agent.")

    @classmethod
    def from_result(cls, 
                    r: AnalysisResult, 
                    session_id: str
                    ) -> "AnalyzeResponse":
        
        return cls(
            
            session_id=session_id,
            image_width=r.image_width,
            image_height=r.image_height,
            teeth=[ToothOut.from_entry(t) for t in r.teeth],
            restorations=[RestorationOut.from_entry(x) for x in r.restorations],
            findings=[FindingOut.from_finding(f) for f in r.findings],
            ambiguous_fdi=r.ambiguous_fdi,
            summary=r.summary(),
            
        )


class HealthResponse(BaseModel):
    
    status: str = Field(description="'ok' once every model and index is resident in app.state")
    lesion_model: bool
    fdi_model: bool
    faiss_index: bool
    embedding_model: bool
