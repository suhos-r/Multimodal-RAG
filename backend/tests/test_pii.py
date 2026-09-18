"""Unit tests: PII redaction never lets emails/phones/IDs into logs."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.pii import redact


def test_email_redacted():
    assert "@" not in redact("contact me at jane.doe@example.com please")


def test_phone_redacted():
    out = redact("call +1 555-123-4567 tomorrow")
    assert "555" not in out and "[phone]" in out


def test_id_number_redacted():
    assert "1234" not in redact("aadhaar 1234 5678 9012 on file")


def test_clean_text_untouched():
    assert redact("Revenue grew 12 percent.") == "Revenue grew 12 percent."


def test_none_safe():
    assert redact(None) == "" and redact("") == ""
