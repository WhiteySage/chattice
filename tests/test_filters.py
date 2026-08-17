"""Magic and custom filter behavior."""

from collections.abc import Mapping

import pytest

from chattice import Dispatcher, F, Router
from chattice.events import ActionEvent, Event, MessageEvent
from chattice.exceptions import ContextConflictError, FilterError
from chattice.filters import BaseFilter, FilterValue


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        (F.text == "ping", True),
        (F.text == "pong", False),
        (F.text != "pong", True),
        (F.text != "ping", False),
        (F.text.contains("in"), True),
        (F.text.startswith("pi"), True),
        (F.text.endswith("ng"), True),
        (F.text.in_({"ping", "pong"}), True),
        (F.text.exists(), True),
        (F.missing.exists(), False),
        (F.missing != "anything", False),
    ],
)
async def test_magic_string_and_missing_operations(
    expression: BaseFilter, expected: bool
) -> None:
    assert await expression(MessageEvent(text="ping"), {}) is expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        (F.parameters["count"] < 4, True),
        (F.parameters["count"] <= 3, True),
        (F.parameters["count"] > 2, True),
        (F.parameters["count"] >= 3, True),
        (F.parameters["count"] > "2", False),
        (F.parameters["missing"] == 3, False),
    ],
)
async def test_comparisons_and_dictionary_traversal(
    expression: BaseFilter, expected: bool
) -> None:
    event = ActionEvent(name="deploy", parameters={"count": 3})
    assert await expression(event, {}) is expected


async def test_boolean_composition_and_identity() -> None:
    marker = object()
    event = Event(raw=marker)

    assert await ((F.raw.is_(marker)) & (F.event_type == "event"))(event, {})
    assert await ((F.event_type == "message") | (F.raw.is_(marker)))(event, {})
    assert await (~(F.event_type == "message"))(event, {})


async def test_nested_action_filter_routes_only_matching_event() -> None:
    router = Router()
    calls: list[str] = []

    @router.action(F.parameters["environment"] == "prod")
    async def deploy(action: ActionEvent) -> str:
        calls.append(action.name)
        return "deploy"

    dispatcher = Dispatcher()
    dispatcher.include_router(router)

    assert (
        await dispatcher.feed_update(
            ActionEvent(name="deploy", parameters={"environment": "dev"})
        )
        is None
    )
    assert (
        await dispatcher.feed_update(
            ActionEvent(name="deploy", parameters={"environment": "prod"})
        )
        == "deploy"
    )
    assert calls == ["deploy"]


class DependencyFilter(BaseFilter):
    async def __call__(
        self, event: Event, context: Mapping[str, object]
    ) -> FilterValue:
        del event, context
        return {"tenant": "production"}


async def test_async_custom_filter_can_supply_handler_context() -> None:
    router = Router()

    @router.message(DependencyFilter())
    async def handler(message: MessageEvent, tenant: object) -> tuple[str, object]:
        return message.text, tenant

    dispatcher = Dispatcher()
    dispatcher.include_router(router)

    assert await dispatcher.feed_update(MessageEvent(text="hello")) == (
        "hello",
        "production",
    )


async def test_filter_context_conflict_is_deterministic() -> None:
    router = Router()

    @router.message(DependencyFilter())
    async def handler(message: MessageEvent, tenant: object) -> object:
        del message
        return tenant

    dispatcher = Dispatcher()
    dispatcher.include_router(router)

    with pytest.raises(ContextConflictError, match="tenant"):
        await dispatcher.feed_update(MessageEvent(), tenant="caller")


async def test_invalid_filter_result_raises_clear_error() -> None:
    router = Router()

    async def invalid_filter(
        event: Event, context: Mapping[str, object]
    ) -> FilterValue:
        del event, context
        return 1  # type: ignore[return-value]

    @router.message(invalid_filter)
    async def handler(message: MessageEvent) -> None:
        del message

    dispatcher = Dispatcher()
    dispatcher.include_router(router)

    with pytest.raises(FilterError, match="expected bool or mapping"):
        await dispatcher.feed_update(MessageEvent())
