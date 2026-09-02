"""Spend ceilings, all checked before the call that would spend."""
from __future__ import annotations

import pytest

from app.core.budget import BudgetExceeded, Spend


def test_process_ceiling_blocks_every_session(budget):
    budget.record(Spend(), 3000, 2000)
    with pytest.raises(BudgetExceeded, match="process token budget"):
        budget.check(Spend())


def test_session_turn_ceiling_is_enforced(budget):
    with pytest.raises(BudgetExceeded, match="turn limit"):
        budget.check(Spend(turns=3))


def test_session_token_ceiling_is_enforced(budget):
    with pytest.raises(BudgetExceeded, match="session token budget"):
        budget.check(Spend(input_tokens=900, output_tokens=100))


