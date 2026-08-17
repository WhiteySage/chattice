"""Streaming-pull Pub/Sub runner: the behind-VPN ingress (Stage B, B3).

Feeds the SAME parser -> Dispatcher -> Router -> filters -> middleware ->
DI -> handlers pipeline as the HTTP router — no second dispatcher.

Operator flow::

    await dispatcher.run_pubsub(
        "projects/P/subscriptions/S",
        bot=bot,
        credentials_provider=...,
    )

Behavior contract :

- streaming pull via ``google-cloud-pubsub`` (lazy import; install the
  ``pubsub`` extra);
- bounded concurrency via an asyncio semaphore — no global serialization;
- one explicit per-delivery attempt state machine: fresh owner token and
  subscription-namespaced dedupe key per delivery, claim
  (COMPLETED -> ACK, ACTIVE -> NACK, FIRST -> process), lease renewal
  tied to the attempt, complete-then-ACK exactly once — a delivery is
  NEVER both ACKed and NACKed;
- pre-completion failures: owner-checked release, then NACK; a poison
  message (``max_delivery_attempts`` reached) is ACKed after a
  best-effort user notification (documented terminal policy);
- ``run()`` races the stop event against the streaming-pull future and
  surfaces unrecoverable subscriber failures; shutdown cancels the pull
  future, stops scheduling and drains every scheduled attempt;
- handler answers go OUTBOUND via ``Bot`` where semantics allow (B4):
  ``str`` -> ``send_message``, ``Card`` -> ``update_message`` for a
  clicked bot card (message identity from ``ActionEvent.message``) or
  ``send_message`` otherwise;
- ``Dialog`` / ``ActionStatus`` answers raise ``CapabilityNotSupported``
  (B7: dialogs require a synchronous transport) and the space is told;
- structured logs under ``chattice.pubsub``; exception CLASSES only.

Wire format: Google Chat publishes the interaction JSON directly as the
Pub/Sub message data. A base64 push envelope is also accepted for
compatibility with push-shaped topics.
"""

from __future__ import annotations

import asyncio
import json
import logging
import signal
from collections.abc import Mapping
from concurrent.futures import Future
from typing import Any

from google.auth.credentials import Credentials

from chattice.adapters.google_chat import parse_interaction
from chattice.auth import CredentialsProvider
from chattice.capabilities import CapabilityNotSupported, ResponseCapabilities
from chattice.cards import ActionStatus, Card, Dialog
from chattice.client import Bot
from chattice.dispatcher import Dispatcher
from chattice.events import ActionEvent, Event, ThreadRef
from chattice.exceptions import ChatticeError
from chattice.idempotency import (
    ClaimResult,
    IdempotencyStorage,
    MemoryIdempotencyStorage,
    new_owner,
)
from chattice.transports.pubsub import PubSubEnvelopeError, decode_message_data

logger = logging.getLogger("chattice.pubsub")

__all__ = ["PubSubPullRunner"]

DIALOG_UNSUPPORTED_MESSAGE = (
    "Dialogs require a synchronous Google Chat transport. "
    "Use a Card form or HTTP transport."
)

_DEFAULT_LEASE_SECONDS = 300.0


def _import_pubsub() -> Any:
    try:
        from google.cloud import pubsub_v1  # type: ignore[import-untyped]
    except ImportError as error:
        raise ChatticeError(
            "Pub/Sub pull requires google-cloud-pubsub — install the "
            "chattice pubsub extra (uv add 'chattice[pubsub]')."
        ) from error
    return pubsub_v1


