"""Operation registry: the single source of outbound auth truth.

Preflight answers "the local configuration allows an attempt", never
"the call will succeed" — Google remains the final authority (403s from
membership, role, policy, admin approval, or resource state are still
possible). ``scopes=None`` means unknown and preserves the identity
baseline; the server decides.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator

from chattice.auth import AuthMode
from chattice.capabilities.operations import (
    AuthPath,
    ExecutionVariant,
    Operation,
    OperationSpec,
    scopes,
)

__all__ = ["REGISTRY", "SPECS", "OperationRegistry", "UnknownOperation"]


class UnknownOperation(KeyError):
    """A capability gate referenced an operation with no registry spec."""


class OperationRegistry:
    """Lookup and local preflight over OperationSpecs."""

    def __init__(self, specs: Iterable[OperationSpec]) -> None:
        self._specs: dict[Operation, OperationSpec] = {}
        for spec in specs:
            if spec.operation in self._specs:
                raise ValueError(f"Duplicate spec for {spec.operation}")
            self._specs[spec.operation] = spec

    def __contains__(self, operation: Operation) -> bool:
        return operation in self._specs

    def __iter__(self) -> Iterator[OperationSpec]:
        return iter(self._specs.values())

    def spec(self, operation: Operation) -> OperationSpec:
        try:
            return self._specs[operation]
        except KeyError:
            raise UnknownOperation(operation.value) from None

    def preflight(
        self,
        operation: Operation,
        *,
        identity: AuthMode | None,
        scopes: Iterable[str] | None = None,
        variant: ExecutionVariant = ExecutionVariant.NORMAL,
    ) -> bool:
        """Return whether the local configuration allows an attempt."""
        paths = [
            path
            for path in self.spec(operation).auth_paths
            if path.identity is identity and path.variant is variant
        ]
        if not paths:
            return False
        if scopes is None:
            return True
        known = frozenset(scopes)
        return any(path.any_scope & known for path in paths)

    def require(
        self,
        operation: Operation,
        *,
        identity: AuthMode | None,
        scopes: Iterable[str] | None = None,
        variant: ExecutionVariant = ExecutionVariant.NORMAL,
    ) -> None:
        """Raise CapabilityNotSupported when preflight fails."""
        if self.preflight(operation, identity=identity, scopes=scopes, variant=variant):
            return
        # Deferred import: matrix.py imports the registry, so the error
        # class resolves at call time to avoid a package cycle.
        from chattice.capabilities.matrix import CapabilityNotSupported

        spec = self.spec(operation)
        raise CapabilityNotSupported(
            f"{operation.name} is not supported in this configuration. "
            f"{spec.description}".rstrip()
        )


def _describe(text: str) -> str:
    return text


# Reviewed scope facts per official Google Chat references. Semantic
# constraints (identity selection, admin approval, preview status) are
# human-reviewed; the CI verifier checks method existence and scopes
# against the discovery document.
SPECS: tuple[OperationSpec, ...] = (
    OperationSpec(
        operation=Operation.MESSAGES_CREATE,
        google_method="spaces.messages.create",
        auth_paths=(
            AuthPath(AuthMode.APP, scopes("chat.bot")),
            AuthPath(
                AuthMode.USER,
                scopes("chat.messages.create", "chat.messages", "chat.import"),
            ),
        ),
        description=_describe(
            "Creating messages requires app or user authentication and an "
            "admissible OAuth scope."
        ),
    ),
    OperationSpec(
        operation=Operation.MESSAGES_UPDATE,
        google_method="spaces.messages.update",
        auth_paths=(
            AuthPath(AuthMode.APP, scopes("chat.bot")),
            AuthPath(AuthMode.USER, scopes("chat.messages", "chat.import")),
        ),
        description=_describe(
            "Updating messages requires app or user authentication and an "
            "admissible OAuth scope."
        ),
    ),
    OperationSpec(
        operation=Operation.MESSAGES_GET,
        google_method="spaces.messages.get",
        auth_paths=(
            AuthPath(AuthMode.APP, scopes("chat.bot")),
            AuthPath(AuthMode.USER, scopes("chat.messages.readonly", "chat.messages")),
        ),
        description=_describe(
            "Getting messages requires app or user authentication and an "
            "admissible OAuth scope."
        ),
    ),
    OperationSpec(
        operation=Operation.MESSAGES_LIST,
        paginated=True,
        google_method="spaces.messages.list",
        auth_paths=(
            AuthPath(AuthMode.APP, scopes("chat.app.messages.readonly")),
            AuthPath(AuthMode.USER, scopes("chat.messages.readonly", "chat.messages")),
        ),
        description=_describe(
            "Listing messages requires app or user authentication and an "
            "admissible OAuth scope."
        ),
    ),
    OperationSpec(
        operation=Operation.MESSAGES_DELETE,
        google_method="spaces.messages.delete",
        auth_paths=(
            AuthPath(AuthMode.APP, scopes("chat.bot")),
            AuthPath(AuthMode.USER, scopes("chat.messages")),
        ),
        description=_describe(
            "Deleting messages requires app or user authentication and an "
            "admissible OAuth scope."
        ),
    ),
    OperationSpec(
        operation=Operation.MEDIA_UPLOAD,
        google_method="media.upload",
        auth_paths=(
            AuthPath(
                AuthMode.USER,
                scopes("chat.messages.create", "chat.messages", "chat.import"),
            ),
        ),
        description="media.upload requires user authentication.",
    ),
    OperationSpec(
        operation=Operation.MEDIA_DOWNLOAD,
        google_method="media.download",
        auth_paths=(
            AuthPath(AuthMode.USER, scopes("chat.messages.readonly", "chat.messages")),
            AuthPath(AuthMode.APP, scopes("chat.bot")),
        ),
        description="media.download allows user scopes or app auth.",
    ),
    OperationSpec(
        operation=Operation.ATTACHMENT_METADATA_GET,
        google_method="spaces.messages.attachments.get",
        auth_paths=(AuthPath(AuthMode.APP, scopes("chat.bot")),),
        description="Attachment metadata requires app authentication.",
    ),
    OperationSpec(
        operation=Operation.SPACES_GET,
        google_method="spaces.get",
        auth_paths=(
            AuthPath(AuthMode.APP, scopes("chat.bot", "chat.spaces")),
            AuthPath(AuthMode.USER, scopes("chat.spaces", "chat.spaces.readonly")),
        ),
        description=_describe(
            "Getting a space requires app or user authentication and an "
            "admissible OAuth scope."
        ),
    ),
    OperationSpec(
        operation=Operation.SPACES_LIST,
        paginated=True,
        google_method="spaces.list",
        auth_paths=(AuthPath(AuthMode.APP, scopes("chat.bot")),),
        description=_describe(
            "Listing spaces as the Chat app requires app authentication with chat.bot."
        ),
    ),
    OperationSpec(
        operation=Operation.SPACES_FIND_DIRECT_MESSAGE,
        google_method="spaces.findDirectMessage",
        auth_paths=(
            AuthPath(AuthMode.USER, scopes("chat.spaces", "chat.spaces.readonly")),
            AuthPath(AuthMode.APP, scopes("chat.bot")),
        ),
        description=_describe(
            "Finding a direct message requires user authentication or app "
            "auth with chat.bot."
        ),
    ),
    OperationSpec(
        operation=Operation.SPACES_SETUP,
        google_method="spaces.setup",
        auth_paths=(
            AuthPath(AuthMode.USER, scopes("chat.spaces", "chat.spaces.create")),
        ),
        description=_describe(
            "Setting up a space requires user authentication with chat.spaces."
        ),
    ),
    OperationSpec(
        operation=Operation.MEMBERSHIPS_CREATE,
        google_method="spaces.members.create",
        auth_paths=(AuthPath(AuthMode.APP, scopes("chat.app.memberships")),),
        description=_describe(
            "Creating memberships requires app authentication with "
            "chat.app.memberships and Workspace administrator approval."
        ),
    ),
    OperationSpec(
        operation=Operation.MEMBERSHIPS_GET,
        google_method="spaces.members.get",
        auth_paths=(
            AuthPath(AuthMode.APP, scopes("chat.bot", "chat.app.memberships")),
        ),
        description=_describe(
            "Getting memberships requires app authentication with chat.bot "
            "or chat.app.memberships."
        ),
    ),
    OperationSpec(
        operation=Operation.MEMBERSHIPS_LIST,
        paginated=True,
        google_method="spaces.members.list",
        auth_paths=(
            AuthPath(AuthMode.APP, scopes("chat.bot", "chat.app.memberships")),
        ),
        description=_describe(
            "Listing memberships requires app authentication with chat.bot "
            "or chat.app.memberships."
        ),
    ),
    OperationSpec(
        operation=Operation.MEMBERSHIPS_DELETE,
        google_method="spaces.members.delete",
        auth_paths=(AuthPath(AuthMode.APP, scopes("chat.app.memberships")),),
        description=_describe(
            "Deleting memberships requires app authentication with "
            "chat.app.memberships and Workspace administrator approval."
        ),
    ),
    OperationSpec(
        operation=Operation.REACTIONS_CREATE,
        google_method="spaces.messages.reactions.create",
        auth_paths=(
            AuthPath(
                AuthMode.USER,
                scopes("chat.messages.reactions", "chat.messages.reactions.create"),
            ),
        ),
        description=_describe("Creating reactions requires user authentication."),
    ),
    OperationSpec(
        operation=Operation.REACTIONS_LIST,
        paginated=True,
        google_method="spaces.messages.reactions.list",
        auth_paths=(
            AuthPath(
                AuthMode.USER,
                scopes("chat.messages.reactions", "chat.messages.reactions.readonly"),
            ),
        ),
        description=_describe("Listing reactions requires user authentication."),
    ),
    OperationSpec(
        operation=Operation.REACTIONS_DELETE,
        google_method="spaces.messages.reactions.delete",
        auth_paths=(AuthPath(AuthMode.USER, scopes("chat.messages.reactions")),),
        description=_describe("Deleting reactions requires user authentication."),
    ),
    OperationSpec(
        operation=Operation.SPACE_READ_STATE_GET,
        google_method="users.spaces.getSpaceReadState",
        auth_paths=(
            AuthPath(
                AuthMode.USER,
                scopes("chat.users.readstate", "chat.users.readstate.readonly"),
            ),
        ),
        description=_describe(
            "Getting a space read state requires user authentication."
        ),
    ),
    OperationSpec(
        operation=Operation.SPACE_READ_STATE_UPDATE,
        google_method="users.spaces.updateSpaceReadState",
        auth_paths=(AuthPath(AuthMode.USER, scopes("chat.users.readstate")),),
        description=_describe(
            "Updating a space read state requires user authentication."
        ),
    ),
    OperationSpec(
        operation=Operation.THREAD_READ_STATE_GET,
        google_method="users.spaces.threads.getThreadReadState",
        auth_paths=(
            AuthPath(
                AuthMode.USER,
                scopes("chat.users.readstate", "chat.users.readstate.readonly"),
            ),
        ),
        description=_describe(
            "Getting a thread read state requires user authentication."
        ),
    ),
    OperationSpec(
        operation=Operation.NOTIFICATION_SETTING_GET,
        google_method="users.spaces.spaceNotificationSetting.get",
        auth_paths=(AuthPath(AuthMode.USER, scopes("chat.users.spacesettings")),),
        description=_describe(
            "Getting space notification settings requires user authentication."
        ),
    ),
    OperationSpec(
        operation=Operation.NOTIFICATION_SETTING_UPDATE,
        google_method="users.spaces.spaceNotificationSetting.patch",
        auth_paths=(AuthPath(AuthMode.USER, scopes("chat.users.spacesettings")),),
        description=_describe(
            "Updating space notification settings requires user authentication."
        ),
    ),
)

REGISTRY = OperationRegistry(SPECS)
