import time
from pathlib import Path

from .chunker import parse_transcript
from .db import get_connection, init_db, insert_chunk
from .embedder import Embedder
from .filter import contains_sensitive


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

    # Filter out sensitive chunks
    safe_chunks = [c for c in chunks if not contains_sensitive(c.combined_text)]
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
