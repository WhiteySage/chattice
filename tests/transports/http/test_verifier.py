"""Incoming verification."""

from __future__ import annotations

import datetime

import pytest
from google.auth import exceptions as google_auth_exceptions

from chattice.transports.http import (
    GoogleTokenVerifier,
    IncomingRequest,
    MockVerifier,
    VerificationError,
)

from ._test_tokens import CHAT_ISSUER, StubTransport, _make_cert, make_token

AUDIENCE = "1234567890"
_cert_pem, _key_pem = _make_cert()
_stub = StubTransport(_cert_pem)


def _request(token: str | None) -> IncomingRequest:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return IncomingRequest(method="POST", path="/", headers=headers)


def _verifier() -> GoogleTokenVerifier:
    return GoogleTokenVerifier(audience=AUDIENCE, request=_stub)  # type: ignore[arg-type]


def test_valid_token_passes() -> None:
    _verifier().verify(_request(make_token(_key_pem, audience=AUDIENCE)))


def test_id_token_strategy_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Endpoint-URL audience: the official verify_oauth2_token flow with
    the Google Chat identity checks."""
    import chattice.transports.http.verifier as verifier_module

    audience = "https://example.com/app/"
    calls: dict[str, object] = {}

    def fake_verify_oauth2_token(
        token: str, request: object, *, audience: str
    ) -> dict[str, object]:
        calls["token"] = token
        calls["request"] = request
        calls["audience"] = audience
        return {
            "iss": "https://accounts.google.com",
            "aud": audience,
            "email": CHAT_ISSUER,
            "email_verified": True,
        }

    monkeypatch.setattr(
        verifier_module, "verify_oauth2_token", fake_verify_oauth2_token
    )
    GoogleTokenVerifier(audience=audience, request=_stub).verify(  # type: ignore[arg-type]
        _request("t")
    )
    assert calls["audience"] == audience


def test_id_token_strategy_rejects_wrong_email(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import chattice.transports.http.verifier as verifier_module

    def fake_verify_oauth2_token(
        token: str, request: object, *, audience: str
    ) -> dict[str, object]:
        return {
            "iss": "https://accounts.google.com",
            "aud": audience,
            "email": "attacker@example.com",
            "email_verified": True,
        }

    monkeypatch.setattr(
        verifier_module, "verify_oauth2_token", fake_verify_oauth2_token
    )
    with pytest.raises(VerificationError, match="identity"):
        GoogleTokenVerifier(audience="https://example.com/", request=_stub).verify(  # type: ignore[arg-type]
            _request("t")
        )


def test_id_token_strategy_rejects_unverified_email(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import chattice.transports.http.verifier as verifier_module

    def fake_verify_oauth2_token(
        token: str, request: object, *, audience: str
    ) -> dict[str, object]:
        return {
            "iss": "https://accounts.google.com",
            "aud": audience,
            "email": CHAT_ISSUER,
            "email_verified": False,
        }

    monkeypatch.setattr(
        verifier_module, "verify_oauth2_token", fake_verify_oauth2_token
    )
    with pytest.raises(VerificationError, match="not verified"):
        GoogleTokenVerifier(audience="https://example.com/", request=_stub).verify(  # type: ignore[arg-type]
            _request("t")
        )


def test_id_token_strategy_wrong_audience_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """verify_oauth2_token raises ValueError on audience mismatch ->
    VerificationError (never a bypass)."""
    import chattice.transports.http.verifier as verifier_module

    def fake_verify_oauth2_token(
        token: str, request: object, *, audience: str
    ) -> dict[str, object]:
        raise ValueError("Wrong audience")

    monkeypatch.setattr(
        verifier_module, "verify_oauth2_token", fake_verify_oauth2_token
    )
    with pytest.raises(VerificationError, match="bearer token"):
        GoogleTokenVerifier(audience="https://example.com/", request=_stub).verify(  # type: ignore[arg-type]
            _request("t")
        )


def test_id_token_strategy_invalid_signature_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import chattice.transports.http.verifier as verifier_module

    def fake_verify_oauth2_token(
        token: str, request: object, *, audience: str
    ) -> dict[str, object]:
        raise ValueError("Token verification failed")

    monkeypatch.setattr(
        verifier_module, "verify_oauth2_token", fake_verify_oauth2_token
    )
    with pytest.raises(VerificationError, match="bearer token"):
        GoogleTokenVerifier(audience="https://example.com/", request=_stub).verify(  # type: ignore[arg-type]
            _request("t")
        )


def test_missing_authorization_raises() -> None:
    with pytest.raises(VerificationError, match="Authorization"):
        _verifier().verify(_request(None))


def test_malformed_authorization_raises() -> None:
    request = IncomingRequest(
        method="POST", path="/", headers={"Authorization": "Basic abc"}
    )
    with pytest.raises(VerificationError, match="Authorization"):
        _verifier().verify(request)


def test_bearer_with_internal_whitespace_raises() -> None:
    request = IncomingRequest(
        method="POST", path="/", headers={"Authorization": "Bearer token with space"}
    )
    with pytest.raises(VerificationError, match="Authorization"):
        _verifier().verify(request)


def test_expired_token_raises() -> None:
    token = make_token(
        _key_pem, audience=AUDIENCE, expiry=datetime.timedelta(minutes=-5)
    )
    with pytest.raises(VerificationError):
        _verifier().verify(_request(token))


def test_wrong_audience_raises() -> None:
    token = make_token(_key_pem, audience="someone-else")
    with pytest.raises(VerificationError):
        _verifier().verify(_request(token))


def test_missing_issuer_raises() -> None:
    token = make_token(_key_pem, audience=AUDIENCE, issuer=None)
    with pytest.raises(VerificationError, match="issuer"):
        _verifier().verify(_request(token))


def test_wrong_issuer_raises() -> None:
    token = make_token(_key_pem, audience=AUDIENCE, issuer="evil@example.com")
    with pytest.raises(VerificationError, match="issuer"):
        _verifier().verify(_request(token))


def test_wrong_email_raises() -> None:
    token = make_token(
        _key_pem,
        audience=AUDIENCE,
        issuer="https://accounts.google.com",
        email="someone@example.com",
    )
    with pytest.raises(VerificationError, match="issuer"):
        _verifier().verify(_request(token))


def test_unverifiable_signature_raises() -> None:
    _other_cert, other_key = _make_cert()
    token = make_token(other_key, audience=AUDIENCE)
    with pytest.raises(VerificationError, match="bearer"):
        _verifier().verify(_request(token))


def test_mock_verifier_accepts() -> None:
    MockVerifier().verify(_request(None))


def test_mock_verifier_rejects() -> None:
    with pytest.raises(VerificationError):
        MockVerifier(reject=True).verify(_request(None))


def test_certs_url_matches_documented_issuer() -> None:
    _verifier().verify(_request(make_token(_key_pem, audience=AUDIENCE)))
    assert _stub.last_url == (
        "https://www.googleapis.com/service_accounts/v1/metadata/x509/" + CHAT_ISSUER
    )


class _FailingTransport:
    def __call__(
        self,
        url: str,
        method: str = "GET",
        body: bytes | None = None,
        headers: object = None,
        **kwargs: object,
    ) -> object:
        raise ConnectionError("network down")


def test_transport_failure_propagates() -> None:
    verifier = GoogleTokenVerifier(
        audience=AUDIENCE,
        request=_FailingTransport(),  # type: ignore[arg-type]
    )
    with pytest.raises(ConnectionError):
        verifier.verify(_request(make_token(_key_pem, audience=AUDIENCE)))


class _TransportErrorStub:
    def __call__(
        self,
        url: str,
        method: str = "GET",
        body: bytes | None = None,
        headers: object = None,
        **kwargs: object,
    ) -> object:
        raise google_auth_exceptions.TransportError(  # type: ignore[no-untyped-call]
            "certs endpoint down"
        )


def test_transport_error_becomes_verification_error() -> None:
    verifier = GoogleTokenVerifier(
        audience=AUDIENCE,
        request=_TransportErrorStub(),  # type: ignore[arg-type]
    )
    with pytest.raises(VerificationError, match="certificates"):
        verifier.verify(_request(make_token(_key_pem, audience=AUDIENCE)))


def test_certs_source_follows_audience_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression (live E2E): the endpoint-URL audience goes through
    verify_oauth2_token (standard OAuth2 certs, NO certs_url ever);
    the project-number audience goes through verify_token with the Chat
    service-account certs URL."""
    import chattice.transports.http.verifier as verifier_module
    from chattice.transports.http import GoogleTokenVerifier
    from chattice.transports.http.request import IncomingRequest

    seen_oauth2: list[dict[str, object]] = []
    seen_token: list[dict[str, object]] = []

    def fake_verify_oauth2_token(
        token: str, request: object, *, audience: str
    ) -> dict[str, object]:
        seen_oauth2.append({"audience": audience})
        return {
            "iss": "https://accounts.google.com",
            "aud": audience,
            "email": "chat@system.gserviceaccount.com",
            "email_verified": True,
        }

    def fake_verify_token(token: str, **kwargs: object) -> dict[str, object]:
        seen_token.append(kwargs)
        return {
            "iss": "chat@system.gserviceaccount.com",
            "email": "chat@system.gserviceaccount.com",
        }

    monkeypatch.setattr(
        verifier_module, "verify_oauth2_token", fake_verify_oauth2_token
    )
    monkeypatch.setattr(verifier_module, "verify_token", fake_verify_token)
    request = IncomingRequest(
        method="POST", path="/", headers={"Authorization": "Bearer t"}
    )

    GoogleTokenVerifier(audience="https://example.ngrok-free.app").verify(request)
    assert seen_oauth2 == [{"audience": "https://example.ngrok-free.app"}]
    assert seen_token == []  # URL mode NEVER touches verify_token

    GoogleTokenVerifier(audience="1234567890").verify(request)
    assert seen_token and seen_token[0]["certs_url"] == verifier_module._CHAT_CERTS_URL
