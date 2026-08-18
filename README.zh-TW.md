# Open AlphaXiv

[English](README.md) | [繁體中文](README.zh-TW.md)

本機論文閱讀工具：匯入 arXiv 論文、針對內文提問、寫筆記。程式跑在你自己的機器上，模型與 coding agent（程式碼代理：Claude Code、Codex、Cursor 等）用你已經登入的帳號或自己的 API 金鑰。

本專案與 [alphaXiv](https://www.alphaxiv.org/) 無關，也不會連線 `alphaxiv.org`。

## 功能

- 用 arXiv 網址匯入論文，或上傳 PDF
- 在瀏覽器讀頁面、畫重點，並針對選取內容提問
- 用 Claude Code、Codex、OpenCode，或任何 OpenAI-compatible（相容 OpenAI HTTP 介面）的服務回答；也可以用內建 mock（不呼叫外部模型）
- 訂閱 arXiv 分類 feed（訂閱清單）；未開啟前只存 metadata（書目資料）
- 從 [Semantic Scholar](https://www.semanticscholar.org/) 看 related / prior / derivative（相關、先前、後續）論文
- 筆記、書籤、標籤、研究專案，以及 Markdown 匯出
- 提供 [MCP](https://modelcontextprotocol.io/)（Model Context Protocol，讓外部工具呼叫本機函式庫）介面，Cursor、Claude Code、Codex 可以直接搜尋與閱讀你的本機收藏

快取的 PDF 只供你自己閱讀與研究。下載請連回 [arXiv 摘要頁](https://arxiv.org/)。細節見 [NOTICE](NOTICE) 與 [法律邊界](docs/LEGAL_BOUNDARY.md)。

## 快速開始

**Docker**

```bash
docker compose up --build
```

接著開啟 http://127.0.0.1:3100（API 在 http://127.0.0.1:8000）。

```bash
WEB_PORT=3200 docker compose up -d
```

Compose 使用 SQLite。Claude Code 與 OpenCode 的登入在主機上，不在容器裡；若要在網頁裡用這兩個當助手，請改走下方原始碼安裝。

**從原始碼跑**

需要 Python 3.10+、Node.js 20+，以及 [Poppler](https://poppler.freedesktop.org/)（`pdftotext`、`pdftoppm`，用來抽全文與頁面圖）。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

```bash
cd web
npm install
npm run dev
```

開啟 http://127.0.0.1:3000。若 3000 已被佔用，改跑 `npm run dev -- --port 3310`，並把 API 的 `OPEN_ALPHAXIV_CORS_ORIGIN` 設成 `http://localhost:3310`。

## 設定

```bash
cp .env.example .env
```

| 變數 | 用途 |
| --- | --- |
| `OPEN_ALPHAXIV_CLAUDE_ENABLED=true` | 用本機已登入的 `claude` 回答論文問題 |
| `OPEN_ALPHAXIV_OPENCODE_ENABLED=true` | 用本機的 `opencode` 回答 |
| `OPEN_ALPHAXIV_CODEX_ENABLED=true` | 用本機的 `codex` 回答 |
| `SEMANTIC_SCHOLAR_API_KEY` | 文獻圖譜。沒有金鑰時，Semantic Scholar 常回 HTTP 429 |
| `OPEN_ALPHAXIV_ARXIV_CATEGORIES` | feed 分類，預設 `cs.LG` |
| `OPENAI_COMPATIBLE_BASE_URL` | 可選的 HTTP API。非 localhost 必須使用 `https` |

畫面上也可以新增 OpenAI-compatible 服務（含本機 Ollama）。金鑰留在伺服器端，不會打進前端打包檔。

## MCP

把本機 agent 指到 http://127.0.0.1:8000/mcp。這個埠請綁在 loopback（本機回環），不要公開到網際網路。

**Cursor**（`mcp.json`）：

```json
{
  "mcpServers": {
    "open-alphaxiv": {
      "url": "http://127.0.0.1:8000/mcp"
    }
  }
}
```

```bash
claude mcp add --transport http open-alphaxiv http://127.0.0.1:8000/mcp
codex mcp add open-alphaxiv --url http://127.0.0.1:8000/mcp
```

工具：`search_arxiv`、`ingest_paper`、`list_library`、`get_paper_text`、`query_paper_pages`、`save_note`、`list_notes`。

## 測試

```bash
python3 -m pytest
cd web && npm run build
```

## 授權

MIT。見 [LICENSE](LICENSE) 與 [NOTICE](NOTICE)。
