"""Normalize export formats without contacting Gmail or Discord."""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from email.utils import getaddresses, parsedate_to_datetime
import csv
import hashlib
import json
import mailbox
from pathlib import Path
import re
from typing import Iterator


def utc_timestamp(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Message timestamps must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat(timespec="microseconds")


def strip_quotes(body: str) -> str:
    """Conservatively remove common email quote blocks, not arbitrary prose."""
    kept = []
    for line in body.splitlines():
        if re.match(r"^\s*(On .+wrote:|-----Original Message-----)\s*$", line):
            break
        if not line.lstrip().startswith(">"):
            kept.append(line.rstrip())
    return "\n".join(kept).strip()


@dataclass(frozen=True)
class Message:
    id: str
    source: str
    thread: str
    author: str
    recipient: str
    timestamp: str
    body: str

    @classmethod
    def from_dict(cls, raw: dict) -> "Message":
        fields = {name: raw[name] for name in cls.__dataclass_fields__}
        if any(not isinstance(value, str) for value in fields.values()):
            raise ValueError("All message fields must be strings")
        fields = {name: value.strip() for name, value in fields.items()}
        fields["timestamp"] = utc_timestamp(fields["timestamp"])
        fields["author"] = fields["author"].casefold()
        fields["recipient"] = fields["recipient"].casefold()
        fields["body"] = strip_quotes(fields["body"])
        if any(not value for value in fields.values()):
            raise ValueError("Messages require nonempty IDs, provenance, participants, time, and body")
        return cls(**fields)

    @property
    def fingerprint(self) -> str:
        # Provider IDs are intentionally excluded so duplicate exports deduplicate.
        fields = asdict(self)
        del fields["id"]
        return hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()


@dataclass(frozen=True)
class ImportRecord:
    number: int
    message: Message | None = None
    error: str | None = None
    skipped: str | None = None


def _normalize(number: int, raw: dict) -> ImportRecord:
    try:
        return ImportRecord(number, message=Message.from_dict(raw))
    except KeyError as exc:
        return ImportRecord(number, error=f"Missing required field {exc}")
    except (ValueError, TypeError):
        # Reports never include raw message bodies or invalid field values.
        return ImportRecord(number, error="Invalid fields, empty body, or timestamp")


def scan_jsonl(path: str | Path) -> Iterator[ImportRecord]:
    with Path(path).open(encoding="utf-8-sig") as stream:
        for number, line in enumerate(stream, 1):
            if not line.strip():
                yield ImportRecord(number, skipped="Blank line")
                continue
            try:
                raw = json.loads(line)
            except ValueError:
                yield ImportRecord(number, error="Malformed JSON")
                continue
            if not isinstance(raw, dict):
                yield ImportRecord(number, error="Expected a JSON object")
            else:
                yield _normalize(number, raw)


def _strict(records: Iterator[ImportRecord]) -> Iterator[Message]:
    for record in records:
        if record.error:
            raise ValueError(f"Invalid message at record {record.number}: {record.error}")
        if record.message:
            yield record.message


def read_jsonl(path: str | Path) -> Iterator[Message]:
    yield from _strict(scan_jsonl(path))


def scan_mbox(path: str | Path) -> Iterator[ImportRecord]:
    """Read plain-text Gmail/standard MBOX messages; skip HTML-only mail."""
    box = mailbox.mbox(str(path), create=False)
    try:
        for number, mail in enumerate(box, 1):
            parts = mail.walk() if mail.is_multipart() else [mail]
            text = []
            body_error = False
            for part in parts:
                if part.get_content_type() == "text/plain" and part.get_content_disposition() != "attachment":
                    payload = part.get_payload(decode=True)
                    if payload:
                        try:
                            text.append(payload.decode(part.get_content_charset() or "utf-8", errors="replace"))
                        except LookupError:
                            body_error = True
                            break
            if body_error:
                yield ImportRecord(number, error="Unsupported text character encoding")
                continue
            if not text:
                yield ImportRecord(number, skipped="No supported plain-text body")
                continue
            try:
                author = getaddresses(mail.get_all("From", []))[0][1]
                recipients = getaddresses(mail.get_all("To", []))
                if not author or not recipients or any(not address for _, address in recipients):
                    raise ValueError("Missing participants")
                timestamp = parsedate_to_datetime(mail["Date"]).isoformat()
            except (ValueError, TypeError, IndexError, AttributeError):
                yield ImportRecord(number, error="Missing or invalid From, To, or Date header")
                continue
            body = "\n".join(text)
            message_id = mail.get("Message-ID") or hashlib.sha256(mail.as_bytes()).hexdigest()
            thread = mail.get("X-GM-THRID") or mail.get("References", "").split()[:1]
            if isinstance(thread, list):
                thread = thread[0] if thread else message_id
            for _, recipient in recipients:
                yield _normalize(number, dict(id=f"{message_id}:{recipient}", source="gmail", thread=thread,
                                             author=author, recipient=recipient, timestamp=timestamp, body=body))
    finally:
        box.close()


def read_mbox(path: str | Path) -> Iterator[Message]:
    yield from _strict(scan_mbox(path))


def scan_discord_csv(path: str | Path, *, author: str, recipient: str, thread: str) -> Iterator[ImportRecord]:
    """Official Discord package CSVs contain the account owner's outbound messages.

    Channel/contact mapping is supplied explicitly; incoming messages are not inferred.
    Export timestamps without a suffix are interpreted as UTC.
    """
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not {"ID", "Timestamp", "Contents"}.issubset(reader.fieldnames or []):
            yield ImportRecord(1, error="Expected Discord export columns ID, Timestamp, Contents")
            return
        for row in reader:
            number = reader.line_num
            if any(row.get(key) is None for key in ("ID", "Timestamp", "Contents")) or None in row:
                yield ImportRecord(number, error="Malformed CSV row")
                continue
            if not row["Contents"].strip():
                yield ImportRecord(number, skipped="Empty outbound message")
                continue
            try:
                timestamp = row["Timestamp"].strip()
                if datetime.fromisoformat(timestamp.replace("Z", "+00:00")).tzinfo is None:
                    timestamp += "+00:00"
            except ValueError:
                yield ImportRecord(number, error="Invalid timestamp")
                continue
            yield _normalize(number, dict(id=row["ID"], source="discord", thread=thread,
                                         author=author, recipient=recipient, timestamp=timestamp,
                                         body=row["Contents"]))


def read_discord_csv(path: str | Path, *, author: str, recipient: str, thread: str) -> Iterator[Message]:
    yield from _strict(scan_discord_csv(path, author=author, recipient=recipient, thread=thread))
