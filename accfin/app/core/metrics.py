"""Prometheus metrics — `11` monitoring runbook."""

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

HTTP_REQUESTS = Counter(
    "finance_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)
HTTP_LATENCY = Histogram(
    "finance_http_request_duration_seconds",
    "HTTP request latency",
    ["method", "endpoint"],
)
HEALTH_COMPONENT = Gauge(
    "finance_health_component_up",
    "Health component status (1=up, 0=down)",
    ["component"],
)
AUDIT_ENTRIES = Counter(
    "finance_audit_log_entries_total",
    "Audit log entries written",
    ["action", "entity_type"],
)


def metrics_payload() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
