"""GooglePubSubVerifier: authenticated Pub/Sub push OIDC validation."""

from __future__ import annotations

import pytest
from google.auth import exceptions as google_auth_exceptions

import chattice.transports.pubsub as pubsub_module
from chattice.transports.http.errors import VerificationError
from chattice.transports.http.request import IncomingRequest
from chattice.transports.pubsub import GooglePubSubVerifier

_AUDIENCE = "https://example.com/push"
_EMAIL = "push@project.iam.gserviceaccount.com"


def _request(token: str | None) -> IncomingRequest:
    headers = {} if token is None else {"Authorization": f"Bearer {token}"}
    return IncomingRequest(method="POST", path="/push", headers=headers)


@pytest.fixture(autouse=True)
def _stub_verify_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub google-auth's verify_token: the token string selects the claims."""

    def fake_verify_token(token: str, **kwargs: object) -> dict[str, object]:
        if token == "transport-down":
            raise google_auth_exceptions.TransportError(  # type: ignore[no-untyped-call]
                "network down"
            )
        if token == "invalid":
            raise ValueError("bad token")
        claims: dict[str, object] = {
            "iss": "accounts.google.com",
            "email_verified": True,
            "email": _EMAIL,
        }
        if token == "wrong-iss":
            claims["iss"] = "evil.example.com"
        elif token == "email-unverified":
            claims["email_verified"] = False
        elif token == "other-email":
            claims["email"] = "other@project.iam.gserviceaccount.com"
        return claims

    monkeypatch.setattr(pubsub_module, "verify_token", fake_verify_token)


def test_valid_token_with_matching_service_account() -> None:
    verifier = GooglePubSubVerifier(audience=_AUDIENCE, service_account_email=_EMAIL)
    verifier.verify(_request("t"))


def test_service_account_email_is_required() -> None:
    import pytest

    with pytest.raises(TypeError):
        GooglePubSubVerifier(audience=_AUDIENCE)  # type: ignore[call-arg]


def test_missing_authorization_header() -> None:
    verifier = GooglePubSubVerifier(audience=_AUDIENCE, service_account_email=_EMAIL)
    with pytest.raises(VerificationError, match="Authorization"):
        verifier.verify(_request(None))


def test_wrong_issuer() -> None:
    verifier = GooglePubSubVerifier(audience=_AUDIENCE, service_account_email=_EMAIL)
    with pytest.raises(VerificationError, match="issuer"):
        verifier.verify(_request("wrong-iss"))


def test_email_not_verified() -> None:
    verifier = GooglePubSubVerifier(audience=_AUDIENCE, service_account_email=_EMAIL)
    with pytest.raises(VerificationError, match="email"):
        verifier.verify(_request("email-unverified"))


def test_email_mismatch() -> None:
    verifier = GooglePubSubVerifier(
        audience=_AUDIENCE,
        service_account_email="expected@project.iam.gserviceaccount.com",
    )
    with pytest.raises(VerificationError, match="service account"):
        verifier.verify(_request("other-email"))


def test_transport_error_maps_to_verification_error() -> None:
    verifier = GooglePubSubVerifier(audience=_AUDIENCE, service_account_email=_EMAIL)
    with pytest.raises(VerificationError, match="certificates"):
        verifier.verify(_request("transport-down"))


def test_invalid_token_maps_to_verification_error() -> None:
    verifier = GooglePubSubVerifier(audience=_AUDIENCE, service_account_email=_EMAIL)
    with pytest.raises(VerificationError, match="bearer token"):
        verifier.verify(_request("invalid"))
