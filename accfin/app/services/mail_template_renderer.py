"""Jinja2 renderers for executive outbound mail — `18` §7.7–§7.8."""

from __future__ import annotations

from jinja2 import Environment, BaseLoader, select_autoescape

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

_ESCALATION_PLAIN = """\
Action required — manager review for case {{ case_number }}.

Summary: {{ summary }}
{% if error_reason %}Reason: {{ error_reason }}{% endif %}
{% if executive_mailbox %}Executive mailbox: {{ executive_mailbox }}{% endif %}

Approve: {{ approve_url }}
Reject: {{ reject_url }}
Escalate: {{ escalate_url }}
"""

_ESCALATION_HTML = """\
<h2>Action required — manager review</h2>
<p><strong>Case:</strong> {{ case_number }}</p>
<p><strong>Summary:</strong> {{ summary }}</p>
{% if error_reason %}<p><strong>Reason:</strong> {{ error_reason }}</p>{% endif %}
{% if executive_mailbox %}<p><strong>Executive mailbox:</strong> {{ executive_mailbox }}</p>{% endif %}
<p>
  <a href="{{ approve_url }}" style="background:#16a34a;color:#fff;padding:8px 16px;text-decoration:none;border-radius:4px;">Approve</a>
  &nbsp;
  <a href="{{ reject_url }}" style="background:#dc2626;color:#fff;padding:8px 16px;text-decoration:none;border-radius:4px;">Reject</a>
  &nbsp;
  <a href="{{ escalate_url }}" style="background:#64748b;color:#fff;padding:8px 16px;text-decoration:none;border-radius:4px;">Escalate</a>
</p>
<p style="font-size:12px;color:#64748b;">If buttons do not work, use these links:<br>
Approve: {{ approve_url }}<br>
Reject: {{ reject_url }}<br>
Escalate: {{ escalate_url }}</p>
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


def render_acknowledgement(context: dict) -> tuple[str, str]:
    plain = _ENV.from_string(_ACK_PLAIN).render(**context)
    html = _ENV.from_string(_ACK_HTML).render(**context)
    return plain.strip(), html.strip()


def render_manager_escalation(context: dict) -> tuple[str, str]:
    plain = _ENV.from_string(_ESCALATION_PLAIN).render(**context)
    html = _ENV.from_string(_ESCALATION_HTML).render(**context)
    return plain.strip(), html.strip()


def render_daily_log(context: dict) -> tuple[str, str]:
    plain = _ENV.from_string(_DAILY_LOG_PLAIN).render(**context)
    html = _ENV.from_string(_DAILY_LOG_HTML).render(**context)
    return plain.strip(), html.strip()
