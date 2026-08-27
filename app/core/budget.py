
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Rough list prices for claude-sonnet-5, $/1M tokens.
USD_PER_MTOK_IN = 3.0
USD_PER_MTOK_OUT = 15.0


class BudgetExceeded(Exception):
    """Raised by the guard; the orchestrator turns this into an AgentError."""


@dataclass
class Spend:
    input_tokens: int = 0
    output_tokens: int = 0
    turns: int = 0

    @property
    def estimated_usd(self) -> float:
        return (
            self.input_tokens / 1e6 * USD_PER_MTOK_IN
            + self.output_tokens / 1e6 * USD_PER_MTOK_OUT
        )


class BudgetGuard:
    """Process-wide spend tracker. One instance on `app.state`."""

    def __init__(
        self,
        session_token_budget: int,
        process_token_budget: int,
        max_turns_per_session: int,
    ) -> None:
        self.session_token_budget = session_token_budget
        self.process_token_budget = process_token_budget
        self.max_turns_per_session = max_turns_per_session
        self.total = Spend()
        self._lock = threading.Lock()


    def check(self, session_spend: Spend) -> None:
        """
        Called before a turn. Raises `BudgetExceeded` rather than letting it run.

        Checked up front, not after: the point is to refuse the request that would spend
        the money, and a post-hoc check has already paid for the call it is complaining about.
        """
        with self._lock:
            
            total_tokens = self.total.input_tokens + self.total.output_tokens
            
            if total_tokens >= self.process_token_budget:
                
                raise BudgetExceeded(
                    
                    f"process token budget exhausted: {total_tokens:,} >= "
                    f"{self.process_token_budget:,} (~${self.total.estimated_usd:.2f}). "
                    "Restart the backend to reset."
                )

        if session_spend.turns >= self.max_turns_per_session:
            raise BudgetExceeded(
                f"session turn limit reached: {session_spend.turns} >= "
                f"{self.max_turns_per_session}. Start a new consultation."
            )

        session_tokens = session_spend.input_tokens + session_spend.output_tokens
        if session_tokens >= self.session_token_budget:
            raise BudgetExceeded(
                f"session token budget exhausted: {session_tokens:,} >= "
                f"{self.session_token_budget:,}. Start a new consultation."
            )


    def record(self, session_spend: Spend, input_tokens: int, output_tokens: int) -> None:
        """Fold one API response's usage into both the session and process totals."""
        session_spend.input_tokens += input_tokens
        session_spend.output_tokens += output_tokens
        with self._lock:
            self.total.input_tokens += input_tokens
            self.total.output_tokens += output_tokens


    def record_turn(self, session_spend: Spend) -> None:
        
        session_spend.turns += 1
        
        with self._lock:
            
            self.total.turns += 1
            
            logger.info(
                "spend: process %s turns, in=%s out=%s (~$%.3f) | session in=%s out=%s",
                self.total.turns,
                f"{self.total.input_tokens:,}",
                f"{self.total.output_tokens:,}",
                self.total.estimated_usd,
                f"{session_spend.input_tokens:,}",
                f"{session_spend.output_tokens:,}",
            )
