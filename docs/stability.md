# Public beta stability

Current package: Chattice 0.14.0, the public-beta release candidate.

## Stable beta surface

The documented stable API is frozen for the beta. Stable package `__all__`
exports and the public members listed in the [public API inventory](public-api.md)
may grow additively, but existing names, call signatures, and documented
semantics will not change incompatibly. Bug and security fixes may make invalid
or unsafe behavior fail earlier.

This is stronger than ordinary pre-1.0 SemVer expectations. The project is
collecting production feedback before declaring 1.0, but the beta is not an
invitation to churn the architecture.

## Experimental surface

Everything under `chattice.experimental` is outside the stable contract.
The `chattice.experimental` namespace is an optional integration layer:
stable core primitives remain the supported surface, while anything in the
experimental namespace (for example the optional AI integration
`chattice.experimental.ai`) can change or disappear before 1.0.

Google Developer Preview features are also explicitly opted into, for example:

```python
from chattice import Dispatcher
from chattice.capabilities import PreviewFeature

dispatcher = Dispatcher(preview_features={PreviewFeature.MESSAGE_ACTION})
```

The stable preview gate does not make Google's preview feature stable.

## Raw and advanced surface

`Bot.raw_client` exposes the official async Google Chat client. Event `.raw`
preserves the incoming Google payload, and `RawWidget` provides a card-widget
escape hatch. These are intentional, supported extension points for features
the curated facade does not yet wrap. Their fields and methods follow Google's
SDK, discovery schema, and wire payloads, not Chattice's stable-facade promise.

Prefer the typed facade for common operations; use raw access at a narrow
application boundary and test the exact Google schema you depend on.

## Version and deprecation policy

The latest beta line receives normal fixes; older betas receive security fixes
for six months. Stable beta symbols are not removed during the beta. After 1.0,
Semantic Versioning governs breaking changes and deprecated symbols remain for
at least one minor release cycle.

Next: [5-minute Quickstart](getting-started/quickstart.md).
