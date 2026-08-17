# Security Policy

## Reporting

Report suspected security vulnerabilities through **GitHub private
vulnerability reporting** (Security Advisories) on the public
repository — enable the feature before the first public release.
Until the repository is public, contact the project owner directly.
Do not open a public issue for vulnerabilities.

## Supported versions

Pre-1.0 development releases: only the latest development release
receives fixes. A support policy for published releases will be defined
with the first public beta (0.14.0).

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
