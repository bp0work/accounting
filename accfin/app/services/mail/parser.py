"""Parse RFC822 messages into intake DTOs."""

import email
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.message import Message
from email.utils import getaddresses, parsedate_to_datetime

from app.services.mail.normalize import content_hash, normalize_body, sha256_bytes

_CASE_NUMBER_RE = re.compile(r"\[CAS-\d{4}-\d{6,}\]", re.IGNORECASE)


@dataclass
class ParsedAttachment:
    filename: str
    mime_type: str
    content: bytes
    content_hash: str


@dataclass
class ParsedEmail:
    message_id: str
    from_address: str
    from_name: str | None
    to_addresses: list[str]
    cc_addresses: list[str]
    subject: str
    body_text: str | None
    body_html: str | None
    body_preview: str | None
    content_hash: str
    received_at: datetime
    attachments: list[ParsedAttachment] = field(default_factory=list)
    parsed_transaction_number: str | None = None


def _extract_addresses(header_value: str | None) -> list[str]:
    if not header_value:
        return []
    return [addr for _, addr in getaddresses([header_value]) if addr]


def _decode_part(part: Message) -> str:
    payload = part.get_payload(decode=True)
    if payload is None:
        return ""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except LookupError:
        return payload.decode("utf-8", errors="replace")


def _walk_body(msg: Message) -> tuple[str | None, str | None]:
    text_body: str | None = None
    html_body: str | None = None
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_disposition() == "attachment":
                continue
            content_type = part.get_content_type()
            if content_type == "text/plain" and text_body is None:
                text_body = _decode_part(part)
            elif content_type == "text/html" and html_body is None:
                html_body = _decode_part(part)
    else:
        if msg.get_content_type() == "text/html":
            html_body = _decode_part(msg)
        else:
            text_body = _decode_part(msg)
    return text_body, html_body


def _walk_attachments(msg: Message) -> list[ParsedAttachment]:
    attachments: list[ParsedAttachment] = []
    for part in msg.walk():
        disposition = part.get_content_disposition()
        if disposition not in ("attachment", "inline"):
            continue
        filename = part.get_filename()
        if not filename:
            continue
        raw = part.get_payload(decode=True) or b""
        attachments.append(
            ParsedAttachment(
                filename=filename,
                mime_type=part.get_content_type(),
                content=raw,
                content_hash=sha256_bytes(raw),
            )
        )
    return attachments


def parse_rfc822(raw: bytes, *, mailbox_address: str) -> ParsedEmail:
    msg = email.message_from_bytes(raw)
    message_id = (msg.get("Message-ID") or "").strip()
    if not message_id:
        message_id = f"generated-{sha256_bytes(raw)[:32]}@{mailbox_address}"

    subject = msg.get("Subject") or "(no subject)"
    text_body, html_body = _walk_body(msg)
    preview_source = text_body or _strip_html(html_body or "") or ""
    preview = preview_source[:500] if preview_source else None

    date_header = msg.get("Date")
    if date_header:
        try:
            received_at = parsedate_to_datetime(date_header)
            if received_at.tzinfo is None:
                received_at = received_at.replace(tzinfo=UTC)
        except (TypeError, ValueError, OverflowError):
            received_at = datetime.now(UTC)
    else:
        received_at = datetime.now(UTC)

    from_list = getaddresses([msg.get("From") or ""])
    from_address = from_list[0][1] if from_list else "unknown@unknown"
    from_name = from_list[0][0] or None

    match = _CASE_NUMBER_RE.search(subject)
    parsed_case = match.group(0).strip("[]") if match else None

    hash_source = text_body or html_body
    return ParsedEmail(
        message_id=message_id,
        from_address=from_address,
        from_name=from_name,
        to_addresses=_extract_addresses(msg.get("To")),
        cc_addresses=_extract_addresses(msg.get("Cc")),
        subject=subject[:500],
        body_text=text_body,
        body_html=html_body,
        body_preview=preview,
        content_hash=content_hash(hash_source),
        received_at=received_at,
        attachments=_walk_attachments(msg),
        parsed_transaction_number=parsed_case,
    )


def _strip_html(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html)
