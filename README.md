# sui-memory

Claude Code の過去セッションを自動記憶し、自然言語で検索できる MCP サーバー。

## 概要

- セッション終了時にトランスクリプトを自動で SQLite に保存
- ベクトル検索（`sqlite-vec`）+ 全文検索（FTS5）のハイブリッド検索
- 時間減衰スコアリングにより新しい記憶を優先
- センシティブ情報（APIキー・パスワード・トークン等）を自動除外
- 日本語対応の埋め込みモデル（`cl-nagoya/ruri-v3-310m`）を使用

## 動作環境

- macOS（Apple Silicon / Intel）
- Python 3.11 以上
- [uv](https://github.com/astral-sh/uv)
- [Claude Code CLI](https://docs.anthropic.com/claude-code)

## セットアップ

### 1. クローン

```bash
git clone https://github.com/Arrrrrchi/sui-memory.git ~/.claude/sui-memory
```

### 2. 依存関係のインストール

```bash
cd ~/.claude/sui-memory
uv sync
```

初回起動時に埋め込みモデル（約600MB）が自動ダウンロードされます。

### 3. MCP サーバーを登録

```bash
claude mcp add sui-memory \
  ~/.claude/sui-memory/.venv/bin/python \
  -m sui_memory.mcp_server
```

### 4. フック（hooks）を設定

`~/.claude/settings.json` の `hooks` セクションに以下を追加します。

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.0 /Users/YOUR_USERNAME/.claude/sui-memory/.venv/bin/python /Users/YOUR_USERNAME/.claude/sui-memory/scripts/save_session.py",
            "timeout": 10000
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "/Users/YOUR_USERNAME/.claude/sui-memory/scripts/auto_save.sh",
            "timeout": 5000
          }
        ]
      }
    ]
  }
}
```

> `YOUR_USERNAME` をあなたの macOS ユーザー名に置き換えてください。

### 5. 動作確認

```bash
claude mcp list
# → sui-memory: ... ✓ Connected
```

## 使い方

Claude Code のセッション中に以下のツールが使えます。

### `memory_search`

過去のセッションを自然言語で検索します。

```
# 例
- 「先週のAPIキー設計の議論を検索して」
- 「マルチテナントのバグを調べた記憶を探して」
```

オプション：
- `query`（必須）: 検索クエリ（自然言語）
- `top_k`: 返す件数（デフォルト: 5）
- `project_path`: 特定プロジェクトに絞り込む（省略可）

### `memory_stats`

保存されている記憶の統計情報を表示します。

## アーキテクチャ

```
セッション終了 (Stop hook)
  → save_session.py
    → トランスクリプトをチャンク分割
    → センシティブ情報フィルタリング
    → 埋め込みベクトル生成（ruri-v3-310m）
    → SQLite (chunks テーブル + chunks_vec + chunks_fts) に保存

memory_search ツール呼び出し
  → クエリを埋め込みベクトル化
  → ベクトル検索 (sqlite-vec) + FTS5 全文検索
  → Reciprocal Rank Fusion でスコア統合
  → 時間減衰（半減期 30 日）を適用して上位 K 件を返す
```

## ファイル構成

```
sui-memory/
├── src/sui_memory/
│   ├── mcp_server.py   # MCP サーバーエントリポイント
│   ├── save.py         # セッション保存ロジック
│   ├── search.py       # ハイブリッド検索
│   ├── db.py           # SQLite 操作
│   ├── embedder.py     # 埋め込みモデル（シングルトン）
│   ├── chunker.py      # トランスクリプトのチャンク分割
│   ├── filter.py       # センシティブ情報フィルター
│   └── config.py       # 設定定数
├── scripts/
│   ├── save_session.py # Stop hook エントリポイント
│   └── auto_save.sh    # PostToolUse hook（5分デバウンス）
├── pyproject.toml
└── uv.lock
```

## 設定

`src/sui_memory/config.py` で主要パラメータを変更できます。

| 定数 | デフォルト | 説明 |
|------|-----------|------|
| `HALF_LIFE_DAYS` | 30 | 時間減衰の半減期（日） |
| `TOP_K_DEFAULT` | 5 | デフォルト検索件数 |
| `RRF_K` | 60 | RRF の定数 |
| `MAX_CHUNKS_PER_SESSION` | 200 | セッションあたりの最大チャンク数 |
| `MODEL_NAME` | `cl-nagoya/ruri-v3-310m` | 埋め込みモデル |

## ライセンス

MIT
