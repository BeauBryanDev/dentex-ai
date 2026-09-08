
from __future__ import annotations

from pydantic import BaseModel, Field

from app.agent.orchestrator import AgentReply

# Wire format for POST /chat. Pydantic lives here only 
# # to validate the wire format, not to generate it.

class ChatRequest(BaseModel):
    
    message: str = Field(
        min_length=1,
        max_length=8000,
        description="The dentist's message. Bounded because every turn resends the whole "
                    "history — an unbounded message inflates this turn and every one after it.",
    )
    session_id: str | None = Field(
        default=None,
        description="From a previous /analyze or /chat response. Omit to start a new "
                    "conversation. An unknown or expired id transparently starts a new one "
                    "rather than failing — but its analysis is gone, so the reply will ask "
                    "for an upload.",
    )


class DentalOfficeOut(BaseModel):
    """One dental practice from a nearby search."""

    name: str
    address: str
    rating: float | None = None
    user_ratings_total: int | None = None
    open_now: bool | None = None
    maps_url: str | None = Field(
        default=None,
        description="Google Maps link for this practice.",
    )


class ToolCallOut(BaseModel):
    """A tool the agent invoked while answering."""

    name: str
    query: str = Field(description="The query Claude wrote, not the dentist's wording.")
    result_count: int = Field(
        description="Passages or offices returned. 0 means nothing matched."
    )
    resolved_location: str | None = Field(
        default=None,
        description="Geocoded town or city for a dental office search.",
    )
    dental_offices: list[DentalOfficeOut] = Field(
        default_factory=list,
        description="Structured office listings when name is find_dental_offices_nearby.",
    )


class ChatResponse(BaseModel):
    session_id: str = Field(description="Send this back on the next turn.")
    reply: str
    grounded_in_analysis: bool = Field(
        description="False when no X-ray is attached to this session — the reply is general "
                    "dental knowledge, not a reading of this patient's imaging."
    )
    tool_calls: list[ToolCallOut] = Field(
        default_factory=list,
        description="Empty when the agent answered without consulting the corpus. Surface "
                    "these so the dentist can see what a clinical claim was grounded in.",
    )
    input_tokens: int = 0
    output_tokens: int = 0

    @classmethod
    def from_reply(cls, reply: AgentReply) -> "ChatResponse":
        # The reply is a single turn, so the session_id is the same as the request_id.
        return cls(
            
            session_id=reply.session_id,
            reply=reply.text,
            grounded_in_analysis=reply.grounded_in_analysis,
            tool_calls=[
                
                ToolCallOut(
                    name=t.name,
                    query=t.query,
                    result_count=t.result_count,
                    resolved_location=t.resolved_location,
                    dental_offices=[
                        DentalOfficeOut(
                            name=o.name,
                            address=o.address,
                            rating=o.rating,
                            user_ratings_total=o.user_ratings_total,
                            open_now=o.open_now,
                            maps_url=o.maps_url,
                        )
                        for o in t.dental_offices
                    ],
                ) # dental_offices is a list of DentalOfficeOut
                for t in reply.tool_calls
            ],
            
            input_tokens=reply.input_tokens,
            output_tokens=reply.output_tokens,
            
        )
