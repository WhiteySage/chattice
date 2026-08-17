# Event model

Status: **Extended in Phase 2**. See
[ADR-001](../adr/ADR-001-event-domain-model.md) and
[ADR-003](../adr/ADR-003-raw-google-models.md).

## Domain events

Framework events are lightweight immutable Python values. Phase 2 adds focused
optional interaction metadata to the keyword-only base without changing the
Phase 1 construction API:

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class Event:
    event_type: str = "event"
    raw: object = field(default=None, repr=False, compare=False)
    event_time: datetime | None = None
    actor: UserRef | None = None
    space: SpaceRef | None = None
    thread: ThreadRef | None = None
    dialog: DialogMetadata | None = None
```

The implemented hierarchy is:

- `Event(event_type="event", raw=None)` — generic synthetic event.
- `MessageEvent(text="", message=None, raw=None)` — normalized `MESSAGE`.
- `ActionEvent(name="", parameters={}, form_inputs=..., source=...)` —
  `CARD_CLICKED` and existing synthetic actions; `ActionSource` is
  `MESSAGE`, `DIALOG`, or `HOME` only when the wire proves that surface.
- `AddedToSpaceEvent` and `RemovedFromSpaceEvent` — lifecycle interactions.
- `WidgetUpdatedEvent` — dynamic widget input/action data.
- `CommandEvent(command_id=..., kind=...)` — typed slash, quick, and message
  action command families without an invented friendly name. Message actions
  also preserve the target `MessageRef`.
- `AppHomeEvent` and `FormSubmitEvent` — App Home initialization/submission.
- `UnknownEvent(original_type="", raw=None)` — forward-compatible unknown.
- `ErrorEvent(source_event=..., exception=...)` — internal/public error-routing
  value with `event_type == "error"`.

Constructors remain keyword-only. `UserRef`, `SpaceRef`, `ThreadRef`, and
`MessageRef` deliberately expose only stable basic identifiers/metadata, not
full Google resource models. A parsed `ThreadRef` also retains its already-known
parent `SpaceRef`, which enables a zero-fetch `thread.send()`. No event contains
credentials, transport state, response capabilities, or Google client objects;
the dispatcher exposes its configured Bot only through request-local execution
context.

`MessageEvent` exposes deep immutable snapshots of stable read-side Google
message fields through `attachments`, `annotations`, `mentions`, `quote`, and
`reaction_summaries`, plus the normalized booleans `is_private` and
`is_silent`. They read the existing `.raw` snapshot and never perform network
I/O. No attachment or reaction write service is implied.

## Commands and action surfaces

`CommandKind` normalizes Google's two documented wire families:

- slash commands: `MESSAGE` plus `message.slashCommand` →
  `SLASH_COMMAND`;
- quick commands: `APP_COMMAND` plus `appCommandMetadata` →
  `QUICK_COMMAND`;
- message actions: the same `APP_COMMAND` envelope → `MESSAGE_ACTION`
  (Developer Preview and routed only after explicit enrollment).

The compatibility `source_kind` string remains available for pre-beta callers
and unknown/mismatched values. `@router.command` remains the shared observer;
`slash_command`, `quick_command`, and the preview-gated `message_action`
observers make kind-specific routing explicit.

`ActionSource` is evidence-based: dialog metadata proves `DIALOG`, the wrapped
App Home `chat` envelope proves `HOME`, and a clicked message proves `MESSAGE`.
It stays `None` when the payload cannot prove the surface.

## Immutability

The dataclass instances are frozen and slotted. Parameter/form mappings take
immutable shallow snapshots. Synthetic callers can still supply an opaque raw
object. The Google adapter supplies a deep snapshot of the complete decoded
mapping. Raw remains opaque and can itself be mutable; it is excluded from repr
and equality.

## Unknown events

The Phase 2 adapter preserves a future external type without making it fatal:

```python
event = UnknownEvent(
    original_type="SOME_FUTURE_EVENT",
    raw={"type": "SOME_FUTURE_EVENT"},
)
```

The `unknown_event` observer receives it before the generic `event` fallback.
Unknown type and malformed payload are separate outcomes.

## Adapter boundary

Pydantic validates untrusted data only inside the Phase 2 adapter. Known
external types with malformed required content raise a public parser error;
unknown strings map to `UnknownEvent`. No event ID is added because Google
interactions do not document a universal one.
