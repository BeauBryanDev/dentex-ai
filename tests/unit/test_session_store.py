"""In-process session state bridging /analyze and /chat."""
from __future__ import annotations

import time

from app.agent.prompts import NEW_XRAY_NOTICE
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


def test_second_x_ray_replaces_the_analysis_and_announces_itself():
    """The swap has to be visible in the history.

    Replacing `analysis` alone changed the system block while the transcript still read as
    one unbroken conversation about the first image — so the agent kept answering from the
    findings it had already discussed, and the second X-ray never reached the reply.
    """
    store = SessionStore()
    session, started_new = store.attach_analysis(None, {"findings": ["first"]})
    assert started_new is True
    store.append_message(session.session_id, {"role": "user", "content": "what do you see"})

    same, started_new = store.attach_analysis(session.session_id, {"findings": ["second"]})

    assert started_new is False
    assert same.session_id == session.session_id
    assert same.analysis == {"findings": ["second"]}
    assert NEW_XRAY_NOTICE in [m["content"] for m in same.messages]
    # The notice lands after the existing turn, so everything before it reads as history.
    assert same.messages[-1]["content"] == NEW_XRAY_NOTICE


def test_first_x_ray_is_not_announced():
    """Nothing has been superseded on the first upload; a notice would be a lie."""
    store = SessionStore()
    session, _ = store.attach_analysis(None, {"findings": ["first"]})
    assert session.messages == []


def test_a_third_x_ray_starts_a_fresh_consultation():
    """Two images per session. The third gets its own, rather than being refused."""
    store = SessionStore()
    first, _ = store.attach_analysis(None, {"findings": ["a"]})
    second, started_new = store.attach_analysis(first.session_id, {"findings": ["b"]})
    assert started_new is False

    third, started_new = store.attach_analysis(first.session_id, {"findings": ["c"]})

    assert started_new is True
    assert third.session_id != first.session_id
    assert third.analysis == {"findings": ["c"]}
    assert third.analysis_count == 1
    assert third.messages == []          # a fresh consultation, not a continuation
    # The full one is left intact behind it.
    assert store.get(first.session_id).analysis == {"findings": ["b"]}


def test_attach_analysis_mints_a_session_for_an_expired_id():
    store = SessionStore(ttl_seconds=0)
    stale = store.create()
    time.sleep(0.01)
    session, started_new = store.attach_analysis(stale.session_id, {"findings": ["x"]})
    assert started_new is True
    assert session.session_id != stale.session_id
