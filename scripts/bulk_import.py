#!/usr/bin/env python3
"""Bulk import existing transcripts into the memory database."""
import glob
import sys
import os
import time

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(project_root, "src"))

from sui_memory.save import save_session
from sui_memory.db import init_db, get_connection


def main():
    init_db()

    # Find all main session transcripts (exclude subagent ones)
    patterns = [
        os.path.expanduser("~/.claude/projects/*/*.jsonl"),
    ]

    files = []
    for pattern in patterns:
        for f in glob.glob(pattern):
            if "/subagents/" not in f:
                files.append(f)

    # Check which sessions are already imported
    conn = get_connection()
    existing = set()
    try:
        rows = conn.execute("SELECT DISTINCT session_id FROM chunks").fetchall()
        existing = {row[0] for row in rows}
    finally:
        conn.close()

    total = len(files)
    skipped = 0
    imported = 0
    errors = 0

    print(f"Found {total} transcript files, {len(existing)} sessions already imported")

    for i, filepath in enumerate(files):
        session_id = os.path.splitext(os.path.basename(filepath))[0]
        if session_id in existing:
            skipped += 1
            continue

        try:
            saved = save_session(filepath, session_id)
            imported += 1
            if (imported % 10) == 0:
                print(f"  Progress: {i+1}/{total} files processed, {imported} imported, {skipped} skipped")
        except Exception as e:
            errors += 1
            print(f"  Error processing {filepath}: {e}", file=sys.stderr)

    print(f"\nDone! Imported: {imported}, Skipped: {skipped}, Errors: {errors}")

    # Print stats
    conn = get_connection()
    try:
        total_chunks = conn.execute("SELECT count(*) FROM chunks").fetchone()[0]
        total_sessions = conn.execute("SELECT count(DISTINCT session_id) FROM chunks").fetchone()[0]
        print(f"Total chunks in DB: {total_chunks}")
        print(f"Total sessions in DB: {total_sessions}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
