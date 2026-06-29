import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  ArrowRight,
  BookOpen,
  Bookmark,
  CheckCircle2,
  Clipboard,
  Crop,
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
  Tags,
  Type,
  Upload,
  X
} from "lucide-react";
import "./styles.css";

const API_URL = import.meta.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const CODEX_SYSTEM_PROMPT_STORAGE_KEY = "open-alphaxiv.codexSystemPrompt";
const CODEX_PROMPT_PRESETS = [
  {
    label: "Markdown zh-TW",
    value:
      "Answer in Traditional Chinese (Taiwan). Use Markdown with short headings and bullet lists when useful. Avoid Simplified Chinese. Keep technical terms precise and define uncommon terms briefly."
  },
  {
    label: "Structured JSON",
    value:
      'Return valid JSON only with this shape: {"summary": string, "evidence": string[], "limitations": string[]}. Do not wrap the JSON in Markdown fences.'
  },
  {
    label: "Concise English",
    value:
      "Answer in English. Use concise Markdown bullets. Separate claims from evidence and note missing information explicitly."
  }
];

type Paper = {
  id: number;
  title: string;
  abstract: string;
  authors: string[];
  arxiv_id: string;
  source_type: string;
  source_id: string;
  status: string;
  summary: string;
  bookmarked: boolean;
  tags: string[];
  chunk_count?: number;
  full_text_available?: boolean;
  page_image_count?: number;
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
  session_id: number;
  message_id: number;
  user_message_id: number;
  answer: string;
  citations: Array<{ chunk_id: number; section_path: string; score: number; text: string }>;
  retrieval: {
    provider: string;
    model: string;
    answer_mode: "mock" | "codex";
    context_strategy?: string;
    context_scope?: "selection" | "whole_paper";
    paper_context_chars?: number;
    selected_image?: ImageSelection | null;
  };
};

type ChatMessage = {
  id: number;
  session_id: number;
  role: "user" | "assistant";
  content: string;
  metadata: {
    provider?: string;
    model?: string;
    answer_mode?: "mock" | "codex";
    context_strategy?: string;
    context_scope?: "selection" | "whole_paper";
  };
  created_at: string;
};

type ChatSession = {
  id: number;
  paper_id: number;
  title: string;
  created_at: string;
  latest_message_at?: string;
  message_count?: number;
  messages?: ChatMessage[];
};

type PaperPage = {
  paper_id: number;
  page_number: number;
  image_url: string;
  text_layer_url?: string;
};

type PageTextWord = {
  text: string;
  x: number;
  y: number;
  width: number;
  height: number;
};

type PageTextLayer = {
  paper_id: number;
  page_number: number;
  width: number;
  height: number;
  words: PageTextWord[];
};

type PageTextLayersPayload = {
  paper_id: number;
  pages: PageTextLayer[];
};

type ImageSelection = {
  page: number;
  x: number;
  y: number;
  width: number;
  height: number;
};

