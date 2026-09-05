"""Pub/Sub push ingress: envelope -> interaction event, push verification.

The documented push envelope wraps the Chat interaction JSON in
message.data (base64). Delivery has NO synchronous response channel —
the push router acks with 2xx and ignores handler return values.

Authenticated Pub/Sub push sends an OIDC ID token from the configured
push service account in the Authorization header
(https://cloud.google.com/pubsub/docs/authenticate-push-subscriptions);
``GooglePubSubVerifier`` checks signature, audience, issuer, and the
expected service-account email.
"""

from __future__ import annotations

import base64
import binascii
import json
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Protocol

from google.auth import exceptions as google_auth_exceptions
from google.auth.transport import requests as google_requests
from google.oauth2.id_token import verify_token

from chattice.adapters.google_chat import parse_interaction
from chattice.events import Event
from chattice.transports.http.errors import VerificationError
from chattice.transports.http.request import IncomingRequest
from chattice.transports.http.verifier import extract_bearer

__all__ = [
    "GooglePubSubVerifier",
    "MockPubSubVerifier",
    "PubSubEnvelopeError",
    "PubSubPushAdapter",
    "PubSubPushVerifier",
    "decode_message_data",
]

_GOOGLE_ACCOUNT_ISSUERS = ("accounts.google.com", "https://accounts.google.com")


class PubSubEnvelopeError(ValueError):
    """The Pub/Sub push envelope is malformed."""


def decode_message_data(payload: Mapping[str, object]) -> Mapping[str, object] | None:
    """Decode a Pub/Sub push envelope into its inner JSON mapping.

    Returns None when the payload is not a push envelope (e.g. a raw
    CloudEvent delivered to an HTTPS endpoint). Raises PubSubEnvelopeError
    for a malformed envelope.
    """
    message = payload.get("message")
    if message is None:
        return None
    if not isinstance(message, Mapping):
        raise PubSubEnvelopeError("Pub/Sub push payload requires a 'message' object")
    data = message.get("data")
    if not isinstance(data, str):
        raise PubSubEnvelopeError("'message.data' must be a base64 string")
    try:
        decoded = base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError) as error:
        raise PubSubEnvelopeError("'message.data' is not valid base64") from error
    try:
        inner = json.loads(decoded)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise PubSubEnvelopeError(
            "'message.data' does not contain valid JSON"
        ) from error
    if not isinstance(inner, Mapping):
        raise PubSubEnvelopeError("'message.data' must decode to a JSON object")
    return inner


class PubSubPushAdapter:
    """Decodes a documented Pub/Sub push envelope into a domain event."""

    def parse_envelope(self, payload: Mapping[str, object]) -> Event:
        """Validate the envelope, decode message.data, parse the interaction."""
        if not isinstance(payload, Mapping):
            raise PubSubEnvelopeError("Pub/Sub push payload must be a mapping")
        interaction = decode_message_data(payload)
        if interaction is None:
            raise PubSubEnvelopeError(
                "Pub/Sub push payload requires a 'message' object"
            )
        event = parse_interaction(interaction)
        # The FULL envelope (not just the inner interaction) stays in raw.
        return replace(event, raw=dict(payload))


class PubSubPushVerifier(Protocol):
    """Contract: prove that an inbound push genuinely came from Pub/Sub."""

    def verify(self, request: IncomingRequest) -> None:
        """Raise VerificationError when the request cannot be verified."""
        ...


@dataclass(frozen=True, slots=True)
class GooglePubSubVerifier:
    """Verify authenticated Pub/Sub push requests.

    The configured push endpoint receives an OIDC ID token issued for the
    Pub/Sub push service account. Signature/exp/aud are validated by
    google-auth's verify_token; the issuer must be accounts.google.com and
    the token's email claim must match ``service_account_email`` (REQUIRED:
    an audience match alone does not bind the publisher identity) with
    ``email_verified`` true.
    """

    audience: str
    service_account_email: str
    clock_skew_in_seconds: int = 10
    request: google_requests.Request | None = None

    def verify(self, incoming: IncomingRequest) -> None:
        token = extract_bearer(incoming)
        request = (
            self.request if self.request is not None else google_requests.Request()
        )
        try:
            claims = verify_token(
                token,
                request=request,
                audience=self.audience,
                clock_skew_in_seconds=self.clock_skew_in_seconds,
            )
        except google_auth_exceptions.TransportError as error:
            raise VerificationError(
                "Cannot reach Google issuer certificates"
            ) from error
        except (ValueError, google_auth_exceptions.GoogleAuthError) as error:
            raise VerificationError("Invalid bearer token") from error
        issuer = claims.get("iss")
        if issuer not in _GOOGLE_ACCOUNT_ISSUERS:
            raise VerificationError("Invalid token issuer")
        if claims.get("email_verified") is not True:
            raise VerificationError("Token email is not verified")
        if claims.get("email") != self.service_account_email:
            raise VerificationError(
                "Token service account does not match the configured push "
                "service account"
            )


class MockPubSubVerifier:
    """Accepts (or rejects) any push request; tests and local dev only."""

    def __init__(self, *, reject: bool = False) -> None:
        self._reject = reject

    def verify(self, request: IncomingRequest) -> None:
        if self._reject:
            raise VerificationError("Mock verifier rejected the request")
