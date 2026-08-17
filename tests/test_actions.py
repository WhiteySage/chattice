"""Typed ActionData codec and filter (B1)."""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import cast

import pytest

from chattice import Dispatcher, Router
from chattice.actions import ActionData, ActionDataDecodeError
from chattice.adapters.google_chat import parse_interaction
from chattice.events import ActionEvent


class Env(enum.Enum):
    PROD = "prod"
    STAGING = "staging"


@dataclass
class DeployAction(ActionData):
    environment: str
    server: str
    replicas: int = 1
    dry_run: bool = False
    ratio: float = 1.0
    env_kind: Env | None = None


def _click(parameters: dict[str, str]) -> ActionEvent:
    payload = {
        "type": "CARD_CLICKED",
        "user": {"name": "users/1"},
        "space": {"name": "spaces/A"},
        "message": {"sender": {"type": "BOT"}},
        "common": {
            "invokedFunction": "deploy.confirm",
            "parameters": parameters,
        },
    }
    return cast(ActionEvent, parse_interaction(payload))


def test_round_trip_all_types() -> None:
    data = DeployAction(
        environment="prod",
        server="api-1",
        replicas=3,
        dry_run=True,
        ratio=2.5,
        env_kind=Env.PROD,
    )
    encoded = data.to_parameters()
    decoded = DeployAction.from_parameters(encoded)
    assert decoded == data


def test_optional_none_is_omitted_and_restored() -> None:
    data = DeployAction(environment="prod", server="s1", env_kind=None)
    encoded = data.to_parameters()
    assert "env_kind" not in encoded
    assert DeployAction.from_parameters(encoded).env_kind is None


def test_defaults_apply_when_parameters_missing() -> None:
    decoded = DeployAction.from_parameters({"environment": "prod", "server": "s1"})
    assert decoded.replicas == 1
    assert decoded.dry_run is False


def test_missing_required_field_raises() -> None:
    with pytest.raises(ActionDataDecodeError, match="environment"):
        DeployAction.from_parameters({"server": "s1"})


def test_malformed_int_raises() -> None:
    with pytest.raises(ActionDataDecodeError, match="int"):
        DeployAction.from_parameters(
            {"environment": "prod", "server": "s1", "replicas": "many"}
        )


def test_malformed_bool_raises() -> None:
    with pytest.raises(ActionDataDecodeError, match="bool"):
        DeployAction.from_parameters(
            {"environment": "prod", "server": "s1", "dry_run": "yes"}
        )


def test_malformed_enum_raises() -> None:
    with pytest.raises(ActionDataDecodeError, match="Env"):
        DeployAction.from_parameters(
            {"environment": "prod", "server": "s1", "env_kind": "dev"}
        )


def test_unknown_parameters_are_ignored() -> None:
    decoded = DeployAction.from_parameters(
        {
            "environment": "prod",
            "server": "s1",
            "autocomplete_widget_query": "Kai",  # system parameter
            "future_google_field": "x",
        }
    )
    assert decoded.environment == "prod"
    assert decoded.server == "s1"


def test_non_dataclass_model_rejected() -> None:
    class NotADataclass(ActionData):
        pass

    with pytest.raises(TypeError, match="dataclass"):
        NotADataclass.from_parameters({})


def test_unsupported_field_type_raises_on_decode() -> None:
    @dataclass
    class Bad(ActionData):
        value: dict[str, str]

    with pytest.raises(ActionDataDecodeError, match="unsupported"):
        Bad.from_parameters({"value": "{}"})


async def test_filter_matches_and_injects_typed_data() -> None:
    router = Router()
    seen: list[DeployAction] = []

    @router.action("deploy.confirm", DeployAction.filter())
    async def confirm(event: ActionEvent, data: DeployAction) -> str:
        seen.append(data)
        return f"deploying {data.environment}@{data.server}"

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    outcome = await dispatcher.feed_update(
        _click({"environment": "prod", "server": "api-1", "replicas": "2"})
    )
    assert outcome == "deploying prod@api-1"
    assert seen and seen[0].replicas == 2


async def test_filter_does_not_match_on_malformed_parameters() -> None:
    router = Router()
    matched = False

    @router.action("deploy.confirm", DeployAction.filter())
    async def confirm(event: ActionEvent, data: DeployAction) -> str:
        nonlocal matched
        matched = True
        return "x"

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    result = await dispatcher.feed_update(
        _click({"environment": "prod", "server": "s1", "replicas": "NaN"})
    )
    assert result is None  # no handler matched
    assert matched is False


async def test_filter_ignores_non_action_events() -> None:
    from chattice.events import MessageEvent

    router = Router()

    @router.message(DeployAction.filter())
    async def handler(message: MessageEvent, data: DeployAction) -> str:
        return "should-not-run"

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    result = await dispatcher.feed_update(MessageEvent(text="hi"))
    assert result is None


def test_optional_union_with_none_first() -> None:
    @dataclass
    class Odd(ActionData):
        value: str | None  # None first: still decodes as str

    decoded = Odd.from_parameters({"value": "x"})
    assert decoded.value == "x"


def test_non_finite_float_rejected() -> None:
    @dataclass
    class Floats(ActionData):
        ratio: float

    with pytest.raises(ActionDataDecodeError, match="finite"):
        Floats.from_parameters({"ratio": "nan"})
    with pytest.raises(TypeError, match="finite"):
        Floats(ratio=float("inf")).to_parameters()
