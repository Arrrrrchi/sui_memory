#!/bin/bash
# Debounced auto-save: only runs the actual save if 5+ minutes since last save.
# Designed for PostToolUse hook - very lightweight when skipping.

LOCK_FILE="$HOME/.claude/sui-memory/.last_save"
INTERVAL=300  # 5 minutes

LAST=$(cat "$LOCK_FILE" 2>/dev/null || echo 0)
NOW=$(date +%s)
DIFF=$((NOW - LAST))

if [ $DIFF -lt $INTERVAL ]; then
    exit 0
fi

# Update timestamp immediately to prevent concurrent runs
echo "$NOW" > "$LOCK_FILE"

# Read hook input from stdin
INPUT=$(cat)
TRANSCRIPT_PATH=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('transcript_path',''))" 2>/dev/null)
SESSION_ID=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('session_id',''))" 2>/dev/null)

if [ -z "$TRANSCRIPT_PATH" ]; then
    exit 0
fi

# Fork to background and save
PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.0 "$HOME/.claude/sui-memory/.venv/bin/python" -c "
import sys
sys.path.insert(0, '$HOME/.claude/sui-memory/src')
from sui_memory.save import save_session
save_session('$TRANSCRIPT_PATH', '$SESSION_ID')
" >> "$HOME/.claude/sui-memory/save.log" 2>&1 &

exit 0
