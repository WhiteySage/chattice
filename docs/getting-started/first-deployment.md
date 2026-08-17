# First deployment

An HTTP Chattice app is an ASGI service. Any platform that provides a stable
public HTTPS URL and preserves the request body and `Authorization` header can
host it.

## Container command

```bash
uvicorn app:app --host 0.0.0.0 --port "${PORT:-8080}"
```

Configure these as runtime secrets/settings:

- `CHATTICE_AUDIENCE`: exact endpoint URL or project number selected in the
  Chat API configuration.
- Service-account credential path or workload identity configuration, only if
  the app makes outbound Chat API calls.

## Cloud Run checklist

1. Build and deploy the ASGI container.
2. Decide whether Cloud IAM or the application verifier is responsible for
   authenticating Chat. Do not accidentally require two incompatible audience
   configurations.
3. Put the final HTTPS URL in the Chat API configuration and use the same URL
   as `CHATTICE_AUDIENCE` when application-level verification is enabled.
4. Restrict app visibility to testers before a wider rollout.
5. Send a direct message, a Space mention, and the configured `/deploy`
   command. Inspect structured logs without logging tokens or private form
   values.

Google Chat can retry failed HTTP deliveries, so make side effects idempotent.
See [Deployment and operations](../guides/deployment.md) for retries,
observability, secrets, and Pub/Sub deployment.

Next: [Recommended project structure](project-structure.md).

## Live test checklist (15 minutes)

1. In the Google Cloud Console, set the app to **Live** mode and choose
   the HTTP endpoint (`https://your-domain/`).
2. Set `CHATTICE_AUDIENCE` to exactly that URL (trailing slash matters).
3. Deploy the app; `curl https://your-domain/healthz` must answer 200.
4. In Google Chat, open a **DM** with the app → send a message → the
   handler answer must appear within seconds.
5. Add the app to a **test Space** → mention the app → check the answer.
6. Test a **card**: trigger the card handler, click a button, confirm the
   update/action response.
7. Test **private**: trigger the private flow with two accounts in the
   Space; the second account must NOT see the private card.
8. Test a **Dialog**: open it from a button, submit, check the banner.
9. Watch `journalctl -u <service> -f` during every step; a 401 means
   audience mismatch, a 403 means the app is not a Space member or lacks
   scopes.

