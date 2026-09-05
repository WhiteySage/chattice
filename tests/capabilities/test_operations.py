"""Tests for the declarative operation model."""

from chattice.auth import AuthMode
from chattice.capabilities.operations import (
    AuthPath,
    ExecutionVariant,
    Operation,
    OperationSpec,
    scopes,
)


def test_admin_path_carries_request_flag() -> None:
    path = AuthPath(
        identity=AuthMode.USER,
        any_scope=scopes("chat.admin.memberships"),
        variant=ExecutionVariant.ADMIN,
        request_flag="use_admin_access",
    )
    assert path.variant is ExecutionVariant.ADMIN
    assert path.request_flag == "use_admin_access"


def test_import_path_uses_import_scopes() -> None:
    path = AuthPath(
        identity=AuthMode.USER,
        any_scope=scopes("chat.import"),
        variant=ExecutionVariant.IMPORT,
    )
    assert path.variant is ExecutionVariant.IMPORT
    assert path.request_flag is None


def test_operation_values_are_stable_strings() -> None:
    assert Operation.MESSAGES_CREATE.value == "messages.create"
    assert Operation.SPACES_FIND_DIRECT_MESSAGE.value == "spaces.find_direct_message"


def test_spec_is_immutable() -> None:
    spec = OperationSpec(
        operation=Operation.SPACES_LIST,
        google_method="spaces.list",
        auth_paths=(AuthPath(AuthMode.APP, scopes("chat.bot")),),
        description="List spaces as the Chat app.",
    )
    assert spec.operation is Operation.SPACES_LIST
    assert spec.google_method == "spaces.list"
    assert len(spec.auth_paths) == 1
