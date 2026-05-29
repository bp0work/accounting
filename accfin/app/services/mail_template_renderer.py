"""Jinja2 renderers for executive outbound mail — `18` §7.7–§7.8."""

from __future__ import annotations

from dataclasses import dataclass

from jinja2 import Environment, BaseLoader, select_autoescape


@dataclass(frozen=True)
class TenantEmailSignature:
    html: str = ""
    plain: str = ""


def append_tenant_signature(
    body_plain: str,
    body_html: str | None,
    *,
    signature: TenantEmailSignature | None,
) -> tuple[str, str | None]:
    """Append tenant footer when HTML and/or plain signature is configured."""
    if signature is None:
        return body_plain, body_html
    html_sig = signature.html.strip()
    plain_sig = signature.plain.strip()
    if not html_sig and not plain_sig:
        return body_plain, body_html

    plain = body_plain
    if plain_sig:
        plain = f"{body_plain.rstrip()}\n\n--\n{plain_sig}"

    html = body_html
    if html_sig and html is not None:
        html = (
            f"{html.rstrip()}"
            '<hr style="margin-top:2rem;border:none;border-top:1px solid #e2e8f0;">'
            f'<div style="color:#6b7280;font-size:0.875rem;">{html_sig}</div>'
        )
    return plain, html

_ENV = Environment(
    loader=BaseLoader(),
    autoescape=select_autoescape(default_for_string=True, enabled_extensions=("html", "xml")),
    trim_blocks=True,
    lstrip_blocks=True,
)

_ACK_PLAIN = """\
Thank you for your email{% if sender_name %}, {{ sender_name }}{% endif %}.

We have received your message and assigned reference {{ case_number }}. Our team will review it shortly.

Original subject: {{ original_subject | default('(no subject)') }}
{% if received_at_display %}Received: {{ received_at_display }}
{% endif %}{% if attachment_filenames %}
File(s) received:
{% for name in attachment_filenames -%}
- {{ name }}
{% endfor -%}
{% endif %}{% if original_body_plain %}

----- Original message -----
{{ original_body_plain }}
{% endif %}"""

_ACK_HTML = """\
<p>Thank you for your email{% if sender_name %}, {{ sender_name }}{% endif %}.</p>
<p>We have received your message and assigned reference <strong>{{ case_number }}</strong>. \
Our team will review it shortly.</p>
<p><strong>Original subject:</strong> {{ original_subject | default('(no subject)') }}</p>
{% if received_at_display %}<p><strong>Received:</strong> {{ received_at_display }}</p>{% endif %}
{% if attachment_filenames %}
<p><strong>File(s) received:</strong></p>
<ul>
{% for name in attachment_filenames %}
  <li>{{ name }}</li>
{% endfor %}
</ul>
{% endif %}
{% if original_body_plain %}
<hr>
<p><strong>Original message</strong></p>
<blockquote style="border-left:3px solid #ccc;padding-left:12px;color:#444;white-space:pre-wrap;margin:0;">
{{ original_body_plain }}
</blockquote>
{% endif %}"""

_FINANCE_UI_RETRY_NOTE = (
    "To reprocess after setting up the vendor, use the Retry button "
    "in the Finance UI case detail page."
)

_VENDOR_NOT_FOUND_ESCALATION_PLAIN = """\
Action required — vendor not set up for case {{ case_number }}.

Summary: {{ summary }}
{% if error_reason %}Reason: {{ error_reason }}{% endif %}
{% if executive_mailbox %}Executive mailbox: {{ executive_mailbox }}{% endif %}

This vendor is not registered. You may only reject this document so the sender is notified.
There is no approve or reprocess action from this email.

{{ finance_ui_note }}

Reject: {{ reject_url }}
"""

_VENDOR_NOT_FOUND_ESCALATION_HTML = """\
<h2>Action required — vendor not set up</h2>
<p><strong>Case:</strong> {{ case_number }}</p>
<p><strong>Summary:</strong> {{ summary }}</p>
{% if error_reason %}<p><strong>Reason:</strong> {{ error_reason }}</p>{% endif %}
{% if executive_mailbox %}<p><strong>Executive mailbox:</strong> {{ executive_mailbox }}</p>{% endif %}
<p>This vendor is not registered. You may only <strong>reject</strong> this document so the sender is notified.
There is no approve or reprocess action from this email.</p>
<p><em>{{ finance_ui_note }}</em></p>
<p>
  <a href="{{ reject_url }}" style="background:#dc2626;color:#fff;padding:8px 16px;text-decoration:none;border-radius:4px;">Reject</a>
</p>
<p style="font-size:12px;color:#64748b;">If the button does not work, use this link:<br>
Reject: {{ reject_url }}</p>
"""

