# ADR-005: Separate request verification and API credentials

- Status: Accepted
- Date: 2026-08-13
- Owners: maintainers

## Context

Inbound interaction authenticity and outbound Chat API authorization are
different security problems. Inbound HTTP may use an ID token for an endpoint
URL audience, a self-signed JWT for a project-number audience, or platform IAM.
Outbound calls use app credentials or user OAuth, with method/scope-dependent
permissions. Synchronous interaction responses need no Chat API authorization.

## Decision

Use separate contracts:

- `IncomingRequestVerifier` authenticates an ingress request and returns a
  verified principal/context or raises a verification error.
- `AppCredentialsProvider` supplies app-auth credentials.
- `UserCredentialsProvider` supplies scoped user credentials without defining
  token persistence inside core.

Credential choice occurs at the outbound operation boundary. Secrets and token
material are never stored in events, handler metadata, or logs. Deployments
that delegate verification to trusted platform IAM must opt in explicitly.

## Consequences

Security boundaries are auditable and synchronous replies avoid unnecessary
credentials. Integrations require more configuration, and app/user method
support must be represented as capabilities rather than guessed.

## Alternatives considered

- One generic auth provider: conflates identity-token verification and OAuth.
- Require service-account credentials everywhere: breaks user-auth operations.
- Trust all inbound traffic by default: unsafe outside a protected deployment.

## Sources

[verify requests from Chat](https://developers.google.com/workspace/chat/verify-requests-from-chat),
[authenticate and authorize](https://developers.google.com/workspace/chat/authenticate-authorize),
[respond to interactions](https://developers.google.com/workspace/chat/receive-respond-interactions).

