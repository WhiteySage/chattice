"""Transport-neutral event dispatcher."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable, MutableMapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from google.auth.credentials import Credentials

    from chattice.auth import CredentialsProvider
    from chattice.client import Bot
    from chattice.idempotency import IdempotencyStorage

from chattice.capabilities import PreviewCapabilities, PreviewFeature
from chattice.events import (
    ActionEvent,
    AddedToSpaceEvent,
    AppHomeEvent,
    CommandEvent,
    CommandKind,
    DialogEventType,
    ErrorEvent,
    Event,
    FormSubmitEvent,
    MessageEvent,
    RemovedFromSpaceEvent,
    UnknownEvent,
    WidgetUpdatedEvent,
)
from chattice.events.references import _reset_current_bot, _set_current_bot
from chattice.exceptions import SkipHandler, StopPropagation
from chattice.filters.base import evaluate_filters
from chattice.fsm import FSMContext
from chattice.fsm.storage import BaseStorage, FSMStrategy, StorageKey
from chattice.middleware import MiddlewareLike, NextHandler
from chattice.observability import ObservabilityHooks

from .handler import HandlerObject
from .lifespan import Lifespan, LifespanResource
from .middleware import invoke_with_middleware
from .observer import EventObserver
from .router import Router

_observability_logger = logging.getLogger("chattice.observability")


@dataclass(frozen=True, slots=True)
class _DispatchOutcome:
    handled: bool = False
    stopped: bool = False
    result: object = None


class Dispatcher(Router):
    """Root router and transport-independent event feed."""

    def lifespan(self, *resources: LifespanResource) -> Lifespan:
        """An async context manager starting resources in order and closing
        them in reverse (partial-start rollback included). Plug it into
        FastAPI via ``app.router.lifespan_context = dispatcher.lifespan(...)``.
        """
        return Lifespan(*resources)

    async def run_pubsub(
        self,
        subscription: str,
        *,
        bot: Bot | None = None,
        credentials: Credentials | None = None,
        credentials_provider: CredentialsProvider | None = None,
        max_concurrency: int = 10,
        max_outstanding_messages: int = 100,
        idempotency_storage: IdempotencyStorage | None = None,
        max_delivery_attempts: int = 5,
        stop_event: asyncio.Event | None = None,
    ) -> None:
        """Streaming-pull Pub/Sub ingress (Stage B): the behind-VPN mode.

        Runs every delivery through THIS dispatcher's router/filter/
        middleware/DI pipeline. Handler answers go outbound through
        ``bot`` where semantics allow (text -> send_message, Card ->
        update_message/send_message); Dialog answers are rejected with
        ``CapabilityNotSupported`` (dialogs require the synchronous HTTP
        transport). Requires the ``chattice[pubsub]`` extra.

        Blocks until ``stop_event`` fires or SIGINT/SIGTERM; drains
        in-flight handlers before returning.
        """
        from chattice.transports.pubsub_runner import PubSubPullRunner

        runner = PubSubPullRunner(
            self,
            subscription,
            bot=bot,
            credentials=credentials,
            credentials_provider=credentials_provider,
            max_concurrency=max_concurrency,
            max_outstanding_messages=max_outstanding_messages,
            idempotency_storage=idempotency_storage,
            max_delivery_attempts=max_delivery_attempts,
        )
        await runner.run(stop_event=stop_event)

    def __init__(
        self,
        *,
        name: str = "dispatcher",
        bot: object | None = None,
        fsm_storage: BaseStorage | None = None,
        fsm_strategy: FSMStrategy = FSMStrategy.USER_IN_SPACE,
        observability_hooks: ObservabilityHooks | None = None,
        preview_features: Iterable[PreviewFeature] = (),
    ) -> None:
        super().__init__(name=name)
        self._is_dispatcher = True
        self._bot = bot
        self._fsm_storage = fsm_storage
        self._fsm_strategy = fsm_strategy
        self._observability_hooks = observability_hooks
        self._preview_capabilities = PreviewCapabilities(preview_features)

    @property
    def preview_capabilities(self) -> PreviewCapabilities:
        """The immutable Developer Preview enrollment for typed routing."""
        return self._preview_capabilities

    async def feed_update(self, event: Event, **context: object) -> object:
        """Route one domain event and return the handler result unchanged."""
        if not isinstance(event, Event):
            raise TypeError("feed_update() accepts chattice Event instances only")
        data = dict(context)
        if "bot" not in data and self._bot is not None:
            data["bot"] = self._bot
        contextual_bot = data.get("bot")
        # Configuration, not caller context, is the source of truth: a
        # feed_update() kwarg must not bypass explicit preview enrollment.
        data["preview_capabilities"] = self._preview_capabilities
        if self._fsm_storage is not None:
            data["state"] = FSMContext(
                self._fsm_storage, StorageKey.build(event, self._fsm_strategy)
            )
        hooks = self._observability_hooks
        result: object = None
        error: BaseException | None = None
        bot_token = _set_current_bot(contextual_bot)
        try:
            if hooks is not None:
                try:
                    await hooks.before_event(event, data)
                except Exception:
                    _observability_logger.error("before_event hook failed")
            try:
                outcome = await self._route_event(event, data)
                if outcome.handled:
                    result = outcome.result
            except BaseException as exc:
                error = exc
                if not isinstance(exc, Exception):
                    # CancelledError and friends bypass error routing but are
                    # still reported to the after_event hook, then re-raised.
                    raise
                error_event = ErrorEvent(
                    source_event=event,
                    exception=exc,
                    raw=event.raw,
                )
                try:
                    error_outcome = await self._route_pass(error_event, data, "error")
                except Exception as error_handler_failure:
                    if error_handler_failure is exc:
                        raise
                    raise error_handler_failure from exc
                if error_outcome.handled:
                    result = error_outcome.result
                else:
                    raise
        finally:
            try:
                if hooks is not None:
                    await hooks.after_event(event, data, result, error)
            except Exception:
                _observability_logger.error("after_event hook failed")
            finally:
                _reset_current_bot(bot_token)
        return result

    async def _route_event(
        self, event: Event, data: dict[str, object]
    ) -> _DispatchOutcome:
        for observer_name in self._specific_observer_names(event):
            outcome = await self._route_pass(event, data, observer_name)
            if outcome.handled or outcome.stopped:
                return outcome
        if not isinstance(event, ErrorEvent):
            return await self._route_pass(event, data, "event")
        return _DispatchOutcome()

    async def _route_pass(
        self,
        event: Event,
        data: dict[str, object],
        observer_name: str,
    ) -> _DispatchOutcome:
        for router, middleware in self._walk():
            observer = self._observer(router, observer_name)
            for handler in observer.handlers:
                candidate_data = dict(data)
                try:
                    matches = await evaluate_filters(
                        handler.filters, event, candidate_data
                    )
                    if not matches:
                        continue
                    result = await self._invoke(
                        handler, middleware, event, candidate_data
                    )
                except SkipHandler:
                    continue
                except StopPropagation:
                    return _DispatchOutcome(stopped=True)
                return _DispatchOutcome(handled=True, result=result)
        return _DispatchOutcome()

    @staticmethod
    def _observer(router: Router, name: str) -> EventObserver:
        observer = getattr(router, name)
        if not isinstance(observer, EventObserver):
            raise TypeError(f"Router attribute {name!r} is not an EventObserver")
        return observer

    def _specific_observer_names(self, event: Event) -> tuple[str, ...]:
        if isinstance(event, MessageEvent):
            return ("message",)
        if isinstance(event, ActionEvent):
            if event.dialog is not None and (
                event.dialog.type == DialogEventType.SUBMIT_DIALOG
            ):
                return ("dialog_submit",)
            if event.dialog is not None and (
                event.dialog.type == DialogEventType.CANCEL_DIALOG
            ):
                return ("dialog_cancel",)
            return ("action",)
        if isinstance(event, CommandEvent):
            if event.kind is CommandKind.MESSAGE_ACTION:
                if PreviewFeature.MESSAGE_ACTION not in self._preview_capabilities:
                    return ()
                return ("message_action", "command")
            if event.kind is CommandKind.SLASH_COMMAND:
                return ("slash_command", "command")
            if event.kind is CommandKind.QUICK_COMMAND:
                return ("quick_command", "command")
            return ()
        if isinstance(event, AddedToSpaceEvent):
            return ("added_to_space",)
        if isinstance(event, RemovedFromSpaceEvent):
            return ("removed_from_space",)
        if isinstance(event, WidgetUpdatedEvent):
            return ("widget_updated",)
        if isinstance(event, AppHomeEvent):
            return ("app_home",)
        if isinstance(event, FormSubmitEvent):
            return ("form_submit",)
        if isinstance(event, UnknownEvent):
            return ("unknown_event",)
        if isinstance(event, ErrorEvent):
            return ("error",)
        return ()

    @staticmethod
    async def _invoke(
        handler: HandlerObject,
        middleware: tuple[MiddlewareLike, ...],
        event: Event,
        data: MutableMapping[str, object],
    ) -> object:
        async def resolved_handler(
            resolved_event: Event, resolved_data: MutableMapping[str, object]
        ) -> object:
            return await handler.plan.invoke(resolved_event, resolved_data)

        next_handler: NextHandler = resolved_handler
        return await invoke_with_middleware(next_handler, middleware, event, data)


__all__ = ["Dispatcher"]
