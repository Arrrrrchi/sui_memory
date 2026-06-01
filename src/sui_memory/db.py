import sqlite3
import struct
from pathlib import Path

import numpy as np
import sqlite_vec

from .config import DB_PATH


def _serialize_f32(vector: np.ndarray) -> bytes:
    return struct.pack(f"{len(vector)}f", *vector.astype(np.float32))


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or DB_PATH
    conn = sqlite3.connect(str(path))
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path | None = None) -> None:
    conn = get_connection(db_path)
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            user_text TEXT,
            assistant_text TEXT,
            combined_text TEXT NOT NULL,
            created_at REAL NOT NULL,
            project_path TEXT,
            UNIQUE(session_id, chunk_index)
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
            combined_text,
            content='chunks',
            content_rowid='id',
            tokenize='trigram'
        );

        CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
            INSERT INTO chunks_fts(rowid, combined_text)
            VALUES (new.id, new.combined_text);
        END;

        CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
            INSERT INTO chunks_fts(chunks_fts, rowid, combined_text)
            VALUES ('delete', old.id, old.combined_text);
        END;

        CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
            INSERT INTO chunks_fts(chunks_fts, rowid, combined_text)
            VALUES ('delete', old.id, old.combined_text);
            INSERT INTO chunks_fts(rowid, combined_text)
            VALUES (new.id, new.combined_text);
        END;
    """)

    cur.execute("""
        SELECT count(*) FROM sqlite_master
        WHERE type='table' AND name='chunks_vec'
    """)
    if cur.fetchone()[0] == 0:
        cur.execute("""
            CREATE VIRTUAL TABLE chunks_vec USING vec0(
                chunk_id INTEGER PRIMARY KEY,
                embedding float[768]
            )
        """)

    conn.commit()
    conn.close()


def insert_chunk(
    conn: sqlite3.Connection,
    session_id: str,
    chunk_index: int,
    user_text: str | None,
    assistant_text: str | None,
    combined_text: str,
    embedding: np.ndarray,
    created_at: float,
    project_path: str | None = None,
) -> int:
    cur = conn.cursor()
    cur.execute(
        """INSERT OR IGNORE INTO chunks
           (session_id, chunk_index, user_text, assistant_text,
            combined_text, created_at, project_path)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (session_id, chunk_index, user_text, assistant_text,
         combined_text, created_at, project_path),
    )
    if cur.rowcount == 0:
        return -1
    chunk_id = cur.lastrowid

    cur.execute(
        "INSERT INTO chunks_vec (chunk_id, embedding) VALUES (?, ?)",
        (chunk_id, _serialize_f32(embedding)),
    )
    return chunk_id
