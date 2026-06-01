import math
import struct
import time

import numpy as np

from .config import DB_PATH, RRF_K, HALF_LIFE_DAYS, TOP_K_DEFAULT
from .db import get_connection
from .embedder import Embedder


def _serialize_f32(vector: np.ndarray) -> bytes:
    return struct.pack(f"{len(vector)}f", *vector.astype(np.float32))


def _time_decay(created_at: float, half_life_days: float = HALF_LIFE_DAYS) -> float:
    age_days = (time.time() - created_at) / 86400
    if age_days < 0:
        age_days = 0
    return math.pow(0.5, age_days / half_life_days)


def _vector_search(conn, query_vec: np.ndarray, limit: int) -> list[tuple[int, int]]:
    """Returns list of (chunk_id, rank)."""
    rows = conn.execute(
        """
        SELECT chunk_id, distance
        FROM chunks_vec
        WHERE embedding MATCH ?
        ORDER BY distance
        LIMIT ?
        """,
        (_serialize_f32(query_vec), limit),
    ).fetchall()
    return [(row[0], rank + 1) for rank, row in enumerate(rows)]


def _fts_search(conn, query: str, limit: int) -> list[tuple[int, int]]:
    """Returns list of (chunk_id, rank)."""
    # FTS5 trigram: escape double quotes in query
    safe_query = query.replace('"', '""')
    try:
        rows = conn.execute(
            """
            SELECT c.id, rank
            FROM chunks_fts
            JOIN chunks c ON chunks_fts.rowid = c.id
            WHERE chunks_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (f'"{safe_query}"', limit),
        ).fetchall()
    except Exception:
        return []
    return [(row[0], rank + 1) for rank, row in enumerate(rows)]


def _rrf_merge(
    vec_results: list[tuple[int, int]],
    fts_results: list[tuple[int, int]],
    k: int = RRF_K,
) -> dict[int, float]:
    """Reciprocal Rank Fusion. Returns {chunk_id: score}."""
    scores: dict[int, float] = {}
    for chunk_id, rank in vec_results:
        scores[chunk_id] = scores.get(chunk_id, 0) + 1.0 / (k + rank)
    for chunk_id, rank in fts_results:
        scores[chunk_id] = scores.get(chunk_id, 0) + 1.0 / (k + rank)
    return scores


def hybrid_search(
    query: str,
    top_k: int = TOP_K_DEFAULT,
    project_path: str | None = None,
) -> list[dict]:
    embedder = Embedder.get()
    query_vec = embedder.embed_query(query)

    conn = get_connection()
    over_fetch = top_k * 3

    vec_results = _vector_search(conn, query_vec, over_fetch)
    fts_results = _fts_search(conn, query, over_fetch)

    rrf_scores = _rrf_merge(vec_results, fts_results)

    if not rrf_scores:
        conn.close()
        return []

    # Fetch chunk metadata
    chunk_ids = list(rrf_scores.keys())
    placeholders = ",".join("?" * len(chunk_ids))
    rows = conn.execute(
        f"""SELECT id, session_id, user_text, assistant_text,
                   combined_text, created_at, project_path
            FROM chunks WHERE id IN ({placeholders})""",
        chunk_ids,
    ).fetchall()
    conn.close()

    results = []
    for row in rows:
        chunk_id = row[0]
        created_at = row[5]
        proj = row[6]

        if project_path and proj != project_path:
            continue

        decay = _time_decay(created_at)
        final_score = rrf_scores[chunk_id] * decay

        results.append({
            "chunk_id": chunk_id,
            "session_id": row[1],
            "user_text": row[2],
            "assistant_text": row[3],
            "combined_text": row[4],
            "created_at": created_at,
            "project_path": proj,
            "score": final_score,
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]


def format_results(results: list[dict]) -> str:
    if not results:
        return "記憶が見つかりませんでした。"

    parts = []
    for i, r in enumerate(results, 1):
        ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(r["created_at"]))
        proj = r["project_path"] or "不明"
        parts.append(
            f"--- 記憶 {i} (スコア: {r['score']:.4f}, 日時: {ts}, プロジェクト: {proj}) ---\n"
            f"{r['combined_text']}\n"
        )
    return "\n".join(parts)
