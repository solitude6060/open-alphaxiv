import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  ArrowRight,
  BookOpen,
  Bookmark,
  CheckCircle2,
  Clipboard,
  Database,
  Download,
  ExternalLink,
  FileSearch,
  GitBranch,
  HeartPulse,
  KeyRound,
  MessageSquare,
  Network,
  Plus,
  Quote,
  Search,
  Settings,
  ShieldCheck,
  Sparkles,
  Tags
} from "lucide-react";
import "./styles.css";

const API_URL = import.meta.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Paper = {
  id: number;
  title: string;
  abstract: string;
  authors: string[];
  arxiv_id: string;
  status: string;
  summary: string;
  bookmarked: boolean;
  tags: string[];
  chunk_count?: number;
  landing_url: string;
};

type Provider = {
  id: number;
  name: string;
  provider_type: string;
  model: string;
  health_status: string;
  has_api_key: boolean;
};

type GraphNode = {
  id: number;
  title: string;
  group: "seed" | "prior" | "derivative" | "related";
  year: number;
  citation_count: number;
};

type GraphEdge = {
  id: number;
  source: number;
  target: number;
  edge_type: string;
  score: number;
};

type ChatResult = {
  answer: string;
  citations: Array<{ chunk_id: number; section_path: string; score: number; text: string }>;
  retrieval: {
    provider: string;
    model: string;
    answer_mode: "mock" | "codex";
  };
};

type Chunk = {
  id: number;
  section_path: string;
  chunk_index: number;
  text: string;
  token_count: number;
};

type CodexStatus = {
  status: "ready" | "not_configured";
  codex_agent_enabled: boolean;
  codex_chat_available: boolean;
  codex_cli_available: boolean;
  codex_cli_path: string;
  codex_access_token_present: boolean;
  codex_api_key_present: boolean;
  codex_auth_json_configured: boolean;
  codex_default_auth_json_configured: boolean;
  auth_modes: string[];
  integration_boundary: string;
};

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {})
    }
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || response.statusText);
  }
  return response.json() as Promise<T>;
}

