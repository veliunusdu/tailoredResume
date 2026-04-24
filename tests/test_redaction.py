from ajas.logger import redact_pii


def test_redact_pii_processor():
    """Verify structlog processor correctly strips PII from log events."""
    event_dict = {"event": "Contact test@example.com or +1 555 000 1111"}
    # The redact_pii processor modifies the dict in-place
    redacted = redact_pii(None, "info", event_dict)

    assert "test@example.com" not in redacted["event"]
    assert "[[EMAIL]]" in redacted["event"]
    assert "+1 555 000 1111" not in redacted["event"]
    assert "[[PHONE]]" in redacted["event"]


if __name__ == "__main__":
    # If run as script, use simple assert
    test_redact_pii_processor()
    print("Redaction test passed.")
