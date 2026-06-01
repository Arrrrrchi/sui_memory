import json
from dataclasses import dataclass
from pathlib import Path

from .config import MIN_CHUNK_LENGTH, MAX_CHUNK_LENGTH, MAX_CHUNKS_PER_SESSION


@dataclass
class Chunk:
    user_text: str | None
    assistant_text: str | None
    combined_text: str


def _extract_text_from_content(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(block.get("text", ""))
                elif block.get("type") == "tool_result":
                    result_content = block.get("content", "")
                    if isinstance(result_content, str):
                        # tool_result のテキストは短縮して含める
                        if len(result_content) > 200:
                            result_content = result_content[:200] + "..."
                        parts.append(f"[ツール結果: {result_content}]")
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(parts)
    return ""


def _extract_assistant_text(content) -> str:
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "\n".join(parts)
    if isinstance(content, str):
        return content
    return ""


def parse_transcript(transcript_path: str | Path) -> tuple[list[Chunk], str | None, str | None]:
    """Parse a JSONL transcript into Q&A chunks.

    Returns (chunks, session_id, project_path).
    """
    path = Path(transcript_path)
    if not path.exists():
        return [], None, None

    messages = []
    session_id = None
    project_path = None

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            entry_type = entry.get("type")

            if session_id is None:
                session_id = entry.get("sessionId")
            if project_path is None:
                project_path = entry.get("cwd")

            # Skip non-message types
            if entry_type not in ("user", "assistant"):
                continue

            # Skip meta and sidechain messages
            if entry.get("isMeta", False) or entry.get("isSidechain", False):
                continue

            message = entry.get("message", {})
            role = message.get("role")
            content = message.get("content")

            if role == "user":
                text = _extract_text_from_content(content)
                if text.strip():
                    messages.append(("user", text.strip()))
            elif role == "assistant":
                text = _extract_assistant_text(content)
                if text.strip():
                    messages.append(("assistant", text.strip()))

    # Deduplicate consecutive same-role messages (merge them)
    merged = []
    for role, text in messages:
        if merged and merged[-1][0] == role:
            merged[-1] = (role, merged[-1][1] + "\n" + text)
        else:
            merged.append((role, text))

    # Group into Q&A pairs
    chunks = []
    i = 0
    while i < len(merged):
        user_text = None
        assistant_text = None

        if merged[i][0] == "user":
            user_text = merged[i][1]
            if i + 1 < len(merged) and merged[i + 1][0] == "assistant":
                assistant_text = merged[i + 1][1]
                i += 2
            else:
                i += 1
        elif merged[i][0] == "assistant":
            assistant_text = merged[i][1]
            i += 1

        parts = []
        if user_text:
            parts.append(f"Q: {user_text}")
        if assistant_text:
            parts.append(f"A: {assistant_text}")
        combined = "\n".join(parts)

        if len(combined) < MIN_CHUNK_LENGTH:
            continue

        # Split long chunks
        if len(combined) > MAX_CHUNK_LENGTH:
            for start in range(0, len(combined), MAX_CHUNK_LENGTH):
                sub = combined[start : start + MAX_CHUNK_LENGTH]
                if len(sub) >= MIN_CHUNK_LENGTH:
                    chunks.append(Chunk(
                        user_text=user_text,
                        assistant_text=assistant_text,
                        combined_text=sub,
                    ))
        else:
            chunks.append(Chunk(
                user_text=user_text,
                assistant_text=assistant_text,
                combined_text=combined,
            ))

        if len(chunks) >= MAX_CHUNKS_PER_SESSION:
            break

    return chunks, session_id, project_path
