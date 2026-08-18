# ruff: noqa: ASYNC109 — timeout kwarg mirrors the gapic client call convention
"""High-level async Bot: authenticated outgoing Chat API operations."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Iterable, Mapping, Sequence
from enum import Enum
from pathlib import Path
from typing import Any, cast

from google.api_core import exceptions as api_core_exceptions
from google.apps.chat_v1 import ChatServiceAsyncClient
from google.apps.chat_v1.services.chat_service.transports import (
    ChatServiceTransport,
)
from google.apps.chat_v1.types.attachment import Attachment, AttachmentDataRef
from google.apps.chat_v1.types.message import (
    CardWithId,
    CreateMessageNotificationOptions,
    CreateMessageRequest,
    Message,
)
from google.apps.chat_v1.types.space import Space
from google.apps.chat_v1.types.user import User as ProtoUser
from google.auth.credentials import Credentials
from google.protobuf import field_mask_pb2  # type: ignore[import-untyped]

from chattice.auth import AuthMode, CredentialsProvider
from chattice.capabilities import (
    CapabilityNotSupported,
    OutboundCapabilities,
    OutboundCapability,
)
from chattice.cards import AccessoryWidget, Card
from chattice.events import SpaceRef, ThreadRef, UserRef
from chattice.media import AttachmentRef, InputFile, UploadedAttachment

from .errors import ChatAPIError, wrap_api_error

_GRPC_ASYNCIO = "grpc_asyncio"


def _attachment_data_ref_proto(mapping: Mapping[str, object]) -> AttachmentDataRef:
    """Build the SDK proto from a wire ``attachmentDataRef`` mapping."""
    kwargs: dict[str, Any] = {}
    resource_name = mapping.get("resourceName") or mapping.get("resource_name")
    if isinstance(resource_name, str) and resource_name:
        kwargs["resource_name"] = resource_name
    upload_token = mapping.get("attachmentUploadToken") or mapping.get(
        "attachment_upload_token"
    )
    if isinstance(upload_token, str) and upload_token:
        kwargs["attachment_upload_token"] = upload_token
    return AttachmentDataRef(**kwargs)


def _scope_attribute(credentials: Credentials, attribute: str) -> frozenset[str] | None:
    """Read a local credential scope attribute without doing any I/O."""
    value = cast(object, getattr(credentials, attribute, None))
    if value is None:
        return None
    if isinstance(value, str):
        return frozenset({value})
    if not isinstance(value, Iterable):
        return None
    scopes: set[str] = set()
    for scope in cast(Iterable[object], value):
        if not isinstance(scope, str):
            return None
        scopes.add(scope)
    return frozenset(scopes)


def _credential_scopes(
    auth_mode: AuthMode, credentials: Credentials | None
) -> frozenset[str] | None:
    """Return reliably known local scopes, or None when they are unknown.

    User token responses can narrow originally requested scopes, so an
    available ``granted_scopes`` value wins. App credentials use configured
    explicit/default scopes; neither source proves Workspace administrator
    approval for ``chat.app.*`` scopes.
    """
    if credentials is None:
        return None
    if auth_mode is AuthMode.USER:
        granted = _scope_attribute(credentials, "granted_scopes")
        if granted is not None:
            return granted
        return _scope_attribute(credentials, "scopes")
    if auth_mode is AuthMode.APP:
        explicit = _scope_attribute(credentials, "scopes")
        defaults = _scope_attribute(credentials, "default_scopes")
        if explicit is None and defaults is None:
            return None
        return (explicit or frozenset()) | (defaults or frozenset())
    return frozenset()


def _canonical_space(space: SpaceRef | str) -> str:
    """Validate and canonicalize a space target .

    One resource-name policy: a bare space ID is wrapped into the
    canonical ``spaces/{id}`` form (as the identifier docs promise),
    an already-canonical name passes through, malformed values raise
    locally — no network lookups, no remote errors replacing local
    validation.
    """
    name = space if isinstance(space, str) else space.name
    if name is None:
        raise ChatAPIError("SpaceRef has no name; cannot target a space")
    parent = name.strip()
    if not parent:
        raise ChatAPIError("space must be a non-empty identifier")
    if "/" in parent:
        if not parent.startswith("spaces/") or parent.count("/") != 1:
            raise ChatAPIError(
                "space must be a bare space ID or a canonical "
                "'spaces/{id}' resource name; got {parent!r}"
            )
        return parent
    return f"spaces/{parent}"


def _canonical_user(private_to: UserRef | str) -> str:
    """Validate and canonicalize a privateMessageViewer target.

    an empty string or a nameless ``UserRef`` must FAIL CLOSED — it
    previously produced a public message. A bare user ID is wrapped into
    the canonical ``users/{id}`` resource form; already-canonical names
    pass through; malformed values (whitespace, misplaced slashes) raise
    before any transport work.
    """
    name = private_to if isinstance(private_to, str) else private_to.name
    if name is None:
        raise ChatAPIError("private_to UserRef has no name; cannot target a user")
    viewer = name.strip()
    if not viewer:
        raise ChatAPIError("private_to must be a non-empty user identifier")
    if "/" in viewer:
        if not viewer.startswith("users/") or viewer.count("/") != 1:
            raise ChatAPIError(
                "private_to must be a bare user ID or a canonical "
                "'users/{id}' resource name; got {viewer!r}"
            )
        return viewer
    return f"users/{viewer}"


class MessageReplyOption(Enum):
    """Documented messageReplyOption values for send_message."""

    REPLY_FALLBACK_TO_NEW_THREAD = "reply_fallback_to_new_thread"
    REPLY_OR_FAIL = "reply_or_fail"
    NEW_THREAD = "new_thread"

    def to_proto(self) -> object:
        """Map to the SDK's nested MessageReplyOption enum value."""
        # The SDK nests the enum under CreateMessageRequest.
        proto = CreateMessageRequest.MessageReplyOption
        if self is MessageReplyOption.REPLY_FALLBACK_TO_NEW_THREAD:
            return proto.REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD
        if self is MessageReplyOption.REPLY_OR_FAIL:
            return proto.REPLY_MESSAGE_OR_FAIL
        return proto.MESSAGE_REPLY_OPTION_UNSPECIFIED


