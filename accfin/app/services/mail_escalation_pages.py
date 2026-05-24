"""HTML pages for manager escalation respond flow — `05` §8.8a."""

from __future__ import annotations

import html
from uuid import UUID

_ACTION_LABELS = {
    "approve": "Approved",
    "reject": "Rejected",
    "escalate": "Escalated",
    "request_info": "Request More Info",
}


def action_label(action: str) -> str:
    return _ACTION_LABELS.get(action, action.replace("_", " ").title())


def html_escalation_form(
    *,
    escalation_id: UUID,
    case_number: str,
    action: str,
    token: str,
) -> str:
    label = action_label(action)
    esc_id = html.escape(str(escalation_id))
    case_num = html.escape(case_number)
    act = html.escape(action)
    tok = html.escape(token)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Confirm escalation — {label}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 32rem; margin: 2rem auto; padding: 0 1rem; color: #0f172a; }}
    label {{ display: block; font-weight: 600; margin-bottom: 0.35rem; }}
    textarea {{ width: 100%; min-height: 5rem; padding: 0.5rem; border: 1px solid #cbd5e1; border-radius: 4px; }}
    button {{ margin-top: 1rem; background: #1d4ed8; color: #fff; border: none; padding: 0.65rem 1.25rem; border-radius: 4px; font-size: 1rem; cursor: pointer; }}
    .meta {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 1rem; margin-bottom: 1.25rem; }}
    .meta dt {{ font-weight: 600; margin-top: 0.5rem; }}
    .meta dd {{ margin: 0.15rem 0 0 0; }}
  </style>
</head>
<body>
  <h1>Confirm manager action</h1>
  <dl class="meta">
    <dt>Case number</dt>
    <dd>{case_num}</dd>
    <dt>Action</dt>
    <dd>{html.escape(label)}</dd>
  </dl>
  <form method="post" action="/mail/escalations/{esc_id}/respond?action={act}&amp;token={tok}">
    <label for="comment">Comment (optional)</label>
    <textarea id="comment" name="comment" maxlength="4000" placeholder="e.g. Approved — recurring ACRA fee, no PO required"></textarea>
    <button type="submit">Submit</button>
  </form>
</body>
</html>"""


def html_escalation_confirmation(
    *,
    case_number: str,
    action: str,
    comment: str | None = None,
    target_email: str | None = None,
    message: str | None = None,
) -> str:
    label = action_label(action)
    case_num = html.escape(case_number)
    body = message or f"Case {case_num} has been updated."
    parts = [
        f"<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"utf-8\" />"
        f"<title>Escalation {html.escape(label)}</title></head><body>",
        f"<h1>{html.escape(label)}</h1>",
        f"<p><strong>Case number:</strong> {case_num}</p>",
        f"<p><strong>Action taken:</strong> {html.escape(label)}</p>",
    ]
    if comment:
        parts.append(
            f"<p><strong>Your comment:</strong> {html.escape(comment)}</p>"
        )
    if target_email and action == "escalate":
        parts.append(
            f"<p><strong>Forwarded to:</strong> {html.escape(target_email)}</p>"
        )
    parts.append(f"<p>{html.escape(body)}</p>")
    parts.append("</body></html>")
    return "".join(parts)
