# Accounts Worker (port 8010)

Consumes `intake_queue` (email classification via Hermes) and handles `general_inquiry` on `accounts_queue`.

- Health: `GET /health`
- Manual intake: `POST /process-intake-once`
