"""Action and OpenLink facades."""

from __future__ import annotations

from chattice.cards import Action, OpenLink


def test_action_builds_proto() -> None:
    action = Action(function="deploy.confirm", parameters={"environment": "prod"})
    proto = action.to_proto()
    assert proto.function == "deploy.confirm"
    assert [(p.key, p.value) for p in proto.parameters] == [("environment", "prod")]


def test_action_without_parameters() -> None:
    proto = Action(function="deploy.cancel").to_proto()
    assert proto.function == "deploy.cancel"
    assert len(proto.parameters) == 0


def test_action_from_proto_round_trip() -> None:
    action = Action(function="f", parameters={"a": "1", "b": "2"})
    assert Action.from_proto(action.to_proto()) == action


def test_open_link_builds_proto() -> None:
    link = OpenLink(url="https://example.com")
    proto = link.to_proto()
    assert proto.url == "https://example.com"
    assert OpenLink.from_proto(proto) == link