type ImageDrag = {
  page: number;
  startX: number;
  startY: number;
  currentX: number;
  currentY: number;
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
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadInputKey, setUploadInputKey] = useState(0);
  const [query, setQuery] = useState("What is the core contribution?");
  const [answerMode, setAnswerMode] = useState<"mock" | "codex">("mock");
  const [codexSystemPrompt, setCodexSystemPrompt] = useState(() => {
    return window.localStorage.getItem(CODEX_SYSTEM_PROMPT_STORAGE_KEY) || "";
  });
  const [selectedText, setSelectedText] = useState("");
  const [selectedImage, setSelectedImage] = useState<ImageSelection | null>(null);
  const [imageDrag, setImageDrag] = useState<ImageDrag | null>(null);
  const [pages, setPages] = useState<PaperPage[]>([]);
  const [pageTextLayers, setPageTextLayers] = useState<Record<number, PageTextLayer>>({});
  const [selectionMode, setSelectionMode] = useState<"text" | "area">("text");
  const [chatSessions, setChatSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<number | null>(null);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
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

  useEffect(() => {
    setSelectedText("");
    setSelectedImage(null);
    setActiveSessionId(null);
    setChatMessages([]);
    if (selectedPaper) {
      loadChatSessions(selectedPaper.id).catch((err) => setError(String(err.message || err)));
    }
  }, [selectedPaper?.id]);

  useEffect(() => {
    window.localStorage.setItem(CODEX_SYSTEM_PROMPT_STORAGE_KEY, codexSystemPrompt);
  }, [codexSystemPrompt]);

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

  async function uploadLocalPaper() {
    if (!uploadFile) return;
    setError("");
    setStatus("Uploading local PDF");
    const params = new URLSearchParams({ filename: uploadFile.name });
    const response = await fetch(`${API_URL}/api/papers/upload?${params.toString()}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/pdf"
      },
      body: uploadFile
    });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(errorMessageFromResponse(text, response.statusText));
    }
    const paper = (await response.json()) as Paper;
    setUploadFile(null);
    setUploadInputKey((key) => key + 1);
    setSelectedPaperId(paper.id);
    await refresh();
    await loadPaperData(paper.id, graphView);
    setStatus(`Paper ready: ${paper.title}`);
  }

  async function askPaper() {
    if (!selectedPaper) return;
    const question = query.trim();
    if (!question) return;
    setError("");
    setStatus(answerMode === "codex" ? "Asking Codex with paper context" : "Asking local mock model");
    const result = await request<ChatResult>("/api/chat/messages", {
      method: "POST",
      body: JSON.stringify({
        paper_id: selectedPaper.id,
        query: question,
        session_id: activeSessionId,
        selected_text: selectedText,
        selected_image: selectedImage,
        system_prompt: answerMode === "codex" ? codexSystemPrompt : "",
        answer_mode: answerMode
      })
    });
    setActiveSessionId(result.session_id);
    await Promise.all([
      loadChatSession(result.session_id),
      refreshChatSessions(selectedPaper.id)
    ]);
    setQuery("");
    setStatus("Answer generated");
  }

  async function refreshChatSessions(paperId: number) {
    const sessions = await request<ChatSession[]>(`/api/papers/${paperId}/chat/sessions`);
    setChatSessions(sessions);
    return sessions;
  }

  async function loadChatSessions(paperId: number) {
    const sessions = await refreshChatSessions(paperId);
    const nextSessionId = sessions[0]?.id || null;
    setActiveSessionId(nextSessionId);
    if (nextSessionId) {
      await loadChatSession(nextSessionId);
    } else {
      setChatMessages([]);
    }
  }

  async function loadChatSession(sessionId: number) {
    const session = await request<ChatSession>(`/api/chat/sessions/${sessionId}`);
    setActiveSessionId(session.id);
    setChatMessages(session.messages || []);
  }

  async function startChatSession() {
    if (!selectedPaper) return;
    setError("");
    const session = await request<ChatSession>("/api/chat/sessions", {
      method: "POST",
      body: JSON.stringify({ paper_id: selectedPaper.id, title: "Paper chat" })
    });
    setChatSessions((sessions) => [session, ...sessions]);
    setActiveSessionId(session.id);
    setChatMessages([]);
  }

  async function loadPaperData(paperId: number, view: string) {
    setPageTextLayers({});
    const [pageRows, graphData] = await Promise.all([
      request<PaperPage[]>(`/api/papers/${paperId}/pages`),
      request<{ nodes: GraphNode[]; edges: GraphEdge[] }>(
        `/api/papers/${paperId}/literature-graph?view=${view}`
      )
    ]);
    setPages(pageRows);
    setGraph(graphData);
    if (pageRows.length === 0) {
      setPageTextLayers({});
      return;
    }
    try {
      const layerPayload = await request<PageTextLayersPayload>(`/api/papers/${paperId}/pages/text`);
      setPageTextLayers(
        Object.fromEntries(layerPayload.pages.map((layer) => [layer.page_number, layer] as const))
      );
    } catch {
      setPageTextLayers({});
    }
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

  function imagePoint(event: React.MouseEvent<HTMLDivElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    const x = Math.max(0, Math.min(100, ((event.clientX - rect.left) / rect.width) * 100));
    const y = Math.max(0, Math.min(100, ((event.clientY - rect.top) / rect.height) * 100));
    return { x, y };
  }

  function beginImageSelection(event: React.MouseEvent<HTMLDivElement>, page: number) {
    event.preventDefault();
    const point = imagePoint(event);
    setImageDrag({ page, startX: point.x, startY: point.y, currentX: point.x, currentY: point.y });
    setSelectedImage(null);
    setActiveTool("assistant");
  }

  function updateImageSelection(event: React.MouseEvent<HTMLDivElement>) {
    if (!imageDrag) return;
    event.preventDefault();
    const point = imagePoint(event);
    setImageDrag({ ...imageDrag, currentX: point.x, currentY: point.y });
  }

  function finishImageSelection() {
    if (!imageDrag) return;
    const x = Math.min(imageDrag.startX, imageDrag.currentX);
    const y = Math.min(imageDrag.startY, imageDrag.currentY);
    const width = Math.abs(imageDrag.currentX - imageDrag.startX);
    const height = Math.abs(imageDrag.currentY - imageDrag.startY);
    if (width >= 1 && height >= 1) {
      setSelectedImage({
        page: imageDrag.page,
        x: roundPercent(x),
        y: roundPercent(y),
        width: roundPercent(width),
        height: roundPercent(height)
      });
    }
    setImageDrag(null);
  }

  function imageSelectionBox(page: number) {
    const active = imageDrag?.page === page ? imageDrag : null;
    if (active) {
      return {
        left: Math.min(active.startX, active.currentX),
        top: Math.min(active.startY, active.currentY),
        width: Math.abs(active.currentX - active.startX),
        height: Math.abs(active.currentY - active.startY)
      };
    }
    if (selectedImage?.page === page) {
      return {
        left: selectedImage.x,
        top: selectedImage.y,
        width: selectedImage.width,
        height: selectedImage.height
      };
    }
    return null;
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
          <label className="upload-picker">
            <input
              key={uploadInputKey}
              type="file"
              accept="application/pdf,.pdf"
              onChange={(event) => setUploadFile(event.target.files?.[0] || null)}
              aria-label="Local PDF file"
            />
            <span>{uploadFile ? uploadFile.name : "PDF"}</span>
          </label>
          <button
            className="primary secondary"
            type="button"
            disabled={!uploadFile}
            onClick={() => uploadLocalPaper().catch((err) => setError(String(err.message || err)))}
          >
            <Upload size={16} /> Upload
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
        {selectedPaper?.landing_url ? (
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
            <div className="paper-toolbar">
              <div>
                <strong>{selectedPaper.title}</strong>
                <span>{paperSourceLabel(selectedPaper)}</span>
              </div>
              <div className="paper-toolbar-meta">
                {pages.length > 0 ? <span>{pages.length} pages</span> : null}
                <div className="selection-mode-switch" aria-label="PDF selection mode">
                  <button
                    className={selectionMode === "text" ? "active" : ""}
                    onClick={() => setSelectionMode("text")}
                    type="button"
                  >
                    <Type size={14} /> Text
                  </button>
                  <button
                    className={selectionMode === "area" ? "active" : ""}
                    onClick={() => setSelectionMode("area")}
                    type="button"
                  >
                    <Crop size={14} /> Area
                  </button>
                </div>
              </div>
              <button className="icon-button" onClick={toggleBookmark} aria-label="Bookmark paper">
                <Bookmark size={18} fill={selectedPaper.bookmarked ? "currentColor" : "none"} />
              </button>
            </div>

            {pages.length > 0 ? (
              <section className="pdf-reader-stage" aria-label="Paper PDF">
                <div className="pdf-page-list">
                  {pages.map((page) => {
                    const box = imageSelectionBox(page.page_number);
                    const textLayer = pageTextLayers[page.page_number];
                    return (
                      <article className="pdf-page-card" key={page.page_number}>
                        <div className="page-label">Page {page.page_number}</div>
                        <div
                          className={`page-frame ${selectionMode === "area" ? "area-mode" : "text-mode"}`}
                          onMouseDown={
                            selectionMode === "area"
                              ? (event) => beginImageSelection(event, page.page_number)
                              : undefined
                          }
                          onMouseMove={selectionMode === "area" ? updateImageSelection : undefined}
                          onMouseUp={selectionMode === "area" ? finishImageSelection : undefined}
                          onMouseLeave={selectionMode === "area" ? finishImageSelection : undefined}
                        >
                          <img src={assetUrl(page.image_url)} alt={`Paper page ${page.page_number}`} />
                          <div className="pdf-text-layer" aria-hidden="true">
                            {(textLayer?.words || []).map((word, index) => (
                              <span
                                className="pdf-word"
                                key={`${page.page_number}-${index}`}
                                style={{
                                  left: `${word.x}%`,
                                  top: `${word.y}%`,
                                  width: `${word.width}%`,
                                  height: `${word.height}%`,
                                  fontSize: `${Math.max(6, word.height * 7)}px`
                                }}
                              >
                                {word.text}{" "}
                              </span>
                            ))}
                          </div>
                          {box ? (
                            <div
                              className="image-selection"
                              style={{
                                left: `${box.left}%`,
                                top: `${box.top}%`,
                                width: `${box.width}%`,
                                height: `${box.height}%`
                              }}
                            />
                          ) : null}
                        </div>
                      </article>
                    );
                  })}
                </div>
              </section>
            ) : (
              <section className="pdf-empty-state">
                <BookOpen size={24} />
                <h2>PDF pages unavailable</h2>
                <p>
                  PDF page rendering is unavailable for this paper. The abstract remains available for reading and
                  question answering.
                </p>
                <div className="pdf-fallback-abstract">
                  <strong>Abstract</strong>
                  <p>{selectedPaper.abstract}</p>
                </div>
              </section>
            )}
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
                  <span>{answerMode === "codex" ? "full text" : "local mock"}</span>
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
                <div className="conversation-controls">
                  <select
                    value={activeSessionId || ""}
                    onChange={(event) => {
                      const sessionId = Number(event.target.value);
                      if (sessionId) {
                        loadChatSession(sessionId).catch((err) => setError(String(err.message || err)));
                      }
                    }}
                    aria-label="Conversation"
                  >
                    {chatSessions.length === 0 ? <option value="">New conversation</option> : null}
                    {chatSessions.map((session) => (
                      <option key={session.id} value={session.id}>
                        {session.title} · {session.message_count || 0} messages
                      </option>
                    ))}
                  </select>
                  <button type="button" onClick={() => startChatSession().catch((err) => setError(String(err.message || err)))} title="New conversation">
                    <Plus size={15} />
                  </button>
                </div>
                {answerMode === "codex" && codexSystemPrompt.trim() ? (
                  <div className="prompt-applied">
                    <KeyRound size={15} />
                    <span>Custom Codex prompt applied</span>
                  </div>
                ) : null}
                {selectedText ? (
                  <div className="selected-quote">
                    <Quote size={15} />
                    <p>{selectedText}</p>
                    <button onClick={() => setSelectedText("")}>Clear</button>
                  </div>
                ) : null}
                {selectedImage ? (
                  <div className="selected-image-card">
                    <Crop size={15} />
                    <p>
                      Page {selectedImage.page} · {selectedImage.width}% × {selectedImage.height}%
                    </p>
                    <button onClick={() => setSelectedImage(null)} aria-label="Clear selected image">
                      <X size={14} />
                    </button>
                  </div>
                ) : null}
                {!selectedText && !selectedImage ? (
                  <div className="whole-paper-context">
                    <BookOpen size={15} />
                    <span>Whole paper context will be sent when you ask.</span>
                  </div>
                ) : null}
                <div className="conversation-thread" aria-label="Paper conversation">
                  {chatMessages.length === 0 ? (
                    <div className="conversation-empty">Ask a question to start a paper conversation.</div>
                  ) : (
                    chatMessages.map((message) => (
                      <article className={`chat-message ${message.role}`} key={message.id}>
                        <div className="chat-message-meta">
                          <strong>{message.role === "assistant" ? "Assistant" : "You"}</strong>
                          {message.metadata?.provider ? (
                            <span>
                              {message.metadata.provider} / {message.metadata.model}
                              {message.metadata.context_scope === "whole_paper" ? " / whole paper" : ""}
                            </span>
                          ) : null}
                        </div>
                        {message.role === "assistant" ? (
                          <MarkdownAnswer markdown={message.content} />
                        ) : (
                          <p>{message.content}</p>
                        )}
                      </article>
                    ))
                  )}
                </div>
                <textarea
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Ask a follow-up about this paper..."
                />
                <button className="primary wide" onClick={askPaper}>
                  <MessageSquare size={16} /> Ask paper
                </button>
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
                <label className="field-label">
                  System prompt
                  <textarea
                    className="codex-system-prompt"
                    value={codexSystemPrompt}
                    onChange={(event) => setCodexSystemPrompt(event.target.value)}
                    placeholder="Example: Answer in Traditional Chinese. Use Markdown headings, bullets, and tables where useful."
                  />
                </label>
                <div className="prompt-actions" aria-label="Codex prompt presets">
                  {CODEX_PROMPT_PRESETS.map((preset) => (
                    <button
                      key={preset.label}
                      type="button"
                      onClick={() => setCodexSystemPrompt(preset.value)}
                    >
                      {preset.label}
                    </button>
                  ))}
                  <button type="button" onClick={() => setCodexSystemPrompt("")}>
                    Clear
                  </button>
                </div>
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
          <p>Paste an arXiv URL or upload a local PDF in the top bar.</p>
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

function MarkdownAnswer({ markdown }: { markdown: string }) {
  return <div className="markdown-answer">{renderMarkdownBlocks(markdown)}</div>;
}

function renderMarkdownBlocks(markdown: string) {
  const lines = markdown.replace(/\r\n/g, "\n").split("\n");
  const blocks: React.ReactNode[] = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];
    if (!line.trim()) {
      index += 1;
      continue;
    }

    if (line.trim().startsWith("```")) {
      const language = line.trim().slice(3).trim();
      const code: string[] = [];
      index += 1;
      while (index < lines.length && !lines[index].trim().startsWith("```")) {
        code.push(lines[index]);
        index += 1;
      }
      if (index < lines.length) index += 1;
      blocks.push(
        <pre key={`code-${index}`} className="markdown-code">
          {language ? <span>{language}</span> : null}
          <code>{code.join("\n")}</code>
        </pre>
      );
      continue;
    }

    const heading = /^(#{1,3})\s+(.+)$/.exec(line);
    if (heading) {
      const level = heading[1].length;
      const content = renderInlineMarkdown(heading[2], `heading-${index}`);
      blocks.push(
        level === 1 ? (
          <h3 key={`heading-${index}`}>{content}</h3>
        ) : level === 2 ? (
          <h4 key={`heading-${index}`}>{content}</h4>
        ) : (
          <h5 key={`heading-${index}`}>{content}</h5>
        )
      );
      index += 1;
      continue;
    }

    if (isMarkdownTable(lines, index)) {
      const tableLines = [lines[index]];
      index += 2;
      while (index < lines.length && lines[index].includes("|") && lines[index].trim()) {
        tableLines.push(lines[index]);
        index += 1;
      }
      blocks.push(renderMarkdownTable(tableLines, `table-${index}`));
      continue;
    }

    const listMatch = /^(\s*)([-*]|\d+\.)\s+(.+)$/.exec(line);
    if (listMatch) {
      const ordered = /^\d+\.$/.test(listMatch[2]);
      const items: string[] = [];
      while (index < lines.length) {
        const item = /^(\s*)([-*]|\d+\.)\s+(.+)$/.exec(lines[index]);
        if (!item || /^\d+\.$/.test(item[2]) !== ordered) break;
        items.push(item[3]);
        index += 1;
      }
      const ListTag = ordered ? "ol" : "ul";
      blocks.push(
        <ListTag key={`list-${index}`}>
          {items.map((item, itemIndex) => (
            <li key={`${index}-${itemIndex}`}>{renderInlineMarkdown(item, `list-${index}-${itemIndex}`)}</li>
          ))}
        </ListTag>
      );
      continue;
    }

    if (line.trim().startsWith(">")) {
      const quote: string[] = [];
      while (index < lines.length && lines[index].trim().startsWith(">")) {
        quote.push(lines[index].trim().replace(/^>\s?/, ""));
        index += 1;
      }
      blocks.push(
        <blockquote key={`quote-${index}`}>
          {renderInlineMarkdown(quote.join(" "), `quote-${index}`)}
        </blockquote>
      );
      continue;
    }

    const paragraph: string[] = [line.trim()];
    index += 1;
    while (index < lines.length && lines[index].trim() && !isMarkdownBlockStart(lines, index)) {
      paragraph.push(lines[index].trim());
      index += 1;
    }
    blocks.push(
      <p key={`paragraph-${index}`}>{renderInlineMarkdown(paragraph.join(" "), `paragraph-${index}`)}</p>
    );
  }

  return blocks;
}

function isMarkdownBlockStart(lines: string[], index: number) {
  const line = lines[index];
  return (
    line.trim().startsWith("```") ||
    /^(#{1,3})\s+/.test(line) ||
    /^(\s*)([-*]|\d+\.)\s+/.test(line) ||
    line.trim().startsWith(">") ||
    isMarkdownTable(lines, index)
  );
}

function isMarkdownTable(lines: string[], index: number) {
  if (index + 1 >= lines.length) return false;
  return (
    lines[index].includes("|") &&
    /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(lines[index + 1])
  );
}

function renderMarkdownTable(lines: string[], key: string) {
  const rows = lines.map(splitMarkdownTableRow);
  const [header, ...body] = rows;
  return (
    <div className="markdown-table-wrap" key={key}>
      <table>
        <thead>
          <tr>
            {header.map((cell, index) => (
              <th key={`${key}-head-${index}`}>{renderInlineMarkdown(cell, `${key}-head-${index}`)}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {body.map((row, rowIndex) => (
            <tr key={`${key}-row-${rowIndex}`}>
              {row.map((cell, cellIndex) => (
                <td key={`${key}-cell-${rowIndex}-${cellIndex}`}>
                  {renderInlineMarkdown(cell, `${key}-cell-${rowIndex}-${cellIndex}`)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function splitMarkdownTableRow(line: string) {
  return line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => cell.trim());
}

function renderInlineMarkdown(text: string, keyPrefix: string) {
  const nodes: React.ReactNode[] = [];
  const pattern = /(\[([^\]]+)\]\((https?:\/\/[^\s)]+|mailto:[^\s)]+)\)|`([^`]+)`|\*\*([^*]+)\*\*)/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      nodes.push(text.slice(lastIndex, match.index));
    }
    if (match[2] && match[3]) {
      nodes.push(
        <a key={`${keyPrefix}-${match.index}`} href={match[3]} target="_blank" rel="noreferrer">
          {match[2]}
        </a>
      );
    } else if (match[4]) {
      nodes.push(<code key={`${keyPrefix}-${match.index}`}>{match[4]}</code>);
    } else if (match[5]) {
      nodes.push(<strong key={`${keyPrefix}-${match.index}`}>{match[5]}</strong>);
    }
    lastIndex = pattern.lastIndex;
  }

  if (lastIndex < text.length) {
    nodes.push(text.slice(lastIndex));
  }
  return nodes;
}

function assetUrl(path: string) {
  return path.startsWith("http") ? path : `${API_URL}${path}`;
}

function errorMessageFromResponse(text: string, fallback: string) {
  try {
    const payload = JSON.parse(text) as { detail?: string };
    return payload.detail || text || fallback;
  } catch {
    return text || fallback;
  }
}

function paperSourceLabel(paper: Paper) {
  if (paper.source_type === "upload") {
    return `Upload:${paper.source_id.slice(0, 12)}`;
  }
  return `arXiv:${paper.arxiv_id}`;
}

function roundPercent(value: number) {
  return Math.round(value * 10) / 10;
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
          <span>Metadata, PDF text, page images, and Markdown export.</span>
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
