# API Reference

This reference is rendered from current signatures and docstrings by
mkdocstrings. The [public API inventory](public-api.md) defines the deliberate
stable import surface; conceptual behavior and Google mappings live in the
task guides.

## Core

::: chattice

::: chattice.dispatcher

::: chattice.events

::: chattice.filters

::: chattice.middleware

## Actions, Cards, and Forms

::: chattice.actions

::: chattice.cards

::: chattice.forms

## Authentication, capabilities, and outbound client

::: chattice.auth

::: chattice.capabilities

::: chattice.client

## State and reliability

::: chattice.fsm

::: chattice.idempotency

::: chattice.observability

## Transports and integrations

::: chattice.transports.http

::: chattice.transports.pubsub

::: chattice.integrations.fastapi

## Workspace Events

::: chattice.workspace_events

## Experimental namespace

`chattice.experimental` carries optional integration contracts (e.g.
`chattice.experimental.ai`). The namespace has NO compatibility
promise; use it explicitly and pin the package version.

::: chattice.experimental

## Testing

::: chattice.testing


