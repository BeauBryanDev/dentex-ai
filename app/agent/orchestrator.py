
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

import anthropic

from app.agent.prompts import build_system_blocks
from app.agent.tool_schema import (
    ADVICE_VIDEO_TOOL_NAME,
    DENTAL_OFFICE_TOOL_NAME,
    ORAL_HEALTH_STATS_TOOL_NAME,
    SEARCH_TOOL_NAME,
    TOOLS,
)
from app.core.budget import BudgetExceeded, BudgetGuard
from app.core.exception import (
    AgentBudgetError,
    AgentError,
    AgentRefusalError,
    translate_anthropic_error,
)
from app.core.logging import log_agent_usage
from app.core.session_store import ChatSession
from app.tools.dentist_advisor import format_advice_videos, get_oral_health_advice
from app.tools.get_dental_offices import DentalOffice, search_dental_offices_near_city
from app.tools.oral_health_stats import format_oral_health_access, get_oral_health_access
from app.tools.rag_tool import run_search

logger = logging.getLogger(__name__)

 
MAX_TOOL_ROUNDS = 2

@dataclass(frozen=True)
class ToolCallRecord:
    """One tool round-trip, kept so the UI can show what was consulted."""

    name: str
    query: str
    result_count: int
    resolved_location: str | None = None
    dental_offices: tuple[DentalOffice, ...] = ()


@dataclass(frozen=True)
class AgentReply:
    """What one `/chat` turn produces."""

    session_id: str
    text: str
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    request_id: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    grounded_in_analysis: bool = False


def _text_of(response: Any) -> str:
    return "".join(b.text for b in response.content if b.type == "text").strip()

# stub is used to replace the text of all but the most recent tool_results.
_STUB = "[earlier retrieval — passages omitted from history to save context]"

# vision models are not a tool claude can call, it is set by default in the backend code.

def _run_tool(
    block: Any,
    *,
    retriever: Any,
    settings: Any,
) -> tuple[str, bool, ToolCallRecord | None]:
    """
    Execute one tool_use block.

    Returns:
        (content, is_error, record) where record is None for unknown tools.
    """
    if block.name == SEARCH_TOOL_NAME:
        
        query = (block.input or {}).get("query", "")
        
        try:
            found = run_search(retriever, query)
            record = ToolCallRecord(SEARCH_TOOL_NAME, 
                                    query, found.hit_count)
            return found.text, False, record
        
        except Exception as exc:  # noqa: BLE001
            logger.exception("retrieval failed for %r", query)
            return f"retrieval failed: {exc}", True, None

    if block.name == DENTAL_OFFICE_TOOL_NAME:
        
        payload = block.input or {}
        city = str(payload.get("city") or "").strip()
        region_hint = payload.get("region_hint")
        region = str(region_hint).strip() if region_hint else None
        label = f"{city}, {region}" if region else city
        
        if not city:
            return (
                "city is required — ask the user which town or city they are in before "
                "searching.",
                True,
                None,
            )
        if not settings.google_maps_api_key:
            
            return (
                "dental office search is unavailable — Google Maps API key is not configured.",
                True,
                None,
            )
            
        try:
            found = search_dental_offices_near_city(
                city,
                api_key=settings.google_maps_api_key,
                region_hint=region,
                radius_m=settings.dental_office_search_radius_m,
                max_results=settings.dental_office_max_results,
            )
            
            record = ToolCallRecord(
                DENTAL_OFFICE_TOOL_NAME,
                label,
                found.office_count,
                resolved_location=found.resolved_location,
                dental_offices=found.offices,
            )
            return found.text, False, record
        
        except Exception as exc:  # noqa: BLE001
            
            logger.exception("dental office search failed for %r", label)
            return f"dental office search failed: {exc}", True, None

    if block.name == ORAL_HEALTH_STATS_TOOL_NAME:

        country = str((block.input or {}).get("country") or "").strip()

        if not country:
            return (
                "country is required — ask the user which country they are asking about "
                "before looking up access data.",
                True,
                None,
            )

        try:
            results = get_oral_health_access(country)
            text, reported = format_oral_health_access(results)
            # A country that resolves but has no indicators on file is not an error —
            # it is a fact the agent must report as "no data", so it comes back as a
            # normal result with a count of 0.
            record = ToolCallRecord(
                ORAL_HEALTH_STATS_TOOL_NAME,
                country,
                reported,
                resolved_location=results.get("iso3"),
            )
            return text, False, record

        except Exception as exc:  # noqa: BLE001
            logger.exception("oral health access lookup failed for %r", country)
            return f"oral health access lookup failed: {exc}", True, None

    if block.name == ADVICE_VIDEO_TOOL_NAME:

        payload = block.input or {}
        query = str(payload.get("query") or "").strip()
        language = str(payload.get("language") or "en").strip().lower()

        if not query:
            return "query is required — say what the video should demonstrate.", True, None

        if not settings.youtube_data_api_key:
            return (
                "advice video search is unavailable — YouTube Data API key is not "
                "configured. Answer from your own knowledge instead.",
                True,
                None,
            )

        try:
            videos = get_oral_health_advice(
                query,
                language,
                api_key=settings.youtube_data_api_key,
                max_results=settings.youtube_max_results,
                search_pool=settings.youtube_search_pool,
            )
            text, count = format_advice_videos(videos, query)
            # Zero trusted matches is a result, not a failure — the agent is told to say
            # so rather than invent a link, so it must not come back as is_error.
            record = ToolCallRecord(ADVICE_VIDEO_TOOL_NAME, query, count)
            return text, False, record

        except Exception as exc:  # noqa: BLE001
            logger.exception("advice video search failed for %r", query)
            return f"advice video search failed: {exc}", True, None

    return f"unknown tool {block.name!r}", True, None


