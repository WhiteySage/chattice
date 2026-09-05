"""Local token-minting helpers for verifier tests (no Google credentials)."""

from __future__ import annotations

import datetime
import json

import jwt as pyjwt
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

CHAT_ISSUER = "chat@system.gserviceaccount.com"


def _make_cert() -> tuple[bytes, bytes]:
    """Return (x509_pem, private_key_pem) for a locally minted Chat issuer."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, CHAT_ISSUER)])
    now = datetime.datetime.now(datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=30))
        .sign(key, hashes.SHA256())
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    key_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    return cert_pem, key_pem


def make_token(
    key_pem: bytes,
    *,
    audience: str,
    issuer: str | None = CHAT_ISSUER,
    expiry: datetime.timedelta = datetime.timedelta(minutes=5),
    email: str | None = None,
) -> str:
    """Mint an RS256 JWT signed with the local key (kid matches the stub)."""
    now = datetime.datetime.now(datetime.UTC)
    claims: dict[str, object] = {
        "aud": audience,
        "iat": int(now.timestamp()),
        "exp": int((now + expiry).timestamp()),
    }
    if issuer is not None:
        claims["iss"] = issuer
    if email is not None:
        claims["email"] = email
    return pyjwt.encode(claims, key_pem, algorithm="RS256", headers={"kid": "local"})


class _StubResponse:
    """Minimal google-auth-compatible response (google-auth 2.56 exposes no
    public Response constructor in google.auth.transport.requests; the
    verifier's cert fetcher only reads ``status`` and ``data``)."""

    def __init__(self, status_code: int, data: bytes) -> None:
        self.status = status_code
        self.data = data
        self.headers: dict[str, str] = {}


class StubTransport:
    """google-auth-compatible transport serving our local x509 certificate."""

    def __init__(self, cert_pem: bytes) -> None:
        self._cert = cert_pem
        self.last_url: str | None = None

    def __call__(
        self,
        url: str,
        method: str = "GET",
        body: bytes | None = None,
        headers: object = None,
        **kwargs: object,
    ) -> object:
        self.last_url = url
        payload = json.dumps({"local": self._cert.decode()}).encode()
        return _StubResponse(status_code=200, data=payload)
