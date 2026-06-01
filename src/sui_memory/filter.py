from .config import SENSITIVE_PATTERNS


def contains_sensitive(text: str) -> bool:
    for pattern in SENSITIVE_PATTERNS:
        if pattern.search(text):
            return True
    return False
