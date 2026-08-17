"""F10 regression: frozen facades snapshot mutable inputs and validate
final shapes (typed and raw widgets obey the same rules)."""

from __future__ import annotations

import pytest

from chattice.cards import Button, Card, Dialog, RawWidget, Section
from chattice.workspace_events import parse_workspace_event


async def test_raw_widget_nested_mutation_does_not_change_widget() -> None:
    """The audit's probe: mutating the original nested dict after
    construction must not change raw.to_dict()."""
    payload: dict[str, object] = {
        "buttonList": {
            "buttons": [{"text": "a", "onClick": {"action": {"function": "f"}}}]
        }
    }
    widget = RawWidget(payload=payload)
    payload["buttonList"]["buttons"][0]["text"] = "EVIL"  # type: ignore[index]
    assert widget.to_dict()["buttonList"]["buttons"][0]["text"] == "a"  # type: ignore[index]


def test_dialog_rejects_datetime_picker_through_raw_widget() -> None:
    """F10: the dialog rule is enforced on the serialized tree — a
    dateTimePicker smuggled through a RawWidget must be rejected too."""
    card = Card(
        sections=[
            Section(widgets=[RawWidget(payload={"dateTimePicker": {"name": "when"}})])
        ]
    )
    with pytest.raises(ValueError, match="DateTimePicker"):
        Dialog(body=card)


def test_dialog_accepts_raw_widget_without_datetime_picker() -> None:
    card = Card(
        sections=[
            Section(widgets=[RawWidget(payload={"textParagraph": {"text": "ok"}})])
        ]
    )
    Dialog(body=card)  # must not raise


def test_button_rejects_both_action_and_link() -> None:
    with pytest.raises(ValueError, match="either"):
        Button("x", action="a", open_link="https://example.com")


def test_button_rejects_neither_action_nor_link_at_serialization() -> None:
    button = Button("x")
    with pytest.raises(ValueError, match="requires"):
        button.to_proto()


def test_button_snapshots_parameters() -> None:
    parameters = {"k": "v"}
    button = Button("x", action="a", parameters=parameters)
    parameters["k"] = "EVIL"
    proto = button.to_proto()
    on_click = proto.on_click.action
    assert {item.key: item.value for item in on_click.parameters} == {"k": "v"}


def test_workspace_event_deep_snapshots_data_and_raw() -> None:
    """F10: mutating the caller's nested values after parsing must not
    change the parsed event."""
    payload: dict[str, object] = {
        "specversion": "1.0",
        "id": "ev-1",
        "source": "//chat.googleapis.com/spaces/AAA",
        "type": "google.workspace.chat.message.v1.created",
        "data": {"message": {"text": "original"}},
    }
    event = parse_workspace_event(payload)
    # mutate the ORIGINAL nested structures
    payload["data"]["message"]["text"] = "EVIL"  # type: ignore[index]
    payload["type"] = "google.workspace.chat.message.v1.deleted"
    assert event.data["message"]["text"] == "original"  # type: ignore[index]
    assert event.raw["type"] == "google.workspace.chat.message.v1.created"
    assert event.cloud_type == "google.workspace.chat.message.v1.created"
