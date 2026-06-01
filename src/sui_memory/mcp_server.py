"""MCP server exposing memory_search tool for Claude Code."""

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .db import init_db
from .search import hybrid_search, format_results

app = Server("sui-memory")


@app.list_tools()
async def list_tools():
    return [
        Tool(
            name="memory_search",
            description=(
                "過去のClaude Codeセッションの記憶を検索します。"
                "以前の会話内容、議論、決定事項などを意味的に検索できます。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "検索クエリ（自然言語）",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "返す結果数（デフォルト: 5）",
                        "default": 5,
                    },
                    "project_path": {
                        "type": "string",
                        "description": "特定プロジェクトのパスで絞り込む（省略可）",
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="memory_stats",
            description="メモリデータベースの統計情報を表示します。",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "memory_search":
        results = hybrid_search(
            query=arguments["query"],
            top_k=arguments.get("top_k", 5),
            project_path=arguments.get("project_path"),
        )
        return [TextContent(type="text", text=format_results(results))]

    elif name == "memory_stats":
        from .db import get_connection

        conn = get_connection()
        try:
            total_chunks = conn.execute("SELECT count(*) FROM chunks").fetchone()[0]
            total_sessions = conn.execute(
                "SELECT count(DISTINCT session_id) FROM chunks"
            ).fetchone()[0]
            projects = conn.execute(
                "SELECT DISTINCT project_path FROM chunks WHERE project_path IS NOT NULL"
            ).fetchall()
            project_list = [r[0] for r in projects]
        finally:
            conn.close()

        stats = (
            f"メモリ統計:\n"
            f"- 総チャンク数: {total_chunks}\n"
            f"- 総セッション数: {total_sessions}\n"
            f"- プロジェクト数: {len(project_list)}\n"
        )
        if project_list:
            stats += "- プロジェクト一覧:\n"
            for p in project_list[:20]:
                stats += f"  - {p}\n"

        return [TextContent(type="text", text=stats)]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    init_db()
    async with stdio_server() as (read, write):
        await app.run(read, write, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
