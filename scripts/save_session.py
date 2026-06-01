#!/usr/bin/env python3
"""Stop hook entry point: save session transcript to memory DB.

Reads hook input from stdin, immediately outputs {} to unblock Claude Code,
then forks a background process to perform the actual save.
"""
import json
import os
import sys


def main():
    # Read hook input from stdin
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        hook_input = {}

    # Prevent infinite loops if stop hook is re-triggered
    if hook_input.get("stop_hook_active", False):
        sys.exit(0)

    transcript_path = hook_input.get("transcript_path")
    session_id = hook_input.get("session_id")

    if not transcript_path:
        # No transcript, nothing to save
        sys.exit(0)

    # Fork to background so the hook returns immediately
    pid = os.fork()
    if pid > 0:
        # Parent: exit immediately (unblocks Claude Code)
        sys.exit(0)

    # Child: detach and do the actual save
    os.setsid()

    # Add project root to sys.path
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, os.path.join(project_root, "src"))

    try:
        from sui_memory.save import save_session
        saved = save_session(transcript_path, session_id)
        # Log to a file for debugging
        log_path = os.path.join(project_root, "save.log")
        with open(log_path, "a") as f:
            f.write(f"Saved {saved} chunks from session {session_id}\n")
    except Exception as e:
        log_path = os.path.join(project_root, "save.log")
        with open(log_path, "a") as f:
            f.write(f"Error saving session {session_id}: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