function App() {
  if (window.location.pathname === "/login") {
    return <LoginPage />;
  }

  const [providers, setProviders] = useState<Provider[]>([]);
  const [papers, setPapers] = useState<Paper[]>([]);
  const [selectedPaperId, setSelectedPaperId] = useState<number | null>(null);
  const [source, setSource] = useState("https://arxiv.org/abs/2201.08239");
  const [query, setQuery] = useState("What is the core contribution?");
  const [answerMode, setAnswerMode] = useState<"mock" | "codex">("mock");
  const [selectedText, setSelectedText] = useState("");
  const [chunks, setChunks] = useState<Chunk[]>([]);
  const [chatResult, setChatResult] = useState<ChatResult | null>(null);
  const [graphView, setGraphView] = useState("related");
  const [graph, setGraph] = useState<{ nodes: GraphNode[]; edges: GraphEdge[] } | null>(null);
  const [activeTool, setActiveTool] = useState<"assistant" | "notes" | "similar" | "codex">("assistant");
  const [codexStatus, setCodexStatus] = useState<CodexStatus | null>(null);
  const [status, setStatus] = useState("Loading local workspace");
  const [error, setError] = useState("");

  const selectedPaper = useMemo(
    () => papers.find((paper) => paper.id === selectedPaperId) || papers[0],
    [papers, selectedPaperId]
  );

  async function refresh() {
    const [providerRows, paperRows] = await Promise.all([
      request<Provider[]>("/api/providers"),
      request<Paper[]>("/api/papers")
    ]);
    let codex: CodexStatus | null = null;
    try {
      codex = await request<CodexStatus>("/api/codex/status");
    } catch {
      codex = null;
    }
    setProviders(providerRows);
    setPapers(paperRows);
    setCodexStatus(codex);
    if (!selectedPaperId && paperRows.length > 0) {
      setSelectedPaperId(paperRows[0].id);
    }
    setStatus("Ready");
  }

  useEffect(() => {
    refresh().catch((err) => {
      setError(String(err.message || err));
      setStatus("API unavailable");
    });
  }, []);

  useEffect(() => {
    if (selectedPaper) {
      loadPaperData(selectedPaper.id, graphView).catch((err) => setError(String(err.message || err)));
    }
  }, [selectedPaper?.id, graphView]);

  async function createMockProvider() {
    setError("");
    setStatus("Creating provider");
    const provider = await request<Provider>("/api/providers", {
      method: "POST",
      body: JSON.stringify({
        name: "MVP1 local mock",
        provider_type: "mock",
        provider_kind: "generation",
        model: "mvp1-cited-extractive",
        wire_api: "chat_completions",
        is_default: true
      })
    });
    await request(`/api/providers/${provider.id}/healthcheck`, { method: "POST" });
    await refresh();
  }

  async function ingestPaper() {
    setError("");
    setStatus("Ingesting paper");
    const paper = await request<Paper>("/api/papers", {
      method: "POST",
      body: JSON.stringify({ source })
    });
    setSelectedPaperId(paper.id);
    await refresh();
    await loadPaperData(paper.id, graphView);
    setStatus(`Paper ready: ${paper.title}`);
  }

  async function askPaper() {
    if (!selectedPaper) return;
    setError("");
    setStatus("Retrieving cited context");
    const result = await request<ChatResult>("/api/chat/messages", {
      method: "POST",
      body: JSON.stringify({
        paper_id: selectedPaper.id,
        query,
        selected_text: selectedText,
        answer_mode: answerMode
      })
    });
    setChatResult(result);
    setStatus("Answer generated");
  }

  async function loadPaperData(paperId: number, view: string) {
    const [chunkRows, graphData] = await Promise.all([
      request<Chunk[]>(`/api/papers/${paperId}/chunks`),
      request<{ nodes: GraphNode[]; edges: GraphEdge[] }>(
        `/api/papers/${paperId}/literature-graph?view=${view}`
      )
    ]);
    setChunks(chunkRows);
    setGraph(graphData);
  }

  async function toggleBookmark() {
    if (!selectedPaper) return;
    await request(`/api/papers/${selectedPaper.id}/bookmark`, {
      method: "POST",
      body: JSON.stringify({ bookmarked: !selectedPaper.bookmarked })
    });
    await refresh();
  }

  async function saveTags(value: string) {
    if (!selectedPaper) return;
    await request(`/api/papers/${selectedPaper.id}/tags`, {
      method: "POST",
      body: JSON.stringify({ tags: value.split(",").map((tag) => tag.trim()) })
    });
    await refresh();
  }

  function captureSelection(event: React.MouseEvent<HTMLElement>) {
    const selection = window.getSelection();
    if (!selection || selection.rangeCount === 0) return;
    const range = selection.getRangeAt(0);
    if (!event.currentTarget.contains(range.commonAncestorContainer)) return;
    const text = selection.toString().replace(/\s+/g, " ").trim();
    if (text.length >= 8) {
      setSelectedText(text.slice(0, 1800));
      setActiveTool("assistant");
    }
  }

  const graphNodes = graph?.nodes.slice(0, 8) || [];

  return (
    <main className="reader-shell">
      <header className="reader-topbar">
        <div className="brand-mark">
          <GitBranch size={22} />
          <span>Open AlphaXiv Local</span>
        </div>
        <form
          className="ingest-bar"
          onSubmit={(event) => {
            event.preventDefault();
            ingestPaper().catch((err) => setError(String(err.message || err)));
          }}
        >
          <Search size={17} />
          <input
            value={source}
            onChange={(event) => setSource(event.target.value)}
            aria-label="arXiv URL"
          />
          <button className="primary" type="submit">
            <Plus size={16} /> Import
          </button>
        </form>
        <div className="topbar-actions">
          <span className={codexStatus?.status === "ready" ? "health ready" : "health"}>
            <KeyRound size={15} /> Codex {codexStatus?.codex_chat_available ? "ready" : "local"}
          </span>
          <span className="health"><HeartPulse size={15} /> {status}</span>
        </div>
      </header>

      {error ? <div className="error-banner">{error}</div> : null}

      <section className="library-strip">
        <select
          value={selectedPaper?.id || ""}
          onChange={(event) => setSelectedPaperId(Number(event.target.value))}
          aria-label="Paper library"
        >
          {papers.map((paper) => (
            <option key={paper.id} value={paper.id}>
              {paper.title}
            </option>
          ))}
        </select>
        <button className="quiet-button" onClick={createMockProvider}>
          <Settings size={15} /> Mock provider
        </button>
        {selectedPaper ? (
          <a className="quiet-button" href={selectedPaper.landing_url} target="_blank" rel="noreferrer">
            <ExternalLink size={15} /> arXiv
          </a>
        ) : null}
        {selectedPaper ? (
          <a className="quiet-button" href={`${API_URL}/api/papers/${selectedPaper.id}/export.md`}>
            <Download size={15} /> Markdown
          </a>
        ) : null}
      </section>

      {selectedPaper ? (
        <section className="reader-layout">
          <article className="paper-reader" onMouseUp={captureSelection}>
            <div className="paper-title-row">
              <div>
                <span className="paper-kicker">arXiv:{selectedPaper.arxiv_id}</span>
                <h1>{selectedPaper.title}</h1>
                <p className="authors">{selectedPaper.authors.join(", ")}</p>
              </div>
              <button className="icon-button" onClick={toggleBookmark} aria-label="Bookmark paper">
                <Bookmark size={18} fill={selectedPaper.bookmarked ? "currentColor" : "none"} />
              </button>
            </div>

            <section className="reader-abstract">
              <h2>Abstract</h2>
              <p>{selectedPaper.abstract}</p>
            </section>

            <section className="reader-chunks">
              {chunks.map((chunk) => (
                <article className="chunk-block" key={chunk.id}>
                  <div className="chunk-heading">
                    <span>{chunk.section_path}</span>
                    <small>chunk {chunk.id}</small>
                  </div>
                  <p>{chunk.text}</p>
                </article>
              ))}
            </section>
          </article>

          <aside className="tool-panel">
            <nav className="tool-tabs" aria-label="Paper tools">
              {[
                ["assistant", MessageSquare],
                ["notes", Clipboard],
                ["similar", Network],
                ["codex", KeyRound]
              ].map(([name, Icon]) => (
                <button
                  key={String(name)}
                  className={activeTool === name ? "active" : ""}
                  onClick={() => setActiveTool(name as typeof activeTool)}
                  aria-label={String(name)}
                >
                  <Icon size={17} />
                </button>
              ))}
            </nav>

            {activeTool === "assistant" ? (
              <section className="tool-section">
                <div className="tool-heading">
                  <h2><Sparkles size={18} /> Assistant</h2>
                  <span>{answerMode === "codex" ? "codex" : `${chunks.length} chunks`}</span>
                </div>
                <div className="mode-switch" aria-label="Answer mode">
                  <button
                    className={answerMode === "mock" ? "active" : ""}
                    onClick={() => setAnswerMode("mock")}
                  >
                    Mock
                  </button>
                  <button
                    className={answerMode === "codex" ? "active" : ""}
                    onClick={() => setAnswerMode("codex")}
                    disabled={!codexStatus?.codex_chat_available}
                  >
                    Codex
                  </button>
                </div>
                {answerMode === "codex" && !codexStatus?.codex_chat_available ? (
                  <p className="codex-boundary">
                    Enable the local Codex agent in the backend before using Codex for paper chat.
                  </p>
                ) : null}
                {selectedText ? (
                  <div className="selected-quote">
                    <Quote size={15} />
                    <p>{selectedText}</p>
                    <button onClick={() => setSelectedText("")}>Clear</button>
                  </div>
                ) : null}
                <textarea value={query} onChange={(event) => setQuery(event.target.value)} />
                <button className="primary wide" onClick={askPaper}>
                  <MessageSquare size={16} /> Ask paper
                </button>
                {chatResult ? (
                  <div className="answer">
                    <div className="answer-meta">
                      {chatResult.retrieval.provider} / {chatResult.retrieval.model}
                    </div>
                    <p>{chatResult.answer}</p>
                    {chatResult.citations.map((citation) => (
                      <blockquote key={citation.chunk_id}>
                        <strong>chunk:{citation.chunk_id}</strong>
                        <span>{citation.section_path} · score {citation.score}</span>
                        <p>{citation.text}</p>
                      </blockquote>
                    ))}
                  </div>
                ) : null}
              </section>
            ) : null}

            {activeTool === "notes" ? (
              <section className="tool-section">
                <div className="tool-heading">
                  <h2><Tags size={18} /> Notes</h2>
                </div>
                <label className="field-label">
                  Tags
                  <input
                    defaultValue={selectedPaper.tags.join(", ")}
                    onBlur={(event) => saveTags(event.target.value)}
                  />
                </label>
                <div className="provider-list">
                  {providers.map((provider) => (
                    <div className="provider-row" key={provider.id}>
                      <strong>{provider.name}</strong>
                      <span>{provider.provider_type} / {provider.model}</span>
                      <small>{provider.health_status}</small>
                    </div>
                  ))}
                </div>
              </section>
            ) : null}

            {activeTool === "similar" ? (
              <section className="tool-section">
                <div className="graph-header compact">
                  <h2><GitBranch size={18} /> Similar</h2>
                  <div className="tabs">
                    {["related", "prior", "derivative"].map((view) => (
                      <button
                        key={view}
                        className={view === graphView ? "active" : ""}
                        onClick={() => setGraphView(view)}
                      >
                        {view}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="related-list">
                  {graphNodes.map((node) => (
                    <article key={node.id} className={`node-row ${node.group}`}>
                      <strong>{node.group}</strong>
                      <span>{node.title}</span>
                      <small>{node.year} · {node.citation_count} citations</small>
                    </article>
                  ))}
                </div>
              </section>
            ) : null}

            {activeTool === "codex" ? (
              <section className="tool-section">
                <div className="tool-heading">
                  <h2><KeyRound size={18} /> Codex</h2>
                  <span>{codexStatus?.status || "unknown"}</span>
                </div>
                <div className="codex-grid">
                  <StatusLine label="Agent enabled" value={codexStatus?.codex_agent_enabled} />
                  <StatusLine label="Paper chat" value={codexStatus?.codex_chat_available} />
                  <StatusLine label="CLI" value={codexStatus?.codex_cli_available} />
                  <StatusLine label="Access token" value={codexStatus?.codex_access_token_present} />
                  <StatusLine label="API key" value={codexStatus?.codex_api_key_present} />
                  <StatusLine label="Auth JSON" value={codexStatus?.codex_auth_json_configured} />
                  <StatusLine label="Default auth" value={codexStatus?.codex_default_auth_json_configured} />
                </div>
                <p className="codex-path">{codexStatus?.codex_cli_path}</p>
                <p className="codex-boundary">{codexStatus?.integration_boundary}</p>
                {!codexStatus?.codex_chat_available ? (
                  <div className="setup-code">
                    <strong>Docker setup</strong>
                    <code>bash scripts/check-codex-docker.sh</code>
                    <code>docker compose -f docker-compose.yml -f docker-compose.codex.yml up -d --build api web worker</code>
                  </div>
                ) : null}
                <div className="auth-modes">
                  {codexStatus?.auth_modes.map((mode) => <span key={mode}>{mode}</span>)}
                </div>
              </section>
            ) : null}
          </aside>
        </section>
      ) : (
        <div className="empty-state">
          <BookOpen size={28} />
          <h2>No paper imported</h2>
          <p>Paste an arXiv URL in the top bar.</p>
        </div>
      )}
    </main>
  );
}

function StatusLine({ label, value }: { label: string; value?: boolean }) {
  return (
    <div className={value ? "status-line ok" : "status-line"}>
      <CheckCircle2 size={16} />
      <span>{label}</span>
      <strong>{value ? "yes" : "no"}</strong>
    </div>
  );
}

function LoginPage() {
  return (
    <main className="login-page">
      <section className="login-hero" aria-label="Open AlphaXiv local entry">
        <div className="login-copy">
          <div className="login-mark">
            <GitBranch size={22} />
            <span>Open AlphaXiv Local</span>
          </div>
          <h1>Local research workspace</h1>
          <p>
            Read papers, ask cited questions, and inspect related work from one local Docker stack.
          </p>
          <div className="login-actions">
            <a className="login-primary" href="/">
              Enter workspace <ArrowRight size={17} />
            </a>
            <a className="login-secondary" href={`${API_URL}/docs`}>
              API docs
            </a>
          </div>
        </div>

        <div className="login-console" aria-label="Local service status">
          <div className="console-bar">
            <span />
            <span />
            <span />
            <strong>local stack</strong>
          </div>
          <div className="service-row ready">
            <ShieldCheck size={18} />
            <div>
              <strong>API</strong>
              <span>http://localhost:8000</span>
            </div>
            <em>ready</em>
          </div>
          <div className="service-row ready">
            <BookOpen size={18} />
            <div>
              <strong>Workspace</strong>
              <span>http://localhost:3100</span>
            </div>
            <em>ready</em>
          </div>
          <div className="service-row planned">
            <KeyRound size={18} />
            <div>
              <strong>Codex connector</strong>
              <span>local Codex auth status</span>
            </div>
            <em>optional</em>
          </div>
        </div>
      </section>

      <section className="login-capabilities" aria-label="Local capabilities">
        <article>
          <FileSearch size={20} />
          <strong>arXiv ingest</strong>
          <span>Metadata, Markdown, chunks, and citations.</span>
        </article>
        <article>
          <Network size={20} />
          <strong>Literature graph</strong>
          <span>Related, prior, and derivative views.</span>
        </article>
        <article>
          <Database size={20} />
          <strong>Local data</strong>
          <span>SQLite MVP state with Docker storage.</span>
        </article>
      </section>
    </main>
  );
}

function Graph({ graph }: { graph: { nodes: GraphNode[]; edges: GraphEdge[] } | null }) {
  if (!graph) return <div className="graph-empty">No graph loaded.</div>;
  const nodes = graph.nodes.slice(0, 28);
  const centerX = 360;
  const centerY = 230;
  const radius = 165;
  const positions = new Map<number, { x: number; y: number }>();
  nodes.forEach((node, index) => {
    if (index === 0) {
      positions.set(node.id, { x: centerX, y: centerY });
    } else {
      const angle = ((index - 1) / Math.max(1, nodes.length - 1)) * Math.PI * 2;
      positions.set(node.id, { x: centerX + Math.cos(angle) * radius, y: centerY + Math.sin(angle) * radius });
    }
  });
  const visible = new Set(nodes.map((node) => node.id));

  return (
    <div className="graph-wrap">
      <svg viewBox="0 0 720 460" role="img" aria-label="Literature graph">
        {graph.edges
          .filter((edge) => visible.has(edge.source) && visible.has(edge.target))
          .map((edge) => {
            const source = positions.get(edge.source)!;
            const target = positions.get(edge.target)!;
            return <line key={edge.id} x1={source.x} y1={source.y} x2={target.x} y2={target.y} />;
          })}
        {nodes.map((node) => {
          const position = positions.get(node.id)!;
          return (
            <g key={node.id} transform={`translate(${position.x} ${position.y})`}>
              <circle className={`node ${node.group}`} r={node.group === "seed" ? 18 : 10} />
              <title>{node.title}</title>
            </g>
          );
        })}
      </svg>
      <div className="node-list">
        {nodes.slice(0, 12).map((node) => (
          <div key={node.id} className={`node-row ${node.group}`}>
            <strong>{node.group}</strong>
            <span>{node.title}</span>
            <small>{node.year} · {node.citation_count} citations</small>
          </div>
        ))}
      </div>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
