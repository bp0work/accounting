# Finance Platform — Incident Response (Phase 10)

## Severity levels

| Level | Example | Response target |
|-------|---------|-----------------|
| SEV-1 | API down, audit chain compromised | 15 min acknowledge |
| SEV-2 | Worker backlog, degraded health | 1 hour |
| SEV-3 | Single mailbox stall | Next business day |

## First steps

1. Check `GET /health` and Grafana `finance-overview` dashboard.
2. Run `GET /audit-logs/integrity-check` if tampering is suspected.
3. Inspect Prometheus alerts: `finance_health_component_up`, queue depth (when wired).
4. Review dead-letter queue: `GET /events/dead-letter`.

## Audit integrity compromise

1. Stop writes that mutate financial state until root cause is known.
2. Export audit logs: `POST /audit-logs/export` with date range.
3. Preserve DB snapshots and application logs with matching `correlation_id`.
4. Escalate to platform admin and document in case timeline.

## Contacts

- Platform on-call: see internal ops roster (`11` §17).
- CFO digest issues: verify `system_settings.last_finance_log_sent_at` (Phase 11b).
