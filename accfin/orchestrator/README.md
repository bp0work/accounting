# Workflow Orchestrator (port 8003)

Consumes `intake_queue`, creates cases, runs state transitions, routes to `accounts_queue`, and manages `retry_queue` / `dead_letter_queue`.

- Health: `GET /health`
- Manual process (tests): `POST /process-once`
