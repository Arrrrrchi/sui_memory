from .config import (
    TIER1_PATTERNS,
    TIER2_EMAIL,
    TIER2_EMAIL_EXCLUDE,
    TIER2_PATTERNS,
)


def contains_tier1(text: str | None) -> bool:
    """Tier1（シークレット + 高リスクPII）を含むか判定する。

    True の場合、その内容を含むチャンクは保存しない（丸ごと破棄）。
    """
    if not text:
        return False
    return any(pattern.search(text) for pattern in TIER1_PATTERNS)


def redact_tier2(text: str | None) -> str | None:
    """Tier2 PII（メアド / 電話 / 郵便 / 生年月日）をプレースホルダに置換して返す。

    保存拒否はせず、該当箇所のみをマスクして文脈を残す。
    None はそのまま返す（user_text / assistant_text が欠けるチャンク用）。
    """
    if not text:
        return text

    def _mask_email(match):
        email = match.group(0)
        # ダミー/テスト用ドメインは PII ではないため置換しない（baseline と同じ除外）
        if TIER2_EMAIL_EXCLUDE.search(email):
            return email
        return "[REDACTED_EMAIL]"

    text = TIER2_EMAIL.sub(_mask_email, text)
    for pattern, replacement in TIER2_PATTERNS:
        text = pattern.sub(replacement, text)
    return text