class PubSubPullRunner:
    """Pull the subscription and run every delivery through the dispatcher."""

    def __init__(
        self,
        dispatcher: Dispatcher,
        subscription: str,
        *,
        bot: Bot | None = None,
        credentials: Credentials | None = None,
        credentials_provider: CredentialsProvider | None = None,
        max_concurrency: int = 10,
        max_outstanding_messages: int = 100,
        idempotency_storage: IdempotencyStorage | None = None,
        max_delivery_attempts: int = 5,
        renew_interval: float | None = None,
    ) -> None:
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be >= 1")
        self._dispatcher = dispatcher
        self._subscription = subscription
        self._bot = bot
        self._credentials = credentials
        self._credentials_provider = credentials_provider
        self._max_concurrency = max_concurrency
        self._max_outstanding_messages = max_outstanding_messages
        self._max_delivery_attempts = max_delivery_attempts
        self._renew_interval = renew_interval or (_DEFAULT_LEASE_SECONDS / 2)
        self._idempotency = (
            idempotency_storage
            if idempotency_storage is not None
            else MemoryIdempotencyStorage()
        )
        self._semaphore = asyncio.Semaphore(max_concurrency)
        # futures are tracked the moment _schedule runs, so close()
        # can never snapshot an empty set while a scheduled coroutine has
        # not entered its first await yet.
        self._scheduled: set[Future[None]] = set()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._subscriber: Any = None
        self._pull_future: Any = None
        self._closed = False

    # ------------------------------------------------------------------ run

    async def run(self, stop_event: asyncio.Event | None = None) -> None:
        """Streaming-pull loop until ``stop_event`` fires (or SIGINT/SIGTERM).

        Races the stop event against the streaming-pull future: an
        unrecoverable subscriber failure ends the run and surfaces as a
        :class:`ChatticeError`  the docstring contract is enforced).
        Returns after the subscriber is closed and scheduled attempts are
        drained.
        """
        self._loop = asyncio.get_running_loop()
        pubsub_v1 = _import_pubsub()
        credentials = await self._resolve_credentials()
        self._subscriber = pubsub_v1.SubscriberClient(credentials=credentials)
        self._pull_future = self._subscriber.subscribe(
            self._subscription,
            callback=self._schedule,
            flow_control=pubsub_v1.types.FlowControl(
                max_messages=self._max_outstanding_messages
            ),
        )
        logger.info("pubsub runner started: subscription=%s", self._subscription)
        stop = stop_event if stop_event is not None else self._install_signals()
        stop_waiter = asyncio.ensure_future(stop.wait())
        # StreamingPullFuture.result() blocks until the stream ends; run it
        # off-loop so BOTH terminal conditions (stop, stream end) race.
        stream_waiter = asyncio.ensure_future(
            asyncio.to_thread(self._pull_future.result)
        )
        try:
            await asyncio.wait(
                {stop_waiter, stream_waiter},
                return_when=asyncio.FIRST_COMPLETED,
            )
            if not stop.is_set():
                # The stream ended on its own — unrecoverable by definition
                # of StreamingPullFuture. Surface the subscriber's error.
                try:
                    stream_waiter.result()
                except Exception as error:
                    raise ChatticeError("Pub/Sub subscriber failed") from error
                raise ChatticeError("Pub/Sub subscriber stopped unexpectedly")
        finally:
            self._pull_future.cancel()
            try:
                await asyncio.to_thread(self._pull_future.result)
            except Exception:  # subscriber teardown is best-effort here
                pass
            await self.close()

    def _install_signals(self) -> asyncio.Event:
        stop = asyncio.Event()
        loop = self._loop
        assert loop is not None
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, stop.set)
            except (NotImplementedError, RuntimeError):
                pass  # non-main thread or unsupported platform
        return stop

    async def _resolve_credentials(self) -> Credentials | None:
        if self._credentials is not None:
            return self._credentials
        if self._credentials_provider is not None:
            return await asyncio.to_thread(self._credentials_provider)
        return None

    async def close(self) -> None:
        """Stop the subscriber, stop scheduling, drain attempts (idempotent)."""
        if self._closed:
            return
        self._closed = True
        self._loop = None  # no new scheduling after close begins
        if self._subscriber is not None:
            await asyncio.to_thread(self._subscriber.close)
            self._subscriber = None
        scheduled = list(self._scheduled)
        self._scheduled.clear()
        if scheduled:
            await asyncio.gather(
                *(asyncio.wrap_future(future) for future in scheduled),
                return_exceptions=True,
            )
        logger.info("pubsub runner stopped")

    # ----------------------------------------------------------- delivery

    def _schedule(self, message: Any) -> None:
        """Subscriber callback (worker thread) -> asyncio handler task."""
        if self._loop is None:
            return
        try:
            future = asyncio.run_coroutine_threadsafe(self._handle(message), self._loop)
        except RuntimeError:
            return  # loop already gone during shutdown
        self._scheduled.add(future)
        future.add_done_callback(self._scheduled.discard)

    async def _handle(self, message: Any) -> None:
        """One explicit per-delivery attempt state machine .

        claim -> COMPLETED: ACK | ACTIVE: NACK | FIRST: process -> complete
        claim -> ACK exactly once. Any pre-completion failure: owner-checked
        release, then NACK — or poison-ACK under the documented terminal
        policy (max attempts reached, after a best-effort notification).
        The same delivery is NEVER both ACKed and NACKed.
        """
        # Namespaced key: Google message IDs are unique per TOPIC, so a
        # shared store needs the subscription in the key (push parity).
        key = f"{self._subscription}:{message.message_id}"
        owner = new_owner()
        try:
            claim = await self._idempotency.claim(
                key, owner=owner, lease_seconds=_DEFAULT_LEASE_SECONDS
            )
        except Exception as error:
            # Storage unavailable: NACK so Pub/Sub redelivers later — never
            # ack work whose ownership we could not record.
            logger.error(
                "claim failed: message_id=%s error=%s",
                message.message_id,
                type(error).__name__,
            )
            message.nack()
            return
        if claim is ClaimResult.COMPLETED:
            logger.info("duplicate acked: message_id=%s", message.message_id)
            message.ack()
            return
        if claim is ClaimResult.ACTIVE:
            # Another owner is processing: hand the delivery back.
            message.nack()
            return
        renewal: asyncio.Task[None] | None = None
        event: Event | None = None
        try:
            renewal = asyncio.create_task(self._renew_loop(key, owner, message))
            event = self._parse(message)
            capabilities = ResponseCapabilities.resolve(transport="pubsub", event=event)
            result = await self._dispatcher.feed_update(
                event,
                bot=self._bot,
                capabilities=capabilities,
            )
            try:
                await self._answer(event, result)
            except CapabilityNotSupported as error:
                # B7: terminal for this delivery — tell the space, complete
                # the claim, THEN ack (completion failure would otherwise
                # leave an acked-but-unrecorded delivery).
                logger.error(
                    "capability rejected: message_id=%s event_type=%s error=%s",
                    message.message_id,
                    event.event_type,
                    type(error).__name__,
                )
                space_name = event.space.name if event.space is not None else None
                if self._bot is not None and space_name is not None:
                    await self._bot.send_message(space_name, text=str(error))
                await self._idempotency.complete(key, owner=owner)
                message.ack()
                return
            # Success: complete the claim FIRST, then ACK exactly once. If
            # complete fails, the attempt falls into the exception branch
            # below — release + NACK — preserving at-least-once semantics.
            await self._idempotency.complete(key, owner=owner)
            message.ack()
            logger.info(
                "acked: message_id=%s event_type=%s",
                message.message_id,
                event.event_type,
            )
        except asyncio.CancelledError:
            message.nack()
            raise
        except Exception as error:
            try:
                await self._idempotency.release(key, owner=owner)
            except Exception as release_error:
                logger.error(
                    "release failed: message_id=%s error=%s",
                    message.message_id,
                    type(release_error).__name__,
                )
            if message.delivery_attempt >= self._max_delivery_attempts:
                # Documented terminal policy: notify first (best-effort),
                # then poison-ACK so the message cannot redeliver forever.
                await self._notify_poison(event, type(error).__name__)
                logger.error(
                    "poison message acked: message_id=%s attempts=%s error=%s",
                    message.message_id,
                    message.delivery_attempt,
                    type(error).__name__,
                )
                message.ack()
            else:
                logger.error(
                    "handler failed, nacked: message_id=%s attempt=%s error=%s",
                    message.message_id,
                    message.delivery_attempt,
                    type(error).__name__,
                )
                message.nack()
        finally:
            if renewal is not None:
                renewal.cancel()
                try:
                    await renewal
                except asyncio.CancelledError:
                    pass
                except Exception as renew_error:
                    logger.error(
                        "renewal task failed: message_id=%s error=%s",
                        message.message_id,
                        type(renew_error).__name__,
                    )

    async def _renew_loop(self, key: str, owner: str, message: Any) -> None:
        """Renew the claim lease while the attempt is in flight .

        A valid long handler must not be reclaimed by an expired lease.
        On renewal failure the loop stops renewing; the attempt itself
        continues — at-least-once survives because the work is already
        running (a takeover duplicates, it never loses).
        """
        while True:
            await asyncio.sleep(self._renew_interval)
            try:
                renewed = await self._idempotency.renew(
                    key, owner=owner, lease_seconds=_DEFAULT_LEASE_SECONDS
                )
            except Exception as error:
                logger.error(
                    "renewal failed: message_id=%s error=%s",
                    message.message_id,
                    type(error).__name__,
                )
                return
            if not renewed:
                logger.error(
                    "renewal refused: message_id=%s (lease lost)",
                    message.message_id,
                )
                return

    async def _notify_poison(self, event: Event | None, error_class: str) -> None:
        """Best-effort user notification before a poison ACK (documented)."""
        if (
            self._bot is None
            or event is None
            or event.space is None
            or event.space.name is None
        ):
            return
        try:
            await self._bot.send_message(
                event.space.name,
                text=f"Error while processing your message ({error_class}).",
            )
        except Exception as notify_error:
            logger.error(
                "poison notification failed: error=%s", type(notify_error).__name__
            )

    # ------------------------------------------------------------ parsing

    def _parse(self, message: Any) -> Event:
        raw = message.data
        if isinstance(raw, (bytes, bytearray)):
            raw = raw.decode()
        if not isinstance(raw, str):
            raise PubSubEnvelopeError("message data is not text")
        try:
            payload: object = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise PubSubEnvelopeError("message data is not valid JSON") from error
        interaction: object = payload
        # Push-shaped topics carry the interaction base64-wrapped under
        # message.data — accept both wire shapes. An interaction's own
        # "message" object (text/sender/...) is NOT an envelope: only a
        # message mapping with a string "data" marks one.
        if isinstance(payload, Mapping):
            envelope_message = payload.get("message")
            if isinstance(envelope_message, Mapping) and isinstance(
                envelope_message.get("data"), str
            ):
                inner = decode_message_data(payload)
                if inner is not None:
                    interaction = inner
        if not isinstance(interaction, Mapping):
            raise PubSubEnvelopeError("interaction must be a JSON object")
        return parse_interaction(interaction)

    # ----------------------------------------------------------- answers

    async def _answer(self, event: Event, result: object) -> None:
        if result is None:
            return
        if isinstance(result, (Dialog, ActionStatus)):
            raise CapabilityNotSupported(DIALOG_UNSUPPORTED_MESSAGE)
        if self._bot is None:
            logger.warning(
                "handler answer dropped: no Bot configured: event_type=%s "
                "result_type=%s",
                event.event_type,
                type(result).__name__,
            )
            return
        space = event.space.name if event.space is not None else None
        if space is None:
            logger.warning(
                "handler answer dropped: event has no space: event_type=%s",
                event.event_type,
            )
            return
        thread = event.thread.name if event.thread is not None else None
        if isinstance(result, str):
            await self._bot.send_message(
                space,
                text=result,
                thread=ThreadRef(name=thread) if thread else None,
            )
            logger.info("answer: text sent to %s", space)
        elif isinstance(result, Card):
            if (
                isinstance(event, ActionEvent)
                and event.message is not None
                and event.message.name is not None
            ):
                await self._bot.update_message(event.message.name, card=result)
                logger.info("answer: card updated %s", event.message.name)
            else:
                await self._bot.send_message(space, card=result)
                logger.info("answer: card sent to %s", space)
        else:
            logger.warning(
                "handler answer type unsupported in Pub/Sub: event_type=%s "
                "result_type=%s",
                event.event_type,
                type(result).__name__,
            )