class Bot:
    """Authenticated outgoing Google Chat operations.

    The SDK client is created lazily on the first call so that Bot() can be
    constructed before credentials are available (e.g. in app factories).
    """

    def __init__(
        self,
        credentials: Credentials | None = None,
        *,
        credentials_provider: CredentialsProvider | None = None,
        app_credentials_provider: CredentialsProvider | None = None,
        user_credentials_provider: CredentialsProvider | None = None,
        auth_mode: AuthMode | None = None,
        transport: ChatServiceTransport | None = None,
    ) -> None:
        has_dual_providers = (
            app_credentials_provider is not None
            or user_credentials_provider is not None
        )
        if has_dual_providers:
            if credentials is not None or credentials_provider is not None:
                raise ValueError(
                    "app_credentials_provider/user_credentials_provider cannot "
                    "be combined with credentials/credentials_provider"
                )
            if auth_mode is not None:
                raise ValueError(
                    "auth_mode is implied by the app/user credential "
                    "providers; pass it only for a single-identity Bot"
                )
        self._credentials = credentials
        # The APP identity: explicit dual provider wins, the legacy
        # credentials_provider alias covers single-identity construction.
        self._credentials_provider = credentials_provider or app_credentials_provider
        self._user_credentials_provider = user_credentials_provider
        self._auth_mode = auth_mode
        self._transport = transport
        self._client: ChatServiceAsyncClient | None = None
        self._resolved_credentials: Credentials | None = None
        self._resolved_set = False
        self._resolved_user_credentials: Credentials | None = None
        self._resolved_user_set = False
        self._closed = False
        # single-flight tasks — concurrent first calls share ONE
        # credential resolution and ONE client construction (a shared
        # Task, not a lock held across provider code).
        self._credential_task: asyncio.Task[Credentials | None] | None = None
        self._user_credential_task: asyncio.Task[Credentials | None] | None = None
        self._init_task: asyncio.Task[ChatServiceAsyncClient] | None = None
        # The USER identity has its own cached client: attachment messages
        # must be created with the SAME USER credentials that uploaded
        # them (live-verified: an APP-authenticated create cannot consume
        # a USER-uploaded attachment — Google rejects the handoff).
        self._user_client: ChatServiceAsyncClient | None = None
        self._user_init_task: asyncio.Task[ChatServiceAsyncClient] | None = None

    def _classify(self, credentials: Credentials | None) -> AuthMode | None:
        if credentials is None:
            return None
        if getattr(credentials, "_subject", None):
            # Domain-wide delegation: a service account impersonating a
            # user (with_subject) acts as USER authentication.
            return AuthMode.USER
        if hasattr(credentials, "signer"):  # service account
            return AuthMode.APP
        if getattr(credentials, "refresh_token", None):
            return AuthMode.USER
        return None

    @property
    def auth_mode(self) -> AuthMode | None:
        """The outgoing auth mode: explicit, or classified from credentials.

        Synchronous classification; the async Bot methods use
        ``_auth_mode_async`` so blocking providers never run on the loop.
        """
        if self._auth_mode is not None:
            return self._auth_mode
        return self._classify(self._resolve_credentials())

    async def _auth_mode_async(self) -> AuthMode | None:
        """Off-loop variant of :attr:`auth_mode` for async call paths."""
        if self._auth_mode is not None:
            return self._auth_mode
        return self._classify(await self._resolve_credentials_async())

    @property
    def capabilities(self) -> OutboundCapabilities | None:
        """The local preflight set for current auth and available scopes."""
        mode = self.auth_mode
        if mode is None:
            return None
        if self._resolved_set:
            credentials = self._resolved_credentials
        elif self._credentials_provider is None:
            credentials = self._credentials
        else:
            # Do not invoke an unresolved provider merely to inspect scopes.
            # The async operation path feeds scopes in when it performs the
            # already-required lazy credential resolution.
            credentials = None
        return OutboundCapabilities.resolve(
            mode, scopes=_credential_scopes(mode, credentials)
        )

    async def _capabilities_async(self) -> OutboundCapabilities | None:
        """Resolve local preflight from the credentials needed by the call."""
        mode = await self._auth_mode_async()
        if mode is None:
            return None
        credentials = (
            None if mode is AuthMode.NONE else await self._resolve_credentials_async()
        )
        return OutboundCapabilities.resolve(
            mode, scopes=_credential_scopes(mode, credentials)
        )

    def _resolve_credentials(self) -> Credentials | None:
        """Resolve credentials once (the provider is called a single time).

        A provider failure is NOT cached: the flag is set only on success,
        so the error re-raises on every attempt instead of silently
        degrading to None (which would disable the capability guards).
        """
        if not self._resolved_set:
            if self._closed:
                raise ChatAPIError("Bot is closed; create a new instance")
            if self._credentials_provider is not None:
                self._resolved_credentials = self._credentials_provider()
            else:
                self._resolved_credentials = self._credentials
            self._resolved_set = True
        return self._resolved_credentials

    @property
    def raw_client(self) -> ChatServiceAsyncClient:
        """The underlying SDK client (escape hatch).

        Uses the synchronous credential path; async callers should prefer
        the normal Bot methods, which resolve credentials off the loop.
        """
        return self._get_client()

    def _get_client(self) -> ChatServiceAsyncClient:
        if self._closed:
            raise ChatAPIError("Bot is closed; create a new instance")
        client = self._client
        if client is not None:
            return client
        return self._build_client(self._resolve_credentials())

    async def _get_client_async(self) -> ChatServiceAsyncClient:
        """Single-flight async client initialization .

        Credential providers may perform blocking I/O (file reads, token
        refresh); the async path runs them in a worker thread. Concurrent
        first calls share ONE construction task. A failed construction is
        not cached — the next call retries (provider errors stay
        retryable, the pinned contract).
        """
        client = self._client
        if client is not None:
            return client
        task = self._init_task
        if task is None:
            task = asyncio.create_task(self._initialize_client())
            self._init_task = task
        try:
            # Shield: cancellation of a WAITER must not kill the shared
            # construction for everyone else.
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            raise
        except Exception:
            if self._init_task is task:
                self._init_task = None
            raise

    async def _initialize_client(self) -> ChatServiceAsyncClient:
        """Resolve credentials and build the client; never publish after close."""
        if self._closed:
            raise ChatAPIError("Bot is closed; create a new instance")
        credentials = await self._resolve_credentials_async()
        if self._closed:
            # close() began while the provider ran off-loop: the client
            # must NOT be published after terminal close.
            raise ChatAPIError("Bot is closed; create a new instance")
        return self._build_client(credentials)

    def _build_client(self, credentials: Credentials | None) -> ChatServiceAsyncClient:
        if self._transport is not None:
            # SDK rule: a transport instance carries its own credentials;
            # passing credentials alongside raises ValueError.
            self._client = ChatServiceAsyncClient(transport=self._transport)
            return self._client
        if credentials is None:
            raise ChatAPIError(
                "Bot has no credentials; pass google.auth credentials "
                "or a credentials_provider to Bot(...)"
            )
        self._client = ChatServiceAsyncClient(
            credentials=credentials,
            transport=_GRPC_ASYNCIO,
        )
        return self._client

    def _build_user_client(self, credentials: Credentials) -> ChatServiceAsyncClient:
        """Build the cached USER Chat client.

        Mirrors the APP client construction: an injected transport (used
        by the testing toolkit) carries no identity, so the same fake
        transport may back both clients in tests. In production the USER
        client gets its own real gRPC-asyncio transport.
        """
        if self._transport is not None:
            self._user_client = ChatServiceAsyncClient(transport=self._transport)
            return self._user_client
        self._user_client = ChatServiceAsyncClient(
            credentials=credentials,
            transport=_GRPC_ASYNCIO,
        )
        return self._user_client

    async def _get_user_client_async(self) -> ChatServiceAsyncClient:
        """Single-flight async USER client initialization .

        Same contract as the APP path: concurrent first attachment sends
        share ONE construction task, a waiter's cancellation never kills
        the shared construction, and a failed construction is not cached
        (provider errors stay retryable).
        """
        client = self._user_client
        if client is not None:
            return client
        task = self._user_init_task
        if task is None:
            task = asyncio.create_task(self._initialize_user_client())
            self._user_init_task = task
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            raise
        except Exception:
            if self._user_init_task is task:
                self._user_init_task = None
            raise

    async def _initialize_user_client(self) -> ChatServiceAsyncClient:
        """Resolve USER credentials and build the client; never publish after close."""
        if self._closed:
            raise ChatAPIError("Bot is closed; create a new instance")
        credentials = await self._resolve_user_credentials_async()
        if credentials is None:
            raise CapabilityNotSupported(
                "Sending message attachments requires USER authentication for "
                "both media.upload and messages.create. Configure "
                "user_credentials_provider=... — UserCredentialsProvider, or "
                "DelegatedUserCredentialsProvider for domain-wide delegation."
            )
        if self._closed:
            # close() began while the provider ran off-loop: the client
            # must NOT be published after terminal close.
            raise ChatAPIError("Bot is closed; create a new instance")
        return self._build_user_client(credentials)

    async def _resolve_credentials_async(self) -> Credentials | None:
        """Async-safe single-flight credential resolution .

        The provider is called exactly ONCE even under concurrent first
        sends (the previous lock-free path raced on the resolve flag). A
        provider failure is not cached: the shared task is dropped so the
        next attempt re-invokes the provider.
        """
        task = self._credential_task
        if task is None:
            task = asyncio.create_task(self._resolve_credentials_once())
            self._credential_task = task
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            raise
        except Exception:
            if self._credential_task is task:
                self._credential_task = None
            raise

    async def _resolve_credentials_once(self) -> Credentials | None:
        if self._closed:
            raise ChatAPIError("Bot is closed; create a new instance")
        if self._resolved_set:
            return self._resolved_credentials
        if self._credentials_provider is not None:
            self._resolved_credentials = await asyncio.to_thread(
                self._credentials_provider
            )
        else:
            self._resolved_credentials = self._credentials
        self._resolved_set = True
        return self._resolved_credentials

    async def _resolve_user_credentials_async(self) -> Credentials | None:
        """Async-safe single-flight USER identity resolution."""
        task = self._user_credential_task
        if task is None:
            task = asyncio.create_task(self._resolve_user_credentials_once())
            self._user_credential_task = task
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            raise
        except Exception:
            if self._user_credential_task is task:
                self._user_credential_task = None
            raise

    async def _resolve_user_credentials_once(self) -> Credentials | None:
        if self._closed:
            raise ChatAPIError("Bot is closed; create a new instance")
        if self._resolved_user_set:
            return self._resolved_user_credentials
        if self._user_credentials_provider is not None:
            self._resolved_user_credentials = await asyncio.to_thread(
                self._user_credentials_provider
            )
        else:
            single = await self._resolve_credentials_async()
            self._resolved_user_credentials = (
                single if self._classify(single) is AuthMode.USER else None
            )
        self._resolved_user_set = True
        return self._resolved_user_credentials

    async def close(self) -> None:
        """Close the underlying SDK transport (idempotent, awaitable).

        close is linearizable with initialization. Once close
        begins, NO client may be published; if construction already
        completed, its transport is closed exactly once before close
        returns. The async gRPC transport's closer is itself awaitable —
        it is AWAITED here (a plain sync call would leak the channel).
        Safe to call multiple times; after close the client must not be
        used. Also available as ``async with Bot(...)``.
        """
        if self._closed:
            return
        self._closed = True
        for task in (
            self._credential_task,
            self._user_credential_task,
            self._init_task,
            self._user_init_task,
        ):
            if task is None:
                continue
            # In-flight resolution/construction either completes and
            # publishes (then we close it below) or observes _closed and
            # raises — both are deterministic; shield keeps OUR
            # cancellation from breaking the shared task for other
            # waiters.
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                raise
            except ChatAPIError:
                pass  # aborted by our own close — nothing to close
        # Close every initialized client exactly once. The injected test
        # transport may back both clients; each transport is closed once.
        closed_transports: set[object] = set()
        for client in (self._client, self._user_client):
            if client is None:
                continue
            transport = client.transport
            if transport in closed_transports:
                continue
            closed_transports.add(transport)
            closer = getattr(transport, "close", None)
            if closer is None:
                continue
            result = closer()
            if inspect.isawaitable(result):
                await result

    async def __aenter__(self) -> Bot:
        return self

    async def __aexit__(
        self,
        exc_type: object,
        exc_value: object,
        traceback: object,
    ) -> None:
        await self.close()

    async def send_message(
        self,
        space: SpaceRef | str,
        text: str | None = None,
        *,
        thread: ThreadRef | None = None,
        reply_option: MessageReplyOption = (
            MessageReplyOption.REPLY_FALLBACK_TO_NEW_THREAD
        ),
        request_id: str | None = None,
        message_id: str | None = None,
        timeout: float | None = None,
        accessory_widgets: Sequence[AccessoryWidget] | None = None,
        card: Card | None = None,
        notify: str | None = None,
        private_to: UserRef | str | None = None,
        attachments: Sequence[InputFile | UploadedAttachment] | None = None,
    ) -> Message:
        # ``notify``: "force" | "silent" (documented app-auth notification
        # options; None = default). ``private_to``: privateMessageViewer —
        # the message is visible only to that user (app auth; not combined
        # with attachments/accessory widgets). every deterministic
        # outbound constraint is validated BEFORE any client work, so
        # rejected requests make zero transport calls and privacy intent
        # can never silently become public.
        # Attachment messages are USER-authenticated end to end: Google
        # live-verified that an APP-authenticated create cannot consume
        # an attachment uploaded by the USER identity. The whole send
        # (media.upload AND messages.create) therefore runs on the USER
        # client; the APP client is not used for attachment sends.
        has_attachments = bool(attachments)
        # Combination guards first: these are identity-independent and
        # must reject before any identity resolution.
        if has_attachments:
            if private_to is not None:
                raise ChatAPIError(
                    "private_to cannot be combined with attachments "
                    "(Google: private messages omit attachments)."
                )
            if accessory_widgets:
                raise ChatAPIError(
                    "attachments cannot be combined with accessory widgets "
                    "(Google restriction)."
                )
        mode = AuthMode.USER if has_attachments else await self._auth_mode_async()
        if notify is not None:
            if notify not in ("force", "silent"):
                raise ChatAPIError(
                    f"notify must be 'force', 'silent', or None; got {notify!r}"
                )
            if has_attachments:
                raise CapabilityNotSupported(
                    "notify (createMessageNotificationOptions) requires app "
                    "authentication and cannot be combined with attachments: "
                    "attachment messages are USER-authenticated."
                )
            if mode is not AuthMode.APP:
                raise CapabilityNotSupported(
                    "createMessageNotificationOptions requires app "
                    "authentication (chat.bot)."
                )
        viewer: str | None = None
        if private_to is not None:
            viewer = _canonical_user(private_to)
            if mode is not AuthMode.APP:
                raise CapabilityNotSupported(
                    "Private messages (privateMessageViewer) require app "
                    "authentication (chat.bot)."
                )
            if accessory_widgets:
                raise ChatAPIError(
                    "private_to cannot be combined with accessory widgets "
                    "(Google: privateMessageViewer is not compatible with "
                    "accessory widgets)."
                )
        if card is not None and mode is AuthMode.USER:
            raise CapabilityNotSupported(
                "User-auth card creation is a Google Developer Preview "
                "(PreviewFeature.USER_AUTH_CARDS); use app auth or "
                "Bot.raw_client for preview surfaces."
            )
        # one resource-name policy — bare IDs canonicalize to
        # spaces/{id} BEFORE any transport work.
        parent = _canonical_space(space)
        # Attachments: the WHOLE set is preflighted before the first
        # upload (paths, sizes, filenames, auth and space consistency),
        # then uploaded sequentially in the caller's order — parallel
        # uploads would leave no rollback story when one fails. The
        # preflight is identity-independent and runs BEFORE identity
        # resolution so deterministic local rejections (e.g. cross-Space
        # UploadedAttachment) never depend on which credentials exist.
        attached: list[Attachment] = []
        if attachments:
            for item in attachments:
                if isinstance(item, UploadedAttachment):
                    # Canonicalize before comparing so a bare space id
                    # stored on a hand-built UploadedAttachment is not
                    # falsely rejected as a different space.
                    if _canonical_space(item.space) != parent:
                        raise ChatAPIError(
                            "UploadedAttachment is scoped to space "
                            f"{item.space!r}; cannot send it in {parent!r}"
                        )
                else:
                    item.validate()  # re-check path/file state, no reads
        if has_attachments:
            # Capability preflight against the EFFECTIVE (USER) identity:
            # the final messages.create is USER-authenticated, so APP
            # capabilities must not satisfy it. Fail locally, before any
            # media I/O, when the USER identity or its scopes are absent.
            user_credentials = await self._resolve_user_credentials_async()
            if user_credentials is None:
                raise CapabilityNotSupported(
                    "Sending message attachments requires USER authentication "
                    "for both media.upload and messages.create. Configure "
                    "user_credentials_provider=... — UserCredentialsProvider, "
                    "or DelegatedUserCredentialsProvider for domain-wide "
                    "delegation."
                )
            if self._classify(user_credentials) is AuthMode.APP:
                raise CapabilityNotSupported(
                    "the user credentials provider returned service-account "
                    "credentials; Google treats attachment sends as "
                    "USER-authenticated calls — use "
                    "DelegatedUserCredentialsProvider (with_subject) to "
                    "impersonate a Workspace user through domain-wide delegation."
                )
            user_capabilities = OutboundCapabilities.resolve(
                AuthMode.USER,
                scopes=_credential_scopes(AuthMode.USER, user_credentials),
            )
            user_capabilities.require(OutboundCapability.MESSAGE_CREATE)
            if attachments is not None and any(
                isinstance(item, InputFile) for item in attachments
            ):
                user_capabilities.require(OutboundCapability.ATTACHMENT_UPLOAD)
        else:
            capabilities = await self._capabilities_async()
            if capabilities is not None:
                capabilities.require(OutboundCapability.MESSAGE_CREATE)
        if accessory_widgets:
            # Documented Google rule: accessory widgets require APP auth.
            if mode is not AuthMode.APP:
                raise CapabilityNotSupported(
                    "Accessory widgets require app authentication (chat.bot)."
                )
        if attachments:
            for item in attachments:
                if isinstance(item, UploadedAttachment):
                    attached.append(
                        Attachment(
                            attachment_data_ref=_attachment_data_ref_proto(
                                item.attachment_data_ref
                            )
                        )
                    )
                else:
                    uploaded = await self.upload_attachment(
                        parent, item, timeout=timeout
                    )
                    attached.append(
                        Attachment(
                            attachment_data_ref=_attachment_data_ref_proto(
                                uploaded.attachment_data_ref
                            )
                        )
                    )
        message = Message(text=text or "")
        for entry in attached:
            message.attachment.append(entry)
        if viewer is not None:
            message.private_message_viewer = ProtoUser(name=viewer)
        if card is not None:
            message.cards_v2.append(CardWithId(card_id="card", card=card.to_proto()))
        if accessory_widgets:
            for widget in accessory_widgets:
                message.accessory_widgets.append(widget.to_proto())
        # Live dogfooding finding: replying into an existing thread needs
        # thread.name in the "spaces/.../threads/..." resource form, while
        # an app can CREATE its own thread with an app-defined threadKey —
        # the client must pass both through (threadKey was dropped).
        has_thread = thread is not None and (
            thread.name is not None or thread.thread_key is not None
        )
        if thread is not None and thread.name is not None:
            message.thread.name = thread.name
        if thread is not None and thread.thread_key is not None:
            message.thread.thread_key = thread.thread_key
        effective_option = reply_option if has_thread else MessageReplyOption.NEW_THREAD
        request = CreateMessageRequest(
            parent=parent,
            message=message,
            request_id=request_id,
            message_id=message_id,
            message_reply_option=effective_option.to_proto(),
        )
        if notify in ("force", "silent"):
            notification = CreateMessageNotificationOptions.NotificationType
            options = CreateMessageNotificationOptions()
            notification_type: int = (
                notification.NOTIFICATION_TYPE_FORCE_NOTIFY
                if notify == "force"
                else notification.NOTIFICATION_TYPE_SILENT
            )
            options.notification_type = cast(Any, notification_type)
            request.create_message_notification_options = options
        try:
            client = (
                await self._get_user_client_async()
                if has_attachments
                else await self._get_client_async()
            )
            return await client.create_message(request=request, timeout=timeout)
        except api_core_exceptions.GoogleAPICallError as error:
            raise wrap_api_error(error) from error

    async def upload_attachment(
        self,
        space: SpaceRef | str,
        file: InputFile,
        *,
        timeout: float | None = None,
    ) -> UploadedAttachment:
        """Upload a local file as a Chat attachment (USER auth only).

        media.upload requires user authentication, so the upload uses the
        Bot's USER identity: ``user_credentials_provider`` on a
        dual-identity Bot, or a single USER-classified credential set.
        A Bot without any user identity is rejected locally, before any
        media I/O. All deterministic constraints (file kind, size,
        filename) are validated before the network call; the synchronous
        REST client runs off the event loop.

        Attribution note: a USER-authenticated call acts on behalf of
        that user — this Google auth semantic is never hidden.
        """
        user_credentials = await self._resolve_user_credentials_async()
        if user_credentials is None:
            raise CapabilityNotSupported(
                "media.upload requires user authentication, but this Bot "
                "has no user identity; pass user_credentials_provider=... "
                "to Bot(...) — UserCredentialsProvider, or "
                "DelegatedUserCredentialsProvider for domain-wide delegation."
            )
        if self._classify(user_credentials) is AuthMode.APP:
            raise CapabilityNotSupported(
                "the user credentials provider returned service-account "
                "credentials; Google treats media.upload as a "
                "USER-authenticated call — use "
                "DelegatedUserCredentialsProvider (with_subject) to "
                "impersonate a Workspace user through domain-wide delegation."
            )
        user_capabilities = OutboundCapabilities.resolve(
            AuthMode.USER,
            scopes=_credential_scopes(AuthMode.USER, user_credentials),
        )
        user_capabilities.require(OutboundCapability.ATTACHMENT_UPLOAD)
        parent = _canonical_space(space)
        file.validate()
        from chattice.media._rest import upload_media

        data = await asyncio.to_thread(file.read)
        response = await asyncio.to_thread(
            upload_media,
            user_credentials,
            parent,
            file.filename,
            file.content_type,
            data,
            timeout,
        )
        data_ref = response.get("attachmentDataRef")
        if not isinstance(data_ref, dict):
            raise ChatAPIError(
                f"media.upload returned no attachmentDataRef; got {response!r}"
            )
        return UploadedAttachment(
            space=parent,
            filename=file.filename,
            attachment_data_ref=dict(data_ref),
            raw=dict(response),
        )

    async def download_attachment(
        self,
        attachment: AttachmentRef | str,
        *,
        destination: str | Path | None = None,
        timeout: float | None = None,
    ) -> bytes | Path:
        """Download Chat-uploaded attachment data (USER or APP auth).

        A string is treated as an ``attachmentDataRef.resourceName``.
        Drive-backed references are rejected locally with an actionable
        message: media.download serves Chat-uploaded content only, Drive
        files need the Google Drive API.
        """
        if isinstance(attachment, AttachmentRef):
            if attachment.is_drive:
                raise ChatAPIError(
                    "Drive-backed attachments cannot be downloaded through "
                    "Chat media.download; use the Google Drive API with "
                    "this attachment's drive_file_id."
                )
            resource_name = attachment.resource_name
        else:
            resource_name = attachment
        if not resource_name:
            raise ChatAPIError(
                "attachment has no attachmentDataRef.resourceName; nothing to download"
            )
        # MEDIA_DOWNLOAD accepts USER or APP: prefer the APP identity,
        # fall back to the USER identity when the app credentials lack
        # the download scopes (or are absent entirely).
        credentials = await self._resolve_credentials_async()
        if credentials is not None:
            capabilities = await self._capabilities_async()
            if capabilities is not None:
                try:
                    capabilities.require(OutboundCapability.MEDIA_DOWNLOAD)
                except CapabilityNotSupported:
                    credentials = await self._user_credentials_for_download()
        else:
            credentials = await self._user_credentials_for_download()
        from chattice.media._rest import download_media

        def _run() -> bytes | Path:
            data = download_media(credentials, resource_name, timeout)
            if destination is None:
                return data
            path = Path(destination)
            path.write_bytes(data)
            return path

        return await asyncio.to_thread(_run)

    async def _user_credentials_for_download(self) -> Credentials:
        user = await self._resolve_user_credentials_async()
        if user is None or self._classify(user) is not AuthMode.USER:
            raise CapabilityNotSupported(
                "media.download requires app credentials (chat.bot) or user "
                "credentials (chat.messages.readonly/chat.messages); this Bot "
                "has neither — pass app_credentials_provider=... or "
                "user_credentials_provider=... to Bot(...)."
            )
        capabilities = OutboundCapabilities.resolve(
            AuthMode.USER, scopes=_credential_scopes(AuthMode.USER, user)
        )
        capabilities.require(OutboundCapability.MEDIA_DOWNLOAD)
        return user

    async def get_attachment(
        self, name: str, *, timeout: float | None = None
    ) -> AttachmentRef:
        """Fetch attachment metadata (APP auth + chat.bot only).

        Uses the GAPIC ``get_attachment``
        (``spaces.messages.attachments.get``) and returns a typed
        :class:`AttachmentRef`. Symmetric media flow:
        ``upload_attachment`` → ``get_attachment`` → ``download_attachment``.
        """
        mode = await self._auth_mode_async()
        if mode is not AuthMode.APP:
            raise CapabilityNotSupported(
                "attachment metadata (spaces.messages.attachments.get) "
                "requires app authentication (chat.bot)."
            )
        capabilities = await self._capabilities_async()
        if capabilities is not None:
            capabilities.require(OutboundCapability.ATTACHMENT_METADATA_GET)
        try:
            proto = await (await self._get_client_async()).get_attachment(
                name=name, timeout=timeout
            )
        except api_core_exceptions.GoogleAPICallError as error:
            raise wrap_api_error(error) from error
        return AttachmentRef.from_proto(proto)

    async def get_message(self, name: str, *, timeout: float | None = None) -> Message:
        try:
            return await (await self._get_client_async()).get_message(
                name=name, timeout=timeout
            )
        except api_core_exceptions.GoogleAPICallError as error:
            raise wrap_api_error(error) from error

    async def update_message(
        self,
        name: str,
        text: str | None = None,
        *,
        card: Card | None = None,
        timeout: float | None = None,
    ) -> Message:
        capabilities = await self._capabilities_async()
        if capabilities is not None:
            capabilities.require(OutboundCapability.MESSAGE_UPDATE)
        message = Message(name=name)
        update_paths: list[str] = []
        if text is not None:
            message.text = text
            update_paths.append("text")
        if card is not None:
            message.cards_v2.append(CardWithId(card_id="card", card=card.to_proto()))
            # Live dogfooding finding: the gRPC update_mask takes the PROTO
            # field name cards_v2 — "cardsV2" is the REST JSON spelling and
            # the API rejects it with "Unsupported path name in message
            # field mask". The name field itself never goes in the mask.
            update_paths.append("cards_v2")
        if not update_paths:
            raise ChatAPIError("update_message requires text or card")
        update_mask = field_mask_pb2.FieldMask(paths=update_paths)
        try:
            return await (await self._get_client_async()).update_message(
                message=message, update_mask=update_mask, timeout=timeout
            )
        except api_core_exceptions.GoogleAPICallError as error:
            raise wrap_api_error(error) from error

    async def delete_message(self, name: str, *, timeout: float | None = None) -> None:
        try:
            await (await self._get_client_async()).delete_message(
                name=name, timeout=timeout
            )
        except api_core_exceptions.GoogleAPICallError as error:
            raise wrap_api_error(error) from error

    async def get_space(self, name: str, *, timeout: float | None = None) -> Space:
        try:
            return await (await self._get_client_async()).get_space(
                name=name, timeout=timeout
            )
        except api_core_exceptions.GoogleAPICallError as error:
            raise wrap_api_error(error) from error


__all__ = ["Bot", "MessageReplyOption"]
