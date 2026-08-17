# Native commands

Google Chat commands are configured in the Chat API Console and routed by
their numeric ID. Chattice normalizes all native families into `CommandEvent`
and identifies the family with `CommandKind`.

| Family | Observer | Status |
| --- | --- | --- |
| Slash command | `router.slash_command()` | stable |
| Quick command | `router.quick_command()` | stable |
| Message action | `router.message_action()` | Google Developer Preview; explicit opt-in |

## Slash command

Configure `/deploy` with command ID `42`, then route it:

```python
from chattice import F, Router
from chattice.events import CommandEvent, CommandKind

router = Router()


@router.slash_command(F.command_id == 42)
async def deploy(event: CommandEvent) -> str:
    assert event.kind is CommandKind.SLASH_COMMAND
    environment = (event.message_text or "").strip()
    return f"Deploying {environment or 'staging'}"
```

Slash commands arrive in Google's `MESSAGE` wire family with
`message.slashCommand.commandId` and `argumentText`; the adapter produces a
`CommandEvent`, so do not parse `/deploy` out of ordinary message text.

## Quick command

```python
@router.quick_command(F.command_id == 7)
async def status(event: CommandEvent) -> str:
    return "All systems operational"
```

Quick commands arrive as `APP_COMMAND` interactions with
`appCommandMetadata`.

## Message action (Preview)

```python
from chattice import Dispatcher
from chattice.capabilities import PreviewFeature

dispatcher = Dispatcher(preview_features={PreviewFeature.MESSAGE_ACTION})


@router.message_action(F.command_id == 9)
async def summarize(event: CommandEvent) -> str:
    assert event.target_message is not None
    return f"Selected {event.target_message.name}"
```

Without enrollment the payload remains parseable but does not reach the
Preview observer. This is a stability gate, not proof of account enrollment,
scope, or Google authorization.

## Text filters are different

Use `@router.message(F.text == "help")` for application text triggers. Use a
native command when discoverability, a command menu, a configured ID, or an
eligible dialog-opening interaction matters. There is no in-process command
registry to synchronize; Google Console is the registry.

Next: [Cards, actions, forms, and dialogs](cards-forms-dialogs.md).
