"""PII redaction for logs/traces. User content in the DB is untouched;
anything emitted to logs, metrics labels, or error payloads passes through redact()."""
import re

EMAIL = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
PHONE = re.compile(r"(\+?\d[\d\s\-().]{7,}\d)")
AADHAAR = re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b")


def redact(text: str | None) -> str:
    if not text:
        return ""
    out = EMAIL.sub("[email]", text)
    out = AADHAAR.sub("[id-number]", out)
    out = PHONE.sub("[phone]", out)
    return out
