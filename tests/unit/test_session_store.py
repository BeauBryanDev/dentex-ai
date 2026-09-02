"""In-process session state bridging /analyze and /chat."""
from __future__ import annotations

import time

from app.core.session_store import SessionStore


def test_get_or_create_mints_a_new_session_for_an_unknown_id():
    store = SessionStore()
    session = store.get_or_create("not-a-real-id")
    assert session.session_id != "not-a-real-id"
    assert store.get(session.session_id) is session


def test_expired_sessions_are_purged_on_access():
    store = SessionStore(ttl_seconds=0)
    session = store.create()
    time.sleep(0.01)
    assert store.get(session.session_id) is None


def test_set_analysis_replaces_findings_but_keeps_the_conversation():
    store = SessionStore()
    session = store.create()
    store.append_message(session.session_id, {"role": "user", "content": "hi"})
    store.set_analysis(session.session_id, {"findings": ["first"]})
    store.set_analysis(session.session_id, {"findings": ["second"]})
    assert session.analysis == {"findings": ["second"]}
    assert len(session.messages) == 1
    assert session.has_analysis is True
