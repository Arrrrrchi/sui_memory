import time
from dataclasses import replace
from pathlib import Path

from .chunker import parse_transcript
from .db import get_connection, init_db, insert_chunk
from .embedder import Embedder
from .filter import contains_tier1, redact_tier2


def save_session(transcript_path: str | Path, session_id: str | None = None) -> int:
    """Save a transcript to the memory database.

    Only embeds and inserts chunks that don't already exist (incremental save).
    Returns the number of new chunks saved.
    """
    init_db()
    chunks, parsed_session_id, project_path = parse_transcript(transcript_path)

    if not chunks:
        return 0

    sid = session_id or parsed_session_id or Path(transcript_path).stem

    # Tier1（シークレット + 高リスクPII）を含むチャンクは丸ごと破棄する。
    # combined_text は長文分割時にスライス断片になり、user_text / assistant_text
    # には全文が残るため、保存対象の 3 フィールドすべてを検査する。
    kept = [
        c for c in chunks
        if not (
            contains_tier1(c.combined_text)
            or contains_tier1(c.user_text)
            or contains_tier1(c.assistant_text)
        )
    ]

    # 残ったチャンクの Tier2 PII（メアド / 電話 / 郵便 / 生年月日）を redact する。
    # 埋め込み前に置換するので、PII は埋め込みベクトルにも DB にも残らない。
    safe_chunks = [
        replace(
            c,
            user_text=redact_tier2(c.user_text),
            assistant_text=redact_tier2(c.assistant_text),
            combined_text=redact_tier2(c.combined_text),
        )
        for c in kept
    ]
    if not safe_chunks:
        return 0

    # Check which chunk indices already exist for this session
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT chunk_index FROM chunks WHERE session_id = ?", (sid,)
        ).fetchall()
        existing_indices = {row[0] for row in rows}
    finally:
        conn.close()

    # Only process new chunks
    new_chunks = [
        (i, c) for i, c in enumerate(safe_chunks)
        if i not in existing_indices
    ]

    if not new_chunks:
        return 0

    # Batch embed only new chunks
    embedder = Embedder.get()
    texts = [c.combined_text for _, c in new_chunks]
    embeddings = embedder.embed_documents(texts)

    now = time.time()
    conn = get_connection()
    saved = 0

    try:
        for (idx, chunk), emb in zip(new_chunks, embeddings):
            result = insert_chunk(
                conn=conn,
                session_id=sid,
                chunk_index=idx,
                user_text=chunk.user_text,
                assistant_text=chunk.assistant_text,
                combined_text=chunk.combined_text,
                embedding=emb,
                created_at=now,
                project_path=project_path,
            )
            if result != -1:
                saved += 1
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return saved
