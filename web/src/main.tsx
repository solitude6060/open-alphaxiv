import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { Bookmark, Download, GitBranch, HeartPulse, MessageSquare, Plus, Search, Settings, Tags } from "lucide-react";
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
  const [providers, setProviders] = useState<Provider[]>([]);
  const [papers, setPapers] = useState<Paper[]>([]);
  const [selectedPaperId, setSelectedPaperId] = useState<number | null>(null);
  const [source, setSource] = useState("https://arxiv.org/abs/2201.08239");
  const [query, setQuery] = useState("What is the paper about?");
  const [chatResult, setChatResult] = useState<ChatResult | null>(null);
  const [graphView, setGraphView] = useState("related");
  const [graph, setGraph] = useState<{ nodes: GraphNode[]; edges: GraphEdge[] } | null>(null);
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
    setProviders(providerRows);
    setPapers(paperRows);
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
      loadGraph(selectedPaper.id, graphView).catch((err) => setError(String(err.message || err)));
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
    setStatus(`Paper ready: ${paper.title}`);
  }

  async function askPaper() {
    if (!selectedPaper) return;
    setError("");
    setStatus("Retrieving cited context");
    const result = await request<ChatResult>("/api/chat/messages", {
      method: "POST",
      body: JSON.stringify({ paper_id: selectedPaper.id, query })
    });
    setChatResult(result);
    setStatus("Answer generated");
  }

  async function loadGraph(paperId: number, view: string) {
    const data = await request<{ nodes: GraphNode[]; edges: GraphEdge[] }>(
      `/api/papers/${paperId}/literature-graph?view=${view}`
    );
    setGraph(data);
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

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <GitBranch size={24} />
          <div>
            <h1>Open AlphaXiv</h1>
            <p>MVP1 local research graph</p>
          </div>
        </div>

        <section className="panel">
          <h2><Settings size={16} /> Provider</h2>
          <button className="primary" onClick={createMockProvider}>
            <Plus size={16} /> Create local mock
          </button>
          {providers.map((provider) => (
            <div className="provider" key={provider.id}>
              <strong>{provider.name}</strong>
              <span>{provider.provider_type} / {provider.model}</span>
              <small>{provider.health_status}</small>
            </div>
          ))}
        </section>

        <section className="panel">
          <h2><Search size={16} /> Ingest</h2>
          <input value={source} onChange={(event) => setSource(event.target.value)} />
          <button className="primary" onClick={ingestPaper}>
            <Plus size={16} /> Ingest arXiv paper
          </button>
        </section>

        <section className="paper-list">
          {papers.map((paper) => (
            <button
              key={paper.id}
              className={paper.id === selectedPaper?.id ? "paper-item active" : "paper-item"}
              onClick={() => setSelectedPaperId(paper.id)}
            >
              <strong>{paper.title}</strong>
              <span>{paper.status} · {paper.chunk_count || 0} chunks</span>
            </button>
          ))}
        </section>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <span className="status"><HeartPulse size={16} /> {status}</span>
            {error ? <span className="error">{error}</span> : null}
          </div>
          {selectedPaper ? (
            <a className="download" href={`${API_URL}/api/papers/${selectedPaper.id}/export.md`}>
              <Download size={16} /> Export Markdown
            </a>
          ) : null}
        </header>

        {selectedPaper ? (
          <div className="content-grid">
            <article className="paper-detail">
              <div className="paper-actions">
                <button onClick={toggleBookmark}>
                  <Bookmark size={16} /> {selectedPaper.bookmarked ? "Bookmarked" : "Bookmark"}
                </button>
                <label>
                  <Tags size={16} />
                  <input
                    defaultValue={selectedPaper.tags.join(", ")}
                    onBlur={(event) => saveTags(event.target.value)}
                    placeholder="tags, separated, by comma"
                  />
                </label>
              </div>
              <h2>{selectedPaper.title}</h2>
              <p className="authors">{selectedPaper.authors.join(", ")}</p>
              <p>{selectedPaper.summary}</p>
              <a href={selectedPaper.landing_url} target="_blank" rel="noreferrer">Open source paper</a>
            </article>

            <section className="chat-panel">
              <h2><MessageSquare size={18} /> Cited Chat</h2>
              <textarea value={query} onChange={(event) => setQuery(event.target.value)} />
              <button className="primary" onClick={askPaper}>Ask with citations</button>
              {chatResult ? (
                <div className="answer">
                  <p>{chatResult.answer}</p>
                  {chatResult.citations.map((citation) => (
                    <blockquote key={citation.chunk_id}>
                      <strong>chunk:{citation.chunk_id}</strong> {citation.section_path} · score {citation.score}
                      <span>{citation.text}</span>
                    </blockquote>
                  ))}
                </div>
              ) : null}
            </section>

            <section className="graph-panel">
              <div className="graph-header">
                <h2><GitBranch size={18} /> Literature Graph</h2>
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
              <Graph graph={graph} />
            </section>
          </div>
        ) : (
          <div className="empty-state">
            <h2>No papers yet</h2>
            <p>Create the mock provider, then ingest an arXiv paper.</p>
          </div>
        )}
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

