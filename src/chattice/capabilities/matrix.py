"""Capability model: response channel, outbound operations, preview features.

Split after an independent pre-beta review: the
pre-fix matrix mixed three different questions into one table — what the
ingress response channel can do, what an outbound credential can call, and
what a specific interaction event allows. Each question now has its own
type:

- :class:`ResponseCapabilities` — derived from the transport plus the
  concrete interaction event (dialogs, App Home, matched URL, bot/human
  sender, widget autocomplete).
- :class:`OutboundCapabilities` — derived from the credential kind
  (app/user), available OAuth scopes, and the operation; guards live next
  to ``Bot``.
- :class:`PreviewFeature` — Developer Preview Google features, a stability
  flag, not an auth capability.

Verified Google facts: docs/research/google-chat.md Phases 2-8 and
docs/audits/research/google-api-facts-2026-08.md.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from enum import Enum, auto

from chattice.auth import AuthMode
from chattice.events import (
    ActionEvent,
    AppHomeEvent,
    CommandEvent,
    DialogEventType,
    Event,
    FormSubmitEvent,
    MessageEvent,
    WidgetUpdatedEvent,
)

__all__ = [
    "PREVIEW_APP_COMMAND_TYPES",
    "CapabilityNotSupported",
    "OutboundCapabilities",
    "OutboundCapability",
    "PreviewCapabilities",
    "PreviewFeature",
    "ResponseCapabilities",
    "ResponseCapability",
    "can_open_dialog",
]


def can_open_dialog(event: Event | None) -> bool:
    """One source of truth : which events may open a dialog.

    Commands always can; actions only when Google delivered them WITH
    REQUEST_DIALOG metadata. SUBMIT/CANCEL actions cannot return a new
    dialog, and a plain Message cannot open one either.
    """
    if isinstance(event, CommandEvent):
        return True
    if isinstance(event, ActionEvent) and event.dialog is not None:
        return event.dialog.type == DialogEventType.REQUEST_DIALOG
    return False


_TRANSPORTS = ("http", "pubsub")


class CapabilityNotSupported(RuntimeError):
    """An operation was attempted without its required capability."""


class ResponseCapability(Enum):
    """What the synchronous ingress response channel can do."""

    SYNC_RESPONSE = auto()
    DIALOGS = auto()
    APP_HOME = auto()
    CARD_UPDATE_BOT = auto()
    CARD_UPDATE_USER = auto()
    UPDATE_WIDGET = auto()


_RESPONSE_DESCRIPTIONS: dict[ResponseCapability, str] = {
    ResponseCapability.SYNC_RESPONSE: (
        "The HTTP interaction transport provides a 30-second synchronous "
        "response channel."
    ),
    ResponseCapability.DIALOGS: "Dialogs require the HTTP interaction transport.",
    ResponseCapability.APP_HOME: (
        "App Home responses require an APP_HOME or SUBMIT_FORM interaction."
    ),
    ResponseCapability.CARD_UPDATE_BOT: (
        "UPDATE_MESSAGE responses require a CARD_CLICKED on a bot message "
        "(message sender type BOT)."
    ),
    ResponseCapability.CARD_UPDATE_USER: (
        "UPDATE_USER_MESSAGE_CARDS responses require a CARD_CLICKED on a "
        "human message or a MESSAGE with a matched URL."
    ),
    ResponseCapability.UPDATE_WIDGET: (
        "UPDATE_WIDGET autocomplete responses require a WIDGET_UPDATED event."
    ),
}


class ResponseCapabilities:
    """An immutable response-channel capability set with require() guards."""

    def __init__(
        self, capabilities: frozenset[ResponseCapability] | set[ResponseCapability]
    ) -> None:
        self._capabilities = frozenset(capabilities)

    def __contains__(self, capability: ResponseCapability) -> bool:
        return capability in self._capabilities

    def __iter__(self) -> Iterator[ResponseCapability]:
        return iter(self._capabilities)

    def require(self, capability: ResponseCapability) -> None:
        """Raise CapabilityNotSupported when the capability is missing."""
        if capability in self._capabilities:
            return
        detail = _RESPONSE_DESCRIPTIONS.get(capability, "")
        message = f"{capability.name} is not supported in this configuration. {detail}"
        raise CapabilityNotSupported(message.rstrip())

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ResponseCapabilities):
            return NotImplemented
        return self._capabilities == other._capabilities

    @classmethod
    def resolve(
        cls, *, transport: str = "http", event: Event | None = None
    ) -> ResponseCapabilities:
        """Resolve the response-channel capabilities for a transport + event.

        HTTP provides the sync response channel and dialogs; Pub/Sub push
        provides NO response channel (ack-only). Event-specific response
        rules are derived from the concrete event, never guessed.
        """
        if transport not in _TRANSPORTS:
            raise ValueError(
                f"Unknown transport {transport!r}; supported: {', '.join(_TRANSPORTS)}"
            )
        if transport == "pubsub":
            return cls(set())
        capabilities: set[ResponseCapability] = {ResponseCapability.SYNC_RESPONSE}
        # DIALOGS only for events that can actually open a dialog
        # (command / REQUEST_DIALOG action) — a plain Message advertising
        # DIALOGS produced 500s at serialization.
        if can_open_dialog(event):
            capabilities.add(ResponseCapability.DIALOGS)
        if isinstance(event, (AppHomeEvent, FormSubmitEvent)):
            capabilities.add(ResponseCapability.APP_HOME)
        if isinstance(event, WidgetUpdatedEvent):
            capabilities.add(ResponseCapability.UPDATE_WIDGET)
        if isinstance(event, ActionEvent):
            if event.sender_type == "BOT":
                capabilities.add(ResponseCapability.CARD_UPDATE_BOT)
            elif event.sender_type == "HUMAN":
                capabilities.add(ResponseCapability.CARD_UPDATE_USER)
        if isinstance(event, MessageEvent) and event.matched_url is not None:
            capabilities.add(ResponseCapability.CARD_UPDATE_USER)
        return cls(capabilities)


class OutboundCapability(Enum):
    """What an authenticated outbound client can call."""

    MESSAGE_CREATE = auto()
    MESSAGE_UPDATE = auto()
    USER_IMPERSONATION = auto()
    ATTACHMENT_UPLOAD = auto()
    MEDIA_DOWNLOAD = auto()
    ATTACHMENT_METADATA_GET = auto()


_OUTBOUND_DESCRIPTIONS: dict[OutboundCapability, str] = {
    OutboundCapability.MESSAGE_CREATE: (
        "Creating messages requires app or user authentication and an "
        "admissible OAuth scope."
    ),
    OutboundCapability.MESSAGE_UPDATE: (
        "Updating messages requires app or user authentication and an "
        "admissible OAuth scope."
    ),
    OutboundCapability.USER_IMPERSONATION: (
        "Impersonating users requires user authentication (OAuth or "
        "domain-wide delegation)."
    ),
    OutboundCapability.ATTACHMENT_UPLOAD: (
        "media.upload requires user authentication — a service-account/"
        "app-auth Bot cannot upload local files."
    ),
    OutboundCapability.MEDIA_DOWNLOAD: (
        "media.download allows user scopes (chat.messages.readonly/"
        "chat.messages) or app auth (chat.bot)."
    ),
    OutboundCapability.ATTACHMENT_METADATA_GET: (
        "spaces.messages.attachments.get requires app authentication "
        "(chat.bot) and serves metadata only."
    ),
}

# Verified Google facts (release notes + media/attachments references):
# app auth can create/update only the app's OWN messages; user auth can
# create/update user messages. media.upload is USER-only; media.download
# allows USER or APP; attachment metadata get is APP-only.
_APP_OUTBOUND = frozenset(
    {
        OutboundCapability.MESSAGE_CREATE,
        OutboundCapability.MESSAGE_UPDATE,
        OutboundCapability.MEDIA_DOWNLOAD,
        OutboundCapability.ATTACHMENT_METADATA_GET,
    }
)
_USER_OUTBOUND = frozenset(
    {
        OutboundCapability.MESSAGE_CREATE,
        OutboundCapability.MESSAGE_UPDATE,
        OutboundCapability.USER_IMPERSONATION,
        OutboundCapability.ATTACHMENT_UPLOAD,
        OutboundCapability.MEDIA_DOWNLOAD,
    }
)

_GOOGLE_AUTH_SCOPE_PREFIX = "https://www.googleapis.com/auth/"


@dataclass(frozen=True, slots=True)
class _CapabilityRule:
    """One identity-specific, any-of OAuth scope rule for an operation."""

    auth_mode: AuthMode
    capability: OutboundCapability
    any_scope: frozenset[str]


def _scopes(*names: str) -> frozenset[str]:
    return frozenset(f"{_GOOGLE_AUTH_SCOPE_PREFIX}{name}" for name in names)


# Official method references (verified 2026-08-16/18):
# https://developers.google.com/workspace/chat/api/reference/rest/v1/spaces.messages/create
# https://developers.google.com/workspace/chat/api/reference/rest/v1/spaces.messages/update
# https://developers.google.com/workspace/chat/api/reference/rest/v1/media/upload
# https://developers.google.com/workspace/chat/api/reference/rest/v1/media/download
# https://developers.google.com/workspace/chat/api/reference/rest/v1/spaces.messages.attachments/get
_OUTBOUND_SCOPE_RULES = (
    _CapabilityRule(
        AuthMode.APP,
        OutboundCapability.MESSAGE_CREATE,
        _scopes("chat.bot"),
    ),
    _CapabilityRule(
        AuthMode.USER,
        OutboundCapability.MESSAGE_CREATE,
        _scopes("chat.messages.create", "chat.messages", "chat.import"),
    ),
    _CapabilityRule(
        AuthMode.APP,
        OutboundCapability.MESSAGE_UPDATE,
        _scopes("chat.bot"),
    ),
    _CapabilityRule(
        AuthMode.USER,
        OutboundCapability.MESSAGE_UPDATE,
        _scopes("chat.messages", "chat.import"),
    ),
    _CapabilityRule(
        AuthMode.USER,
        OutboundCapability.ATTACHMENT_UPLOAD,
        _scopes("chat.messages.create", "chat.messages", "chat.import"),
    ),
    _CapabilityRule(
        AuthMode.USER,
        OutboundCapability.MEDIA_DOWNLOAD,
        _scopes("chat.messages.readonly", "chat.messages"),
    ),
    _CapabilityRule(
        AuthMode.APP,
        OutboundCapability.MEDIA_DOWNLOAD,
        _scopes("chat.bot"),
    ),
    _CapabilityRule(
        AuthMode.APP,
        OutboundCapability.ATTACHMENT_METADATA_GET,
        _scopes("chat.bot"),
    ),
)


class OutboundCapabilities:
    """An immutable outbound capability set with require() guards."""

    def __init__(
        self, capabilities: frozenset[OutboundCapability] | set[OutboundCapability]
    ) -> None:
        self._capabilities = frozenset(capabilities)

    def __contains__(self, capability: OutboundCapability) -> bool:
        return capability in self._capabilities

    def __iter__(self) -> Iterator[OutboundCapability]:
        return iter(self._capabilities)

    def require(self, capability: OutboundCapability) -> None:
        """Raise CapabilityNotSupported when the capability is missing."""
        if capability in self._capabilities:
            return
        detail = _OUTBOUND_DESCRIPTIONS.get(capability, "")
        message = f"{capability.name} is not supported in this configuration. {detail}"
        raise CapabilityNotSupported(message.rstrip())

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, OutboundCapabilities):
            return NotImplemented
        return self._capabilities == other._capabilities

    @classmethod
    def resolve(
        cls,
        auth_mode: AuthMode,
        *,
        scopes: Iterable[str] | None = None,
    ) -> OutboundCapabilities:
        """Resolve a local preflight set for an identity and known scopes.

        ``scopes=None`` means scope information is unavailable, so resolution
        preserves the auth-mode baseline rather than guessing that a scope is
        absent. A provided iterable, including an empty one, is reliable local
        knowledge: each operation is enabled only when any scope in its
        identity-specific rule is present. Server-side membership, resource
        role, and administrator approval checks remain authoritative.
        """
        if auth_mode is AuthMode.APP:
            baseline = _APP_OUTBOUND
        elif auth_mode is AuthMode.USER:
            baseline = _USER_OUTBOUND
        else:
            return cls(set())
        if scopes is None:
            return cls(baseline)

        known_scopes = frozenset(scopes)
        supported = {
            rule.capability
            for rule in _OUTBOUND_SCOPE_RULES
            if rule.auth_mode is auth_mode and rule.any_scope & known_scopes
        }
        # USER_IMPERSONATION describes the credential identity, not a Google
        # Chat method. It therefore remains identity-derived rather than being
        # assigned a fabricated OAuth scope rule.
        if auth_mode is AuthMode.USER:
            supported.add(OutboundCapability.USER_IMPERSONATION)
        return cls(supported)


class PreviewFeature(Enum):
    """Developer Preview Google features (stability flags, not auth).

    Sources: Google Chat release notes (verified 2026-08-15). These exist
    so documentation and code reference ONE list of preview surfaces.
    """

    MESSAGE_ACTION = auto()  # APP_COMMAND message actions (DP 2026-04-10)
    REPLACE_CARDS = auto()  # messages.replaceCards
    USER_AUTH_CARDS = auto()  # card creation with user auth
    CUSTOMER_LEVEL_SUBSCRIPTIONS = auto()  # Workspace Events customer-level
    PINNED_MESSAGES = auto()  # chat.spaces.pins
    RELEVANCE_SEARCH_ORDERING = auto()  # messages/spaces search relevance


class PreviewCapabilities:
    """Explicit enrollment set for typed Developer Preview routing."""

    def __init__(self, features: Iterable[PreviewFeature] = ()) -> None:
        self._features = frozenset(features)

    def __contains__(self, feature: PreviewFeature) -> bool:
        return feature in self._features

    def __iter__(self) -> Iterator[PreviewFeature]:
        return iter(self._features)

    def require(self, feature: PreviewFeature) -> None:
        if feature not in self._features:
            raise CapabilityNotSupported(
                f"{feature.name} is a Developer Preview feature; enable it "
                "explicitly on Dispatcher(preview_features=...)."
            )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PreviewCapabilities):
            return NotImplemented
        return self._features == other._features


# APP_COMMAND types that are Developer Preview: the adapter accepts them
# forward-compatibly (CommandEvent.source_kind carries the wire string) but
# they are not advertised as stable.
PREVIEW_APP_COMMAND_TYPES: frozenset[str] = frozenset({"MESSAGE_ACTION"})
