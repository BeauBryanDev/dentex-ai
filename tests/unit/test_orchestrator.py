"""One agent turn, driven by a scripted client. No network."""
from __future__ import annotations

import pytest

from app.agent.orchestrator import prune_tool_results, run_turn
from app.agent.tool_schema import DENTAL_OFFICE_TOOL_NAME, SEARCH_TOOL_NAME
from app.tools.get_dental_offices import DentalOffice, DentalOfficeSearchResult
from app.core.budget import BudgetGuard, Spend
from app.core.exception import AgentBudgetError, AgentRefusalError
from app.core.session_store import SessionStore
from tests.unit.conftest import (
    FakeAnthropicClient,
    fake_response,
    text_block,
    tool_use_block,
)


def new_session(analysis=None):
    store = SessionStore()
    session = store.create()
    session.analysis = analysis
    return session


def test_a_plain_turn_returns_the_reply_and_its_usage(test_settings, fake_retriever):
    client = FakeAnthropicClient([fake_response([text_block("Caries on 26.")])])
    reply = run_turn(
        new_session({"findings": []}),
        "what do you see",
        client=client,
        retriever=fake_retriever,
        settings=test_settings,
    )
    assert reply.text == "Caries on 26."
    assert reply.tool_calls == []
    assert (reply.input_tokens, reply.output_tokens) == (100, 20)
    assert reply.grounded_in_analysis is True


def test_a_tool_turn_retrieves_and_answers(test_settings, fake_retriever):
    client = FakeAnthropicClient(
        [
            fake_response(
                [tool_use_block("tu_1", SEARCH_TOOL_NAME, {"query": "caries management"})],
                stop_reason="tool_use",
            ),
            fake_response([text_block("Selective removal, per Garg.")]),
        ]
    )
    session = new_session({"findings": []})
    reply = run_turn(
        session,
        "how do I manage this",
        client=client,
        retriever=fake_retriever,
        settings=test_settings,
    )
    assert fake_retriever.queries == ["caries management"]
    assert [t.name for t in reply.tool_calls] == [SEARCH_TOOL_NAME]
    assert reply.tool_calls[0].result_count == 1
    assert reply.input_tokens == 200


def test_tool_results_go_back_in_one_message_paired_to_their_tool_use(
    test_settings, fake_retriever
):
    client = FakeAnthropicClient(
        [
            fake_response(
                [
                    tool_use_block("tu_1", SEARCH_TOOL_NAME, {"query": "first"}),
                    tool_use_block("tu_2", SEARCH_TOOL_NAME, {"query": "second"}),
                ],
                stop_reason="tool_use",
            ),
            fake_response([text_block("done")]),
        ]
    )
    session = new_session()
    run_turn(
        session,
        "two questions",
        client=client,
        retriever=fake_retriever,
        settings=test_settings,
    )
    results = session.messages[-2]["content"]
    assert [b["tool_use_id"] for b in results] == ["tu_1", "tu_2"]
    assert all(b["type"] == "tool_result" for b in results)


def test_a_refusal_is_raised_before_content_is_read(test_settings, fake_retriever):
    client = FakeAnthropicClient([fake_response([], stop_reason="refusal")])
    with pytest.raises(AgentRefusalError):
        run_turn(
            new_session(),
            "something declined",
            client=client,
            retriever=fake_retriever,
            settings=test_settings,
        )


def test_the_budget_is_checked_before_any_request_is_sent(test_settings, fake_retriever):
    guard = BudgetGuard(1000, 5000, 3)
    session = new_session()
    session.spend = Spend(turns=3)
    client = FakeAnthropicClient([])
    with pytest.raises(AgentBudgetError):
        run_turn(
            session,
            "one more",
            client=client,
            retriever=fake_retriever,
            settings=test_settings,
            budget=guard,
        )
    assert client.messages.calls == []


def test_a_dental_office_turn_searches_near_the_users_city(test_settings, fake_retriever, monkeypatch):
    offices = (
        DentalOffice(
            name="Smile Clinic",
            address="12 Rue Example",
            rating=4.5,
            user_ratings_total=12,
            open_now=True,
            maps_url="https://maps.example/dentist-1",
        ),
    )
    monkeypatch.setattr(
        "app.agent.orchestrator.search_dental_offices_near_city",
        lambda city, **kwargs: DentalOfficeSearchResult(
            text=f"offices near {city}",
            office_count=len(offices),
            resolved_location=city,
            offices=offices,
        ),
    )
    client = FakeAnthropicClient(
        [
            fake_response(
                [
                    tool_use_block(
                        "tu_1",
                        DENTAL_OFFICE_TOOL_NAME,
                        {"city": "Lyon", "region_hint": "France"},
                    )
                ],
                stop_reason="tool_use",
            ),
            fake_response([text_block("Here are two clinics in Lyon.")]),
        ]
    )
    settings = test_settings.model_copy(update={"google_maps_api_key": "test-key"})
    reply = run_turn(
        new_session(),
        "find me a dentist",
        client=client,
        retriever=fake_retriever,
        settings=settings,
    )
    assert [t.name for t in reply.tool_calls] == [DENTAL_OFFICE_TOOL_NAME]
    assert reply.tool_calls[0].query == "Lyon, France"
    assert reply.tool_calls[0].result_count == 1
    assert reply.tool_calls[0].resolved_location == "Lyon"
    assert len(reply.tool_calls[0].dental_offices) == 1
    assert reply.tool_calls[0].dental_offices[0].maps_url == "https://maps.example/dentist-1"


def test_prune_stubs_older_retrievals_but_keeps_their_blocks():
    messages = [
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "a", "content": "old"}]},
        {"role": "assistant", "content": "answer"},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "b", "content": "new"}]},
    ]
    prune_tool_results(messages, keep_full=1)
    assert messages[0]["content"][0]["content"] != "old"
    assert messages[0]["content"][0]["tool_use_id"] == "a"
    assert messages[2]["content"][0]["content"] == "new"
