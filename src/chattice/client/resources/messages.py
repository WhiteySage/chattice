# ruff: noqa: ASYNC109 — timeout kwarg mirrors the gapic client call convention
"""Message resource client: explicit-identity message operations (ADR-012).

``create``/``update`` carry the full curated surface (validation,
assets, attachments, thread options).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, cast

from google.apps.chat_v1.types.attachment import Attachment
from google.apps.chat_v1.types.markup_syntax import MarkupSyntax
from google.apps.chat_v1.types.message import (
    CardWithId,
    CreateMessageNotificationOptions,
    CreateMessageRequest,
    ListMessagesRequest,
    Message,
)
from google.apps.chat_v1.types.user import User as ProtoUser
from google.protobuf import field_mask_pb2  # type: ignore[import-untyped]

from chattice.auth import AuthMode
from chattice.capabilities import CapabilityNotSupported
from chattice.capabilities.operations import Operation
from chattice.cards import AccessoryWidget, Card
from chattice.cards._assets import resolve_card_assets, validate_card_assets
from chattice.client._names import _canonical_space, _canonical_user
from chattice.client._proto_helpers import _attachment_data_ref_proto
from chattice.client.config import RequestConfig
from chattice.client.errors import ChatAPIError
from chattice.client.executor import OperationExecutor
from chattice.client.paging import Pager
from chattice.client.resources.base import ResourceClient, _effective_config
from chattice.events import SpaceRef, ThreadRef, UserRef
from chattice.media import InputFile, UploadedAttachment

__all__ = ["Messages"]


class Messages(ResourceClient):
    """Curated message surface bound to one identity (ADR-012)."""

    async def get(
        self,
        name: str,
        *,
        timeout: float | None = None,
        config: RequestConfig | None = None,
    ) -> Message:
        """Get one message by canonical ``spaces/.../messages/...`` name."""
        effective = _effective_config(config, timeout)
        return cast(
            Message,
            await self._executor.execute(
                Operation.MESSAGES_GET,
                identity=self._identity,
                call=lambda client, cfg: client.get_message(
                    name=name, **OperationExecutor.gapic_kwargs(cfg)
                ),
                config=effective,
            ),
        )

    async def create(
        self,
        space: SpaceRef | str,
        text: str | None = None,
        *,
        markup_syntax: MarkupSyntax | None = None,
        thread: ThreadRef | None = None,
        reply_option: object = None,
        request_id: str | None = None,
        message_id: str | None = None,
        timeout: float | None = None,
        accessory_widgets: Sequence[AccessoryWidget] | None = None,
        card: Card | None = None,
        notify: str | None = None,
        private_to: UserRef | str | None = None,
        attachments: Sequence[InputFile | UploadedAttachment] | None = None,
    ) -> Message:
        """Create a message with THIS identity (APP or USER — caller's choice).

        All deterministic constraints are validated before any client
        work; attachment sends require the USER identity and run the
        whole send (upload and create) on the USER client.
        """
        validate_card_assets(card, self._bot._asset_publisher)
        has_attachments = bool(attachments)
        # The EFFECTIVE identity guards:
        # USER for attachment sends, the bot's actual primary identity
        # otherwise (never the resource's declared identity alone).
        actual_mode = (
            AuthMode.USER if has_attachments else await self._bot._auth_mode_async()
        )
        if has_attachments:
            # Combination guards first: identity-independent, must reject
            # before any identity resolution.
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
            if self._identity is not AuthMode.USER:
                raise CapabilityNotSupported(
                    "attachment messages are USER-authenticated; call "
                    "bot.user.messages.create(...) to send attachments."
                )
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
            if actual_mode is not AuthMode.APP:
                raise CapabilityNotSupported(
                    "createMessageNotificationOptions requires app "
                    "authentication (chat.bot)."
                )
        viewer: str | None = None
        if private_to is not None:
            viewer = _canonical_user(private_to)
            if actual_mode is not AuthMode.APP:
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
        if card is not None and actual_mode is AuthMode.USER:
            raise CapabilityNotSupported(
                "User-auth card creation is a Google Developer Preview "
                "(PreviewFeature.USER_AUTH_CARDS); use app auth or "
                "bot.raw.app() for preview surfaces."
            )
        parent = _canonical_space(space)
        attached: list[Attachment] = []
        attachment_list = attachments or ()
        if attachment_list:
            for item in attachment_list:
                if isinstance(item, UploadedAttachment):
                    if _canonical_space(item.space) != parent:
                        raise ChatAPIError(
                            "UploadedAttachment is scoped to space "
                            f"{item.space!r}; cannot send it in {parent!r}"
                        )
                else:
                    item.validate()
        if accessory_widgets and actual_mode is not AuthMode.APP:
            raise CapabilityNotSupported(
                "Accessory widgets require app authentication (chat.bot)."
            )
        if actual_mode is AuthMode.NONE:
            raise CapabilityNotSupported(
                "MESSAGE_CREATE is not supported in this configuration. "
                "Creating messages requires app or user authentication and "
                "an admissible OAuth scope."
            )
        if has_attachments:
            # Fail locally BEFORE any media I/O (upload) when the USER
            # identity or its scopes are absent — media work must never
            # run for a send that will be rejected.
            user_credentials = await self._bot._resolve_user_credentials_async()
            if user_credentials is None:
                raise CapabilityNotSupported(
                    "Sending message attachments requires USER authentication "
                    "for both media.upload and messages.create. Configure "
                    "user_credentials_provider=... — UserCredentialsProvider, "
                    "or DelegatedUserCredentialsProvider for domain-wide "
                    "delegation."
                )
            if self._bot._classify(user_credentials) is AuthMode.APP:
                raise CapabilityNotSupported(
                    "the user credentials provider returned service-account "
                    "credentials; Google treats attachment sends as "
                    "USER-authenticated calls — use "
                    "DelegatedUserCredentialsProvider (with_subject) to "
                    "impersonate a Workspace user through domain-wide delegation."
                )
            await self._preflight(Operation.MESSAGES_CREATE)
            if any(isinstance(item, InputFile) for item in attachment_list):
                await self._preflight(Operation.MEDIA_UPLOAD)
        resolved_card = (
            await resolve_card_assets(card, self._bot._asset_publisher)
            if card is not None
            else None
        )
        if attachments:
            for item in attachment_list:
                if isinstance(item, UploadedAttachment):
                    attached.append(
                        Attachment(
                            attachment_data_ref=_attachment_data_ref_proto(
                                item.attachment_data_ref
                            )
                        )
                    )
                else:
                    uploaded = await self._bot.user.attachments.upload(
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
        if markup_syntax is not None:
            message.markup_syntax = markup_syntax
        for entry in attached:
            message.attachment.append(entry)
        if viewer is not None:
            message.private_message_viewer = ProtoUser(name=viewer)
        if resolved_card is not None:
            message.cards_v2.append(
                CardWithId(card_id="card", card=resolved_card.to_proto())
            )
        if accessory_widgets:
            for widget in accessory_widgets:
                message.accessory_widgets.append(widget.to_proto())
        has_thread = thread is not None and (
            thread.name is not None or thread.thread_key is not None
        )
        if thread is not None and thread.name is not None:
            message.thread.name = thread.name
        if thread is not None and thread.thread_key is not None:
            message.thread.thread_key = thread.thread_key
        # NEW_THREAD when no thread context; otherwise the caller's
        # reply option (GAPIC enum value) passes through.

        effective_option = (
            reply_option
            if reply_option is not None and has_thread
            else (
                CreateMessageRequest.MessageReplyOption.MESSAGE_REPLY_OPTION_UNSPECIFIED
            )
        )
        request = CreateMessageRequest(
            parent=parent,
            message=message,
            request_id=request_id,
            message_id=message_id,
            message_reply_option=effective_option,
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
        effective = _effective_config(None, timeout)
        return cast(
            Message,
            await self._executor.execute(
                Operation.MESSAGES_CREATE,
                identity=self._identity,
                call=lambda client, cfg: client.create_message(
                    request=request, **OperationExecutor.gapic_kwargs(cfg)
                ),
                config=effective,
            ),
        )

    async def update(
        self,
        name: str,
        text: str | None = None,
        *,
        card: Card | None = None,
        timeout: float | None = None,
        config: RequestConfig | None = None,
    ) -> Message:
        """Update text and/or card of one message with THIS identity."""
        if text is None and card is None:
            raise ChatAPIError("update_message requires text or card")
        actual_mode = await self._bot._auth_mode_async()
        if actual_mode is AuthMode.NONE:
            raise CapabilityNotSupported(
                "MESSAGE_UPDATE is not supported in this configuration. "
                "Updating messages requires app or user authentication and "
                "an admissible OAuth scope."
            )
        validate_card_assets(card, self._bot._asset_publisher)
        message = Message(name=name)
        update_paths: list[str] = []
        if text is not None:
            message.text = text
            update_paths.append("text")
        if card is not None:
            resolved_card = await resolve_card_assets(card, self._bot._asset_publisher)
            message.cards_v2.append(
                CardWithId(card_id="card", card=resolved_card.to_proto())
            )
            update_paths.append("cards_v2")
        update_mask = field_mask_pb2.FieldMask(paths=update_paths)
        effective = _effective_config(config, timeout)
        return cast(
            Message,
            await self._executor.execute(
                Operation.MESSAGES_UPDATE,
                identity=self._identity,
                call=lambda client, cfg: client.update_message(
                    message=message,
                    update_mask=update_mask,
                    **OperationExecutor.gapic_kwargs(cfg),
                ),
                config=effective,
            ),
        )

    async def list(
        self,
        *,
        parent: str,
        page_size: int | None = None,
        timeout: float | None = None,
        config: RequestConfig | None = None,
    ) -> Pager[Message]:
        """List messages of one space, one page at a time."""
        effective = _effective_config(config, timeout)
        request = ListMessagesRequest(parent=parent)
        if page_size is not None:
            request.page_size = page_size

        async def fetch() -> object:
            return await self._executor.execute(
                Operation.MESSAGES_LIST,
                identity=self._identity,
                call=lambda client, cfg: client.list_messages(
                    request=request, **OperationExecutor.gapic_kwargs(cfg)
                ),
                config=effective,
            )

        return Pager(fetch=fetch)

    async def delete(
        self,
        name: str,
        *,
        timeout: float | None = None,
        config: RequestConfig | None = None,
    ) -> None:
        """Delete one message by canonical name."""
        effective = _effective_config(config, timeout)
        await self._executor.execute(
            Operation.MESSAGES_DELETE,
            identity=self._identity,
            call=lambda client, cfg: client.delete_message(
                name=name, **OperationExecutor.gapic_kwargs(cfg)
            ),
            config=effective,
        )