def prune_tool_results(messages: list[dict[str, Any]], 
                       keep_full: int
                       ) -> None:
    """
    Replace the text of all but the most recent `keep_full` tool_results with a stub.

    A retrieval costs ~1800 tokens of passages, and because the tool_result stays in the
    history that cost is re-paid on every later turn of the session — the single largest
    growth term in a long consultation. Once Claude has read the passages and written its
    answer, the answer is in the history; the raw passages are not needed again.

    """
    tool_result_msgs = [
        m for m in messages
        if  m.get("role") == "user" and isinstance(m.get("content"), list) 
        # The tool_result is a block in the content list, not the whole content.
        and any(isinstance(b, dict) and b.get("type") == "tool_result" for b in m["content"])
    ] 
    for msg in tool_result_msgs[:-keep_full] if keep_full else tool_result_msgs:
        
        for block in msg["content"]:
            
            if isinstance(block, dict) and block.get("type") == "tool_result":
                
                if block.get("content") != _STUB:
                    
                    block["content"] = _STUB


def set_message_cache_breakpoint(messages: list[dict[str, Any]]) -> None:
    """
    Move the conversation's cache breakpoint to the end of the history.

    Caching is a prefix match over tools -> system -> messages, so a breakpoint on the last
    block lets the whole conversation so far be re-read instead of re-prefilled: on turn 2
    onward, and on the second call of a tool turn, which is the one the user waits through
    twice.
    """
    for msg in messages:
        content = msg.get("content")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    block.pop("cache_control", None)

    if not messages:
        return

    last = messages[-1]
    content = last.get("content")

    # A plain user message is a bare string; it has to become a block to carry the marker.
    if isinstance(content, str):
        last["content"] = [
            {
                "type": "text", 
                "text": content, 
             "cache_control": {"type": "ephemeral"}
             }
        ]
        return

    if isinstance(content, list) and content and isinstance(content[-1], dict):
        content[-1]["cache_control"] = {"type": "ephemeral"}


