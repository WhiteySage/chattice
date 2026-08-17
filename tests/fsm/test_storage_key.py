"""StorageKey construction per strategy."""

from __future__ import annotations

from chattice.adapters.google_chat import parse_interaction
from chattice.events import Event
from chattice.fsm.storage import FSMStrategy, StorageKey


def _message(user: str, space: str, thread: str | None = None) -> Event:
    payload: dict[str, object] = {
        "type": "MESSAGE",
        "eventTime": "2026-08-13T12:35:00Z",
        "message": {"text": "x"},
        "user": {"name": user},
        "space": {"name": space},
    }
    if thread is not None:
        payload["message"] = {"text": "x", "thread": {"name": thread}}
    return parse_interaction(payload)


def test_user_in_space_with_thread() -> None:
    key = StorageKey.build(
        _message("users/1", "spaces/A", "spaces/A/threads/t1"),
        FSMStrategy.USER_IN_SPACE,
    )
    assert key is not None
    assert (key.user, key.space, key.thread) == (
        "users/1",
        "spaces/A",
        "spaces/A/threads/t1",
    )


def test_user_in_space_without_thread() -> None:
    key = StorageKey.build(_message("users/1", "spaces/A"), FSMStrategy.USER_IN_SPACE)
    assert key is not None
    assert (key.user, key.space, key.thread) == ("users/1", "spaces/A", None)


def test_user_in_space_missing_user_returns_none() -> None:
    event = parse_interaction(
        {
            "type": "MESSAGE",
            "eventTime": "2026-08-13T12:35:00Z",
            "message": {"text": "x"},
            "space": {"name": "spaces/A"},
        }
    )
    assert StorageKey.build(event, FSMStrategy.USER_IN_SPACE) is None


def test_user_strategy() -> None:
    key = StorageKey.build(_message("users/1", "spaces/A"), FSMStrategy.USER)
    assert key is not None
    assert (key.user, key.space, key.thread) == ("users/1", None, None)


def test_space_strategy() -> None:
    key = StorageKey.build(_message("users/1", "spaces/A"), FSMStrategy.SPACE)
    assert key is not None
    assert (key.user, key.space, key.thread) == (None, "spaces/A", None)
