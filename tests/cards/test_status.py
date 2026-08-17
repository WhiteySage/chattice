"""ActionStatus facade."""

from __future__ import annotations

from chattice.cards import ActionStatus, ActionStatusCode


def test_ok_factory() -> None:
    status = ActionStatus.ok("Saved")
    assert status.status_code is ActionStatusCode.OK
    assert status.user_facing_message == "Saved"


def test_invalid_factory() -> None:
    status = ActionStatus.invalid("Too long")
    assert status.status_code is ActionStatusCode.INVALID_ARGUMENT
    assert status.user_facing_message == "Too long"


def test_to_dict_shape() -> None:
    data = ActionStatus.ok("Saved").to_dict()
    assert data["statusCode"] == "OK"
    assert data["userFacingMessage"] == "Saved"


def test_message_optional() -> None:
    assert ActionStatus.ok().user_facing_message is None
