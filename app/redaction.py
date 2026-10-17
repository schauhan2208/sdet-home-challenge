"""Sensitive-data redaction. Applied BEFORE storage, so raw values never persist."""
import re

JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
OCTET = r"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)"
IPV4_RE = re.compile(rf"(?<!\d)(?<!\d\.)(?:{OCTET}\.){{3}}{OCTET}(?!\d|\.\d)")
# Contiguous 13-19 digits, 4-4-4-4(-3) groups, or Amex 4-6-5; Luhn-checked afterwards.
CARD_RE = re.compile(
    r"(?<![\d-])(?:\d{13,19}|\d{4}(?:[ -]\d{4}){2,3}(?:[ -]\d{1,3})?|\d{4}[ -]\d{6}[ -]\d{5})(?![\d-])"
)


def luhn_valid(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch)
        if i % 2 == 1:
            n = n * 2 - 9 if n * 2 > 9 else n * 2
        total += n
    return total % 10 == 0


def redact_card(match: re.Match) -> str:
    digits = re.sub(r"\D", "", match.group(0))
    if 13 <= len(digits) <= 19 and luhn_valid(digits):
        return "[REDACTED_CARD]"
    return match.group(0)


def redact(text: str) -> str:
    # Order matters: JWTs and emails first (they contain dots/digits that
    # could confuse the IP and card patterns). Placeholders contain no digits.
    text = JWT_RE.sub("[REDACTED_JWT]", text)
    text = EMAIL_RE.sub("[REDACTED_EMAIL]", text)
    text = IPV4_RE.sub("[REDACTED_IP]", text)
    text = CARD_RE.sub(redact_card, text)
    return text
