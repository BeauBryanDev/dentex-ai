"""Chat wire format includes structured dental office listings."""
from __future__ import annotations

from app.agent.orchestrator import AgentReply, ToolCallRecord
from app.schemas.chat import ChatResponse
from app.tools.get_dental_offices import DentalOffice


def test_chat_response_includes_dental_office_map_links():
    office = DentalOffice(
        name="Smile Clinic",
        address="12 Rue Example",
        rating=4.5,
        user_ratings_total=12,
        open_now=True,
        maps_url="https://maps.example/dentist-1",
    )
    reply = AgentReply(
        session_id="s1",
        text="Here are two clinics near Lyon.",
        tool_calls=[
            ToolCallRecord(
                name="find_dental_offices_nearby",
                query="Lyon, France",
                result_count=1,
                resolved_location="Lyon, France",
                dental_offices=(office,),
            )
        ],
    )

    payload = ChatResponse.from_reply(reply).model_dump()
    offices = payload["tool_calls"][0]["dental_offices"]
    assert offices[0]["name"] == "Smile Clinic"
    assert offices[0]["maps_url"] == "https://maps.example/dentist-1"
    assert payload["tool_calls"][0]["resolved_location"] == "Lyon, France"
