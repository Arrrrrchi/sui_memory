from pathlib import Path
import re

BASE_DIR = Path.home() / ".claude" / "sui-memory"
DB_PATH = BASE_DIR / "memory.db"

MODEL_NAME = "cl-nagoya/ruri-v3-310m"
QUERY_PREFIX = "検索クエリ: "
DOC_PREFIX = "検索文書: "

HALF_LIFE_DAYS = 30
TOP_K_DEFAULT = 5
RRF_K = 60

MAX_CHUNKS_PER_SESSION = 200
MIN_CHUNK_LENGTH = 50
MAX_CHUNK_LENGTH = 2000

# ============================================================
# PII / シークレットフィルタ
#
# ~/.claude/hooks/detect-pii-outbound.sh（AI開発基盤 baseline）の
# 検出パターンを Python へ翻訳し、2 段階で扱う。
#
#   TIER1_PATTERNS : 検出したらチャンクごと保存拒否
#                    - シークレット（APIキー/トークン/秘密鍵 等・従来から）
#                    - 高リスクPII（マイナンバー/クレカ/パスポート/免許/健保/口座）
#   TIER2_*        : 検出したら該当箇所を redact して保存
#                    - メアド/電話/郵便/生年月日
#
# baseline は無人ではなく人間へ「警告」する設計だが、本 MCP の保存は
# 無人バッチのため Tier2 は「redact して保存」に落としている。
# パターンを変更する場合は detect-pii-outbound.sh 側と揃えること。
# ============================================================

TIER1_PATTERNS = [
    # --- シークレット（従来の SENSITIVE_PATTERNS を継承） ---
    re.compile(r"(?:api[_-]?key|apikey)\s*[:=]\s*[\"']?[A-Za-z0-9_\-]{20,}", re.IGNORECASE),
    re.compile(r"[Bb]earer\s+[A-Za-z0-9_\-\.]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(?:aws_secret_access_key|secret_key)\s*[:=]\s*[\"']?[A-Za-z0-9/+=]{40}", re.IGNORECASE),
    re.compile(r"(?:password|passwd|pwd|secret|token)\s*[:=]\s*[\"']?[^\s\"']{8,}", re.IGNORECASE),
    re.compile(r"-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----"),
    re.compile(r"gh[ps]_[A-Za-z0-9_]{36,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"xox[bprs]-[A-Za-z0-9\-]{10,}"),
    # --- 高リスクPII（detect-pii-outbound.sh Tier1 の翻訳） ---
    # マイナンバー（個人番号 12桁・文脈付き）
    re.compile(r"(個人番号|マイナンバー)[^0-9]{0,20}[0-9]{12}"),
    # クレジットカード番号（Visa/Master/Discover/Amex）
    re.compile(
        r"(\b(4[0-9]{3}|5[1-5][0-9]{2}|6011)[ -]?[0-9]{4}[ -]?[0-9]{4}[ -]?[0-9]{4}\b"
        r"|\b3[47][0-9]{2}[ -]?[0-9]{6}[ -]?[0-9]{5}\b)"
    ),
    # パスポート番号（英字2文字 + 数字7桁）
    re.compile(r"\b[A-Z]{2}[0-9]{7}\b"),
    # 運転免許証番号（文脈付き 12桁）
    re.compile(r"(運転免許|免許証|免許番号|driver license)[^0-9]{0,20}[0-9]{12}"),
    # 健康保険証番号（文脈付き）
    re.compile(r"(健康保険|被保険者番号|保険証番号)[^0-9]{0,20}[0-9]{6,11}"),
    # 銀行口座番号（文脈付き）
    re.compile(
        r"(口座番号|普通預金|当座預金|普通\s+[0-9]{7}|当座\s+[0-9]{7})[^0-9]{0,20}[0-9]{7,8}"
    ),
]

# Tier2: メールアドレス（ダミー/テスト用ドメインは PII でないため置換しない）
TIER2_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
TIER2_EMAIL_EXCLUDE = re.compile(
    r"(example\.(com|org|net)|\.invalid|@test\.|@localhost|noreply@|no-reply@)"
)

# Tier2: (検出パターン, 置換後プレースホルダ)。マッチ箇所を redact して保存する。
TIER2_PATTERNS = [
    # 日本の電話番号（携帯 / 固定）
    (
        re.compile(
            r"(0[789]0[-‐ ]?[0-9]{4}[-‐ ]?[0-9]{4}"
            r"|0[1-9][0-9]?[-‐ ]?[0-9]{2,4}[-‐ ]?[0-9]{4})"
        ),
        "[REDACTED_PHONE]",
    ),
    # 日本の郵便番号（〒記号 or ハイフン区切り）
    (
        re.compile(r"(〒[0-9]{3}[-‐ ]?[0-9]{4}|\b[0-9]{3}-[0-9]{4}\b)"),
        "[REDACTED_POSTAL]",
    ),
    # 生年月日（文脈付き）
    (
        re.compile(
            r"(生年月日|誕生日|DOB|date\s+of\s+birth)[^0-9]{0,10}"
            r"((19|20)[0-9]{2}[年/.-][01]?[0-9][月/.-][0-3]?[0-9]"
            r"|(昭和|平成|令和)[0-9]{1,2}年)"
        ),
        "[REDACTED_DOB]",
    ),
]
