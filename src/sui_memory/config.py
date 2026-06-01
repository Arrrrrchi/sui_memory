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

SENSITIVE_PATTERNS = [
    re.compile(r"(?:api[_-]?key|apikey)\s*[:=]\s*[\"']?[A-Za-z0-9_\-]{20,}", re.IGNORECASE),
    re.compile(r"[Bb]earer\s+[A-Za-z0-9_\-\.]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(?:aws_secret_access_key|secret_key)\s*[:=]\s*[\"']?[A-Za-z0-9/+=]{40}", re.IGNORECASE),
    re.compile(r"(?:password|passwd|pwd|secret|token)\s*[:=]\s*[\"']?[^\s\"']{8,}", re.IGNORECASE),
    re.compile(r"-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----"),
    re.compile(r"gh[ps]_[A-Za-z0-9_]{36,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"xox[bprs]-[A-Za-z0-9\-]{10,}"),
]
