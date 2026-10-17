import pytest

from app.redaction import redact

JWT = ("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
       "eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U")


@pytest.mark.parametrize("raw,expected", [
    (f"token={JWT}", "token=[REDACTED_JWT]"),
    ("mail bob.smith+x@example.co.uk now", "mail [REDACTED_EMAIL] now"),
    ("ip 192.168.1.10.", "ip [REDACTED_IP]."),
    ("from 0.0.0.0 to 255.255.255.255", "from [REDACTED_IP] to [REDACTED_IP]"),
    ("card 4111 1111 1111 1111 ok", "card [REDACTED_CARD] ok"),
    ("card 4111-1111-1111-1111", "card [REDACTED_CARD]"),
    ("card 4111111111111111", "card [REDACTED_CARD]"),
    ("amex 378282246310005", "amex [REDACTED_CARD]"),
])
def test_redacts(raw, expected):
    assert redact(raw) == expected


@pytest.mark.parametrize("raw", [
    "hello world",
    "4111 1111 1111 1112",       # fails Luhn
    "999.1.1.1",                 # invalid octet
    "256.256.256.256",
    "version 1.2.3",             # not an IP
    "1.2.3.4.5",                 # too many octets
    "order 12345",               # short number
    "not-an-email@",
])
def test_leaves_benign_text(raw):
    assert redact(raw) == raw


def test_multiple_in_one_message():
    out = redact(f"a@b.io 10.0.0.1 4111111111111111 {JWT}")
    assert out == "[REDACTED_EMAIL] [REDACTED_IP] [REDACTED_CARD] [REDACTED_JWT]"


def test_idempotent():
    once = redact("a@b.io 10.0.0.1")
    assert redact(once) == once


def test_amex_grouped():
    assert redact("3782 822463 10005") == "[REDACTED_CARD]"