_ESCALATION_PLAIN = """\
Action required — manager review for case {{ case_number }}.

Summary: {{ summary }}
{% if error_reason %}Reason: {{ error_reason }}{% endif %}
{% if forwarded_from %}Forwarded from: {{ forwarded_from }}{% endif %}
{% if manager_comment %}Note from previous reviewer: {{ manager_comment }}{% endif %}
{% if executive_mailbox %}Executive mailbox: {{ executive_mailbox }}{% endif %}

{{ approve_label | default('Approve') }}: {{ approve_url }}
Reject: {{ reject_url }}
Escalate: {{ escalate_url }}
"""

_ESCALATION_HTML = """\
<h2>Action required — manager review</h2>
<p><strong>Case:</strong> {{ case_number }}</p>
<p><strong>Summary:</strong> {{ summary }}</p>
{% if error_reason %}<p><strong>Reason:</strong> {{ error_reason }}</p>{% endif %}
{% if forwarded_from %}<p><strong>Forwarded from:</strong> {{ forwarded_from }}</p>{% endif %}
{% if manager_comment %}<p><strong>Note from previous reviewer:</strong> {{ manager_comment }}</p>{% endif %}
{% if executive_mailbox %}<p><strong>Executive mailbox:</strong> {{ executive_mailbox }}</p>{% endif %}
<p>
  <a href="{{ approve_url }}" style="background:#16a34a;color:#fff;padding:8px 16px;text-decoration:none;border-radius:4px;">{{ approve_label | default('Approve') }}</a>
  &nbsp;
  <a href="{{ reject_url }}" style="background:#dc2626;color:#fff;padding:8px 16px;text-decoration:none;border-radius:4px;">Reject</a>
  &nbsp;
  <a href="{{ escalate_url }}" style="background:#64748b;color:#fff;padding:8px 16px;text-decoration:none;border-radius:4px;">Escalate</a>
</p>
<p style="font-size:12px;color:#64748b;">If buttons do not work, use these links:<br>
{{ approve_label | default('Approve') }}: {{ approve_url }}<br>
Reject: {{ reject_url }}<br>
Escalate: {{ escalate_url }}</p>
"""

_MISSING_FIELDS_ESCALATION_PLAIN = """\
Action required — missing invoice fields for case {{ case_number }}.

Summary: {{ summary }}
{% if extraction_confidence is not none %}Extraction confidence: {{ extraction_confidence }}
{% endif %}{% if extracted_fields %}
Extracted:
{% for key, value in extracted_fields.items() -%}
- {{ key }}: {{ value if value else '(not found)' }}
{% endfor -%}
{% endif %}{% if missing_fields %}
Missing:
{% for field in missing_fields -%}
- {{ field }}
{% endfor -%}
{% endif %}{% if executive_mailbox %}Executive mailbox: {{ executive_mailbox }}
{% endif %}
Approve: {{ approve_url }}
Request more info: {{ request_info_url }}
Reject: {{ reject_url }}
"""

_MISSING_FIELDS_ESCALATION_HTML = """\
<h2>Action required — missing invoice fields</h2>
<p><strong>Case:</strong> {{ case_number }}</p>
<p><strong>Summary:</strong> {{ summary }}</p>
{% if extraction_confidence is not none %}<p><strong>Extraction confidence:</strong> {{ extraction_confidence }}</p>{% endif %}
{% if extracted_fields %}
<p><strong>Extracted:</strong></p>
<ul>
{% for key, value in extracted_fields.items() %}
  <li><strong>{{ key }}:</strong> {{ value if value else '(not found)' }}</li>
{% endfor %}
</ul>
{% endif %}
{% if missing_fields %}
<p><strong>Missing:</strong></p>
<ul>
{% for field in missing_fields %}
  <li>{{ field }}</li>
{% endfor %}
</ul>
{% endif %}
{% if executive_mailbox %}<p><strong>Executive mailbox:</strong> {{ executive_mailbox }}</p>{% endif %}
<p>
  <a href="{{ approve_url }}" style="background:#16a34a;color:#fff;padding:8px 16px;text-decoration:none;border-radius:4px;">Approve</a>
  &nbsp;
  <a href="{{ request_info_url }}" style="background:#2563eb;color:#fff;padding:8px 16px;text-decoration:none;border-radius:4px;">Request More Info</a>
  &nbsp;
  <a href="{{ reject_url }}" style="background:#dc2626;color:#fff;padding:8px 16px;text-decoration:none;border-radius:4px;">Reject</a>
</p>
<p style="font-size:12px;color:#64748b;">If buttons do not work, use these links:<br>
Approve: {{ approve_url }}<br>
Request more info: {{ request_info_url }}<br>
Reject: {{ reject_url }}</p>
"""

