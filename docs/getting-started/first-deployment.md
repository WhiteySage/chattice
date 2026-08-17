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