def run_turn(
    session: ChatSession,
    user_message: str,
    *,
    client: anthropic.Anthropic,
    retriever: Any,
    settings: Any,
    budget: BudgetGuard | None = None,
) -> AgentReply:
    """
    Run one conversational turn to completion and return the assistant's reply.
    client and retriever are injected from `app.state` rather than constructed here, so
    one connection pool and one loaded PubMedBERT are shared across requests.
    """
    # Checked before anything is sent: a guard that fires after the call has already spent
    # the money it exists to prevent.
    if budget is not None:
        
        try:
            
            budget.check(session.spend)
            
        except BudgetExceeded as exc:
            
            raise AgentBudgetError(str(exc)) from exc

    system = build_system_blocks(session.analysis)
    
    prune_tool_results(session.messages, settings.keep_full_tool_results)
    
    session.messages.append({"role": "user", "content": user_message})

    tool_calls: list[ToolCallRecord] = []
    in_tokens = out_tokens = 0
    request_id: str | None = None
    # Wall clock across every model call in this turn — what the user actually waited.
    # A tool turn spends it in two calls, so the per-call numbers alone understate it.
    turn_elapsed = 0.0

    for _ in range(MAX_TOOL_ROUNDS):

        # After prune_tool_results, so the marker never lands on a block that is about to
        # be stubbed — rewriting a cached block invalidates everything behind it.
        set_message_cache_breakpoint(session.messages)

        call_started = time.perf_counter()

        try:
            response = client.messages.create(
                
                model=settings.anthropic_model,
                max_tokens=settings.llm_max_tokens,
                system=system,
                messages=session.messages,
                tools=TOOLS,
                # Sent explicitly rather than omitted: omitting `thinking` on
                # claude-sonnet-5 runs adaptive thinking anyway, so there was no way to
                # turn it down from config.
                thinking=(
                    {"type": "adaptive"}
                    if settings.llm_thinking_enabled
                    else {"type": "disabled"}
                ),
                output_config={"effort": settings.llm_effort},
            )
            
        except Exception as exc:  
            
            raise translate_anthropic_error(exc) from exc


        call_elapsed = time.perf_counter() - call_started
        turn_elapsed += call_elapsed

        log_agent_usage(logger,
                        response,
                        model=settings.anthropic_model,
                        elapsed_s=call_elapsed,
                        )
            
        request_id = getattr(response, "_request_id", None)
        in_tokens += response.usage.input_tokens
        out_tokens += response.usage.output_tokens
        
        if budget is not None:
            
            budget.record(
                session.spend, 
                response.usage.input_tokens, 
                response.usage.output_tokens
            )

        # Check stop_reason before touching content: a refusal is an HTTP 200 whose content
        # is empty or partial, so indexing into it here would raise instead of reporting
        # what actually happened.
        if response.stop_reason == "refusal":
            
            raise AgentRefusalError(
                
                "Claude declined this request",
                request_id=request_id,
                category=getattr(getattr(response, 
                                         "stop_details", 
                                         None),
                                 "category", 
                                 None
                                 ),
            )

        # The full content list goes back, not just the text — dropping the tool_use blocks
        # would break the tool_use/tool_result pairing on the next request.
        session.messages.append({"role": "assistant", 
                                 "content": response.content})

        if response.stop_reason != "tool_use":
            
            if budget is not None:

                budget.record_turn(session.spend)

            logger.info(
                "turn done session=%s calls=%s tools=%s in=%s out=%s took=%.2fs",
                session.session_id,
                len(tool_calls) + 1,
                [t.name for t in tool_calls],
                in_tokens,
                out_tokens,
                turn_elapsed,
            )

            return AgentReply(
                
                session_id=session.session_id,
                text=_text_of(response),
                tool_calls=tool_calls,
                request_id=request_id,
                input_tokens=in_tokens,
                output_tokens=out_tokens,
                grounded_in_analysis=session.has_analysis,
            )

        # Every tool_use block must get a tool_result, and they all go back in ONE user
        # message — splitting them across messages teaches the model to stop batching.
        results = []
        
        for block in response.content:
            
            if block.type != "tool_use":
                continue

            content, is_error, record = _run_tool(
                block,
                retriever=retriever,
                settings=settings,
            )
            if record is not None:
                tool_calls.append(record)

            results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": content,
                "is_error": is_error,
            })

        session.messages.append({"role": "user", 
                                 "content": results})

    raise AgentError(
        f"tool loop did not converge after {MAX_TOOL_ROUNDS} rounds",
        request_id=request_id,
    )
