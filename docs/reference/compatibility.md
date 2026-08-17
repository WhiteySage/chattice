# Compatibility and schema status

Last verified: 2026-08-16.

| Input | Compatible snapshot |
| --- | --- |
| Chattice | 0.14.0b1 public beta |
| Python | 3.11, 3.12, 3.13 |
| `google-apps-chat` | `>=0.10.4,<1.0.0` (lock: 0.10.4) |
| Google Chat REST API | v1 |
| Google Chat Discovery revision | `20260809` |
| Google Workspace Events envelopes | CloudEvents 1.0 |

The discovery revision is the live v1 document observed during the
documentation acceptance drive. Compatibility means Chattice's curated public
surface and fixtures were validated against this snapshot; it does not imply
that every method or field in the Google API has a high-level wrapper.

New/unsupported fields remain available through raw payloads and the official
client. Schema drift must be reviewed before changing the curated stable API;
generation must not silently mutate it. The Google REST reference links the
live [Discovery document](https://chat.googleapis.com/$discovery/rest?version=v1).

Preview-to-GA transitions, new scopes, methods, enum values, and deprecations
are release-maintenance inputs. The current release gate pins public exports,
parses sanitized/official payload fixtures, builds the generated reference,
and keeps unknown-event/raw fallbacks forward-compatible. Automated inventory
diff reporting beyond these checks is classified post-beta.
