
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import anthropic

from app.agent.prompts import build_system_blocks
from app.agent.tool_schema import SEARCH_TOOL_NAME, TOOLS
from app.core.budget import BudgetExceeded, BudgetGuard
from app.core.exception import (
    AgentBudgetError,
    AgentError,
    AgentRefusalError,
    translate_anthropic_error,
)
from app.core.logging import log_agent_usage
from app.core.session_store import ChatSession
from app.tools.rag_tool import run_search

logger = logging.getLogger(__name__)

# A turn that keeps calling the tool is a bug, not deep research. One retrieval is the
# normal case and two is defensible; beyond that the loop is spinning.
MAX_TOOL_ROUNDS = 4
# vision models are not a tool claude can call, it is set by default in the backend code.

@dataclass(frozen=True)
class ToolCallRecord:
    """One retrieval round-trip, kept so the UI can show what was consulted."""

    name: str
    query: str
    result_count: int


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

    for _ in range(MAX_TOOL_ROUNDS):
        
        try:
            response = client.messages.create(
                
                model=settings.anthropic_model,
                max_tokens=settings.agent_max_tokens,
                system=system,
                messages=session.messages,
                tools=TOOLS,
                output_config={"effort": settings.agent_effort},
            )
            
        except Exception as exc:  
            
            raise translate_anthropic_error(exc) from exc


        log_agent_usage(logger, 
                        response,
                        model=settings.anthropic_model
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
        session.messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            
            if budget is not None:
                
                budget.record_turn(session.spend)
                
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
            
            if block.name != SEARCH_TOOL_NAME:
                
                results.append({
                    
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": f"unknown tool {block.name!r}",
                    "is_error": True,
                })
                continue

            query = (block.input or {}).get("query", "")
            
            try:
                
                found = run_search(retriever, query)
                content, is_error = found.text, False
                
                tool_calls.append(
                    ToolCallRecord(SEARCH_TOOL_NAME, 
                                   query, 
                                   found.hit_count
                                   )
                )
                
            except Exception as exc:  # noqa: BLE001
                # A retrieval failure is reported to the model as a failed tool, not raised:
                # it can still answer while saying the corpus was unavailable.
                logger.exception("retrieval failed for %r", query)
                content, is_error = f"retrieval failed: {exc}", True

            results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": content,
                "is_error": is_error,
            })

        session.messages.append({"role": "user", "content": results})

    raise AgentError(
        f"tool loop did not converge after {MAX_TOOL_ROUNDS} rounds",
        request_id=request_id,
    )