_DAILY_LOG_PLAIN = """\
Finance activity log for {{ business_date }}.

Total entries: {{ row_count }}
{% for item in mailbox_summary %}
- {{ item.mailbox }}: {{ item.count }}
{% endfor %}

Full details are attached as {{ attachment_filename }}.
"""

_DAILY_LOG_HTML = """\
<h2>Finance activity log — {{ business_date }}</h2>
<p>Total entries: <strong>{{ row_count }}</strong></p>
{% if mailbox_summary %}
<ul>
{% for item in mailbox_summary %}
  <li>{{ item.mailbox }}: {{ item.count }}</li>
{% endfor %}
</ul>
{% endif %}
<p>Full details are attached as <strong>{{ attachment_filename }}</strong>.</p>
"""

_GL_CUTOFF_PLAIN = """\
{{ lead }}

Period type: {{ period_type }}
GL cutoff date: {{ cutoff_date }}
Current status: {{ status }}
Trial balance reviewer: {{ reviewer }}

Accounting calendar: {{ calendar_url }}
"""

_GL_CUTOFF_HTML = """\
<p>{{ lead }}</p>
<ul>
  <li><strong>Period type:</strong> {{ period_type }}</li>
  <li><strong>GL cutoff date:</strong> {{ cutoff_date }}</li>
  <li><strong>Current status:</strong> {{ status }}</li>
  <li><strong>Trial balance reviewer:</strong> {{ reviewer }}</li>
</ul>
<p><a href="{{ calendar_url }}">Accounting calendar</a></p>
"""


def _render_signed(
    plain_template: str,
    html_template: str,
    context: dict,
    *,
    signature: TenantEmailSignature | None = None,
) -> tuple[str, str]:
    plain = _ENV.from_string(plain_template).render(**context).strip()
    html = _ENV.from_string(html_template).render(**context).strip()
    return append_tenant_signature(plain, html, signature=signature)


def render_acknowledgement(
    context: dict,
    *,
    signature: TenantEmailSignature | None = None,
) -> tuple[str, str]:
    return _render_signed(_ACK_PLAIN, _ACK_HTML, context, signature=signature)


def render_manager_escalation(
    context: dict,
    *,
    signature: TenantEmailSignature | None = None,
) -> tuple[str, str]:
    return _render_signed(_ESCALATION_PLAIN, _ESCALATION_HTML, context, signature=signature)


def render_vendor_not_found_escalation(
    context: dict,
    *,
    signature: TenantEmailSignature | None = None,
) -> tuple[str, str]:
    ctx = dict(context)
    ctx.setdefault("finance_ui_note", _FINANCE_UI_RETRY_NOTE)
    return _render_signed(
        _VENDOR_NOT_FOUND_ESCALATION_PLAIN,
        _VENDOR_NOT_FOUND_ESCALATION_HTML,
        ctx,
        signature=signature,
    )


def render_missing_fields_escalation(
    context: dict,
    *,
    signature: TenantEmailSignature | None = None,
) -> tuple[str, str]:
    return _render_signed(
        _MISSING_FIELDS_ESCALATION_PLAIN,
        _MISSING_FIELDS_ESCALATION_HTML,
        context,
        signature=signature,
    )


def render_daily_log(
    context: dict,
    *,
    signature: TenantEmailSignature | None = None,
) -> tuple[str, str]:
    return _render_signed(_DAILY_LOG_PLAIN, _DAILY_LOG_HTML, context, signature=signature)


def render_gl_cutoff_reminder(
    context: dict,
    *,
    signature: TenantEmailSignature | None = None,
) -> tuple[str, str]:
    return _render_signed(_GL_CUTOFF_PLAIN, _GL_CUTOFF_HTML, context, signature=signature)
