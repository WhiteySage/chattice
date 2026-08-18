"""F.text.regexp — native regex routing in the Magic Filter DSL."""

from __future__ import annotations

import re

import pytest

from chattice.events import MessageEvent
from chattice.filters import F


def _event(text: str) -> MessageEvent:
    return MessageEvent(text=text)


async def test_regexp_match_from_start() -> None:
    filt = F.text.regexp(r"^[Тт]ест$")
    assert await filt(_event("Тест"), {}) is True
    assert await filt(_event("тест"), {}) is True
    assert await filt(_event("тест2"), {}) is False
    assert await filt(_event(" мой тест"), {}) is False


async def test_regexp_flags() -> None:
    filt = F.text.regexp(r"^тест$", flags=re.IGNORECASE)
    assert await filt(_event("ТЕСТ"), {}) is True


async def test_regexp_compiled_pattern() -> None:
    filt = F.text.regexp(re.compile(r"^ok"))
    assert await filt(_event("ok!"), {}) is True
    assert await filt(_event("nope"), {}) is False
    with pytest.raises(ValueError, match="compiled"):
        F.text.regexp(re.compile(r"^ok"), flags=re.IGNORECASE)


async def test_regexp_invalid_pattern_fails_at_construction() -> None:
    with pytest.raises(ValueError, match="invalid regex"):
        F.text.regexp("(")


async def test_regexp_missing_field_never_matches() -> None:
    filt = F.unknown_field.regexp("x")
    assert await filt(_event("x"), {}) is False


async def test_regexp_non_string_value_never_matches() -> None:
    class _OddEvent:
        text: int = 123

    assert F.text.regexp(r"\d+").evaluate(_OddEvent()) is False  # type: ignore[arg-type]


async def test_regexp_composition() -> None:
    filt = F.text.regexp(r"^ping") & ~F.text.regexp(r"^pong")
    assert await filt(_event("ping!"), {}) is True
    assert await filt(_event("pong!"), {}) is False
    or_filt = F.text.regexp(r"^a") | F.text.regexp(r"^b")
    assert await or_filt(_event("bingo"), {}) is True


async def test_regexp_equality_stays_literal() -> None:
    # A string containing regex-like syntax keeps its plain == semantics.
    event = _event("/start/")
    assert await (F.text == "/start/")(event, {}) is True
    assert await (F.text == r"^тест$")(event, {}) is False
