# Security Policy

## Reporting

Report suspected security vulnerabilities through **GitHub private
vulnerability reporting** (Security Advisories) on this repository.
Do not open a public issue for vulnerabilities.

## Supported versions

For pre-1.0 releases, only the latest release receives security fixes.
The policy will be expanded before 1.0.

## Security model

Chattice ships transport verification and capability guards:

- Incoming HTTP interactions: `GoogleTokenVerifier` (Google-issued
  bearer tokens, audience + issuer checks) → 401 on failure.
- Pub/Sub push: `GooglePubSubVerifier` (signature, audience, REQUIRED
  service-account email, email_verified) — secure by default; an
  explicit `allow_unverified=True` opt-in exists for local use only.
- Push dedupe is an owner-safe state machine; handlers must stay
  idempotent (push has no exactly-once guarantee).
- Secrets are never logged: the redaction source-scan test pins this.

If you find a bypass, please report it per the section above.
