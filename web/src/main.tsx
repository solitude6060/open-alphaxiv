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

const API_URL =
  import.meta.env.VITE_API_URL || import.meta.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
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

type ResearchProject = {
  id: number;
  title: string;
  slug: string;
  status: string;
  goal: string;
  current_state: string;
  note_count?: number;
  question_count?: number;
};

type ResearchQuestion = {
  id: number;
  project_id: number;
  question: string;
  status: string;
  current_answer: string;
};

type ResearchLink = {
  id: number;
  link_type: string;
  relation: string;
  target_id: string;
  label: string;
  quote: string;
  metadata: Record<string, unknown>;
};

type ResearchNote = {
  id: number;
  project_id: number;
  title: string;
  body_markdown: string;
  note_type: string;
  status: string;
  tags: string[];
  links: ResearchLink[];
};

type ExperimentRun = {
  id: number;
  project_id: number;
  title: string;
  status: string;
  hypothesis: string;
  dataset: string;
  code_ref: string;
  command: string;
  parameters: Record<string, unknown>;
  metrics: Record<string, unknown>;
  summary: string;
  artifact_count: number;
};

type ResearchDiscussion = {
  id: number;
  project_id: number;
  title: string;
  status: string;
  message_count: number;
  messages?: ResearchDiscussionMessage[];
};

type ResearchDiscussionMessage = {
  id: number;
  discussion_id: number;
  project_id: number;
  role: "user" | "assistant" | "system";
  content: string;
  metadata: Record<string, unknown>;
  created_at: string;
};

type GroundingSnapshot = {
  id: number;
  project_id: number;
  title: string;
  content_markdown: string;
  metadata: Record<string, unknown>;
};

type ResearchDashboard = {
  counts: Record<string, number>;
  active_projects: Array<ResearchProject & {
    question_count: number;
    note_count: number;
    experiment_run_count: number;
    discussion_count: number;
    grounding_snapshot_count: number;
  }>;
};

type ResearchSearchResult = {
  type: string;
  id: number;
  project_id: number;
  title: string;
  snippet: string;
  created_at: string;
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
  const [selectedTextPage, setSelectedTextPage] = useState<number | null>(null);
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
  const [researchProjects, setResearchProjects] = useState<ResearchProject[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(null);
  const [researchQuestions, setResearchQuestions] = useState<ResearchQuestion[]>([]);
  const [researchNotes, setResearchNotes] = useState<ResearchNote[]>([]);
  const [experimentRuns, setExperimentRuns] = useState<ExperimentRun[]>([]);
  const [researchDiscussions, setResearchDiscussions] = useState<ResearchDiscussion[]>([]);
  const [groundingSnapshots, setGroundingSnapshots] = useState<GroundingSnapshot[]>([]);
  const [researchDashboard, setResearchDashboard] = useState<ResearchDashboard | null>(null);
  const [researchSearchResults, setResearchSearchResults] = useState<ResearchSearchResult[]>([]);
  const [selectedDiscussionId, setSelectedDiscussionId] = useState<number | null>(null);
  const [selectedDiscussion, setSelectedDiscussion] = useState<ResearchDiscussion | null>(null);
  const [researchCodexBusy, setResearchCodexBusy] = useState(false);
  const [projectTitle, setProjectTitle] = useState("New research project");
  const [projectGoal, setProjectGoal] = useState("");
  const [projectCurrentState, setProjectCurrentState] = useState("");
  const [researchQuestion, setResearchQuestion] = useState("");
  const [noteTitle, setNoteTitle] = useState("");
  const [noteBody, setNoteBody] = useState("");
  const [experimentTitle, setExperimentTitle] = useState("");
  const [experimentDataset, setExperimentDataset] = useState("");
  const [experimentCodeRef, setExperimentCodeRef] = useState("");
  const [experimentCommand, setExperimentCommand] = useState("");
  const [experimentMetrics, setExperimentMetrics] = useState('{"metric": 0}');
  const [experimentSummary, setExperimentSummary] = useState("");
  const [discussionTitle, setDiscussionTitle] = useState("Research discussion");
  const [discussionMessage, setDiscussionMessage] = useState("");
  const [snapshotTitle, setSnapshotTitle] = useState("Grounding snapshot");
  const [researchSearchQuery, setResearchSearchQuery] = useState("");
  const [searchSelectedProjectOnly, setSearchSelectedProjectOnly] = useState(true);
  const [status, setStatus] = useState("Loading local workspace");
  const [error, setError] = useState("");

  const selectedPaper = useMemo(
    () => papers.find((paper) => paper.id === selectedPaperId) || papers[0],
    [papers, selectedPaperId]
  );
  const selectedProject = useMemo(
    () => researchProjects.find((project) => project.id === selectedProjectId) || null,
    [researchProjects, selectedProjectId]
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

  async function loadResearchDiscussion(discussionId: number) {
    setSelectedDiscussion(await request<ResearchDiscussion>(`/api/research/discussions/${discussionId}`));
  }

  async function refreshResearch(preferredProjectId?: number, preferredDiscussionId?: number | null) {
    const [projects, dashboard] = await Promise.all([
      request<ResearchProject[]>("/api/research/projects"),
      request<ResearchDashboard>("/api/research/dashboard")
    ]);
    setResearchProjects(projects);
    setResearchDashboard(dashboard);
    const nextProjectId = preferredProjectId || selectedProjectId || projects[0]?.id || null;
    setSelectedProjectId(nextProjectId);
    if (!nextProjectId) {
      setResearchQuestions([]);
      setResearchNotes([]);
      setExperimentRuns([]);
      setResearchDiscussions([]);
      setGroundingSnapshots([]);
      setSelectedDiscussionId(null);
      setSelectedDiscussion(null);
      return;
    }
    const [questions, notes, runs, discussions, snapshots] = await Promise.all([
      request<ResearchQuestion[]>(`/api/research/questions?project_id=${nextProjectId}`),
      request<ResearchNote[]>(`/api/research/notes?project_id=${nextProjectId}`),
      request<ExperimentRun[]>(`/api/experiments/runs?project_id=${nextProjectId}`),
      request<ResearchDiscussion[]>(`/api/research/discussions?project_id=${nextProjectId}`),
      request<GroundingSnapshot[]>(`/api/research/projects/${nextProjectId}/grounding-snapshots`)
    ]);
    setResearchQuestions(questions);
    setResearchNotes(notes);
    setExperimentRuns(runs);
    setResearchDiscussions(discussions);
    setGroundingSnapshots(snapshots);
    const currentDiscussionId = preferredDiscussionId || selectedDiscussionId;
    const nextDiscussionId =
      currentDiscussionId && discussions.some((discussion) => discussion.id === currentDiscussionId)
        ? currentDiscussionId
        : discussions[0]?.id || null;
    setSelectedDiscussionId(nextDiscussionId);
    if (nextDiscussionId) {
      if (nextDiscussionId === selectedDiscussionId) {
        await loadResearchDiscussion(nextDiscussionId);
      } else {
        setSelectedDiscussion(null);
      }
    } else {
      setSelectedDiscussion(null);
    }
  }

  useEffect(() => {
    Promise.all([refresh(), refreshResearch()]).catch((err) => {
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
    setSelectedTextPage(null);
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

  useEffect(() => {
    if (selectedProjectId) {
      refreshResearch(selectedProjectId).catch((err) => setError(String(err.message || err)));
    }
  }, [selectedProjectId]);

  useEffect(() => {
    if (!selectedDiscussionId) {
      setSelectedDiscussion(null);
      return;
    }
    loadResearchDiscussion(selectedDiscussionId).catch((err) => setError(String(err.message || err)));
  }, [selectedDiscussionId]);

  useEffect(() => {
    setProjectGoal(selectedProject?.goal || "");
    setProjectCurrentState(selectedProject?.current_state || "");
  }, [selectedProject?.id, selectedProject?.goal, selectedProject?.current_state]);

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

  async function createResearchProject() {
    const title = projectTitle.trim();
    if (!title) return;
    const project = await request<ResearchProject>("/api/research/projects", {
      method: "POST",
      body: JSON.stringify({ title, goal: "Track paper evidence and research progress." })
    });
    setProjectTitle("New research project");
    await refreshResearch(project.id);
  }

  async function addResearchQuestion() {
    if (!selectedProjectId || !researchQuestion.trim()) return;
    await request<ResearchQuestion>("/api/research/questions", {
      method: "POST",
      body: JSON.stringify({ project_id: selectedProjectId, question: researchQuestion.trim() })
    });
    setResearchQuestion("");
    await refreshResearch(selectedProjectId);
  }

  async function saveProjectState() {
    if (!selectedProjectId) return;
    await request<ResearchProject>(`/api/research/projects/${selectedProjectId}`, {
      method: "PATCH",
      body: JSON.stringify({
        goal: projectGoal,
        current_state: projectCurrentState
      })
    });
    await refreshResearch(selectedProjectId);
    setStatus("Research project state saved");
  }

  async function saveManualResearchNote() {
    if (!selectedProjectId || !noteTitle.trim()) return;
    await request<ResearchNote>("/api/research/notes", {
      method: "POST",
      body: JSON.stringify({
        project_id: selectedProjectId,
        title: noteTitle.trim(),
        body_markdown: noteBody,
        note_type: "idea",
        tags: []
      })
    });
    setNoteTitle("");
    setNoteBody("");
    await refreshResearch(selectedProjectId);
  }

  async function createExperimentRun() {
    if (!selectedProjectId || !experimentTitle.trim()) return;
    let metrics: Record<string, unknown> = {};
    try {
      metrics = experimentMetrics.trim() ? JSON.parse(experimentMetrics) : {};
    } catch {
      setError("Experiment metrics must be valid JSON");
      return;
    }
    await request<ExperimentRun>("/api/experiments/runs", {
      method: "POST",
      body: JSON.stringify({
        project_id: selectedProjectId,
        title: experimentTitle.trim(),
        dataset: experimentDataset,
        code_ref: experimentCodeRef,
        command: experimentCommand,
        metrics,
        summary: experimentSummary
      })
    });
    setExperimentTitle("");
    setExperimentDataset("");
    setExperimentCodeRef("");
    setExperimentCommand("");
    setExperimentMetrics('{"metric": 0}');
    setExperimentSummary("");
    await refreshResearch(selectedProjectId);
    setStatus("Experiment run saved");
  }

  async function saveExperimentRunToResearch(run: ExperimentRun) {
    if (!selectedProjectId) return;
    await request<ResearchNote>(`/api/experiments/runs/${run.id}/research-note`, {
      method: "POST",
      body: JSON.stringify({ project_id: selectedProjectId, title: `Experiment: ${run.title}` })
    });
    await refreshResearch(selectedProjectId);
    setStatus("Experiment run saved to research notes");
  }

  async function createResearchDiscussion() {
    if (!selectedProjectId || !discussionTitle.trim()) return;
    const discussion = await request<ResearchDiscussion>("/api/research/discussions", {
      method: "POST",
      body: JSON.stringify({ project_id: selectedProjectId, title: discussionTitle.trim() })
    });
    setSelectedDiscussionId(discussion.id);
    setDiscussionTitle("Research discussion");
    await refreshResearch(selectedProjectId, discussion.id);
    setStatus("Research discussion created");
  }

  async function addResearchDiscussionMessage() {
    if (!selectedProjectId || !selectedDiscussionId || !discussionMessage.trim()) return;
    await request(`/api/research/discussions/${selectedDiscussionId}/messages`, {
      method: "POST",
      body: JSON.stringify({ role: "user", content: discussionMessage.trim() })
    });
    setDiscussionMessage("");
    await refreshResearch(selectedProjectId, selectedDiscussionId);
    setStatus("Discussion message saved");
  }

  async function askResearchDiscussionCodex() {
    if (!selectedProjectId || !selectedDiscussionId || !discussionMessage.trim() || researchCodexBusy) return;
    setStatus("Asking Codex about research discussion");
    setResearchCodexBusy(true);
    try {
      await request(`/api/research/discussions/${selectedDiscussionId}/codex`, {
        method: "POST",
        body: JSON.stringify({
          content: discussionMessage.trim(),
          system_prompt: codexSystemPrompt
        })
      });
      setDiscussionMessage("");
      await refreshResearch(selectedProjectId, selectedDiscussionId);
      setStatus("Codex discussion answer saved");
    } finally {
      setResearchCodexBusy(false);
    }
  }

  async function createGroundingSnapshot() {
    if (!selectedProjectId || !snapshotTitle.trim()) return;
    await request<GroundingSnapshot>(`/api/research/projects/${selectedProjectId}/grounding-snapshots`, {
      method: "POST",
      body: JSON.stringify({ title: snapshotTitle.trim() })
    });
    setSnapshotTitle("Grounding snapshot");
    await refreshResearch(selectedProjectId);
    setStatus("Grounding snapshot saved");
  }

  async function runResearchSearch() {
    const queryText = researchSearchQuery.trim();
    if (!queryText) {
      setResearchSearchResults([]);
      return;
    }
    const params = new URLSearchParams({ q: queryText });
    if (searchSelectedProjectOnly && selectedProjectId) {
      params.set("project_id", String(selectedProjectId));
    }
    const results = await request<ResearchSearchResult[]>(`/api/research/search?${params.toString()}`);
    setResearchSearchResults(results);
    setStatus(`Found ${results.length} research results`);
  }

  async function saveSelectedPassageToResearch() {
    if (!selectedPaper || !selectedProjectId || !selectedText.trim()) return;
    await request<ResearchNote>(`/api/papers/${selectedPaper.id}/research-notes`, {
      method: "POST",
      body: JSON.stringify({
        project_id: selectedProjectId,
        title: `Passage from ${selectedPaper.title}`,
        selected_text: selectedText,
        page_number: selectedTextPage
      })
    });
    await refreshResearch(selectedProjectId);
    setStatus("Passage saved to research notes");
  }

  async function saveAssistantMessageToResearch(message: ChatMessage) {
    if (!selectedProjectId) return;
    await request<ResearchNote>(`/api/chat/messages/${message.id}/research-note`, {
      method: "POST",
      body: JSON.stringify({ project_id: selectedProjectId, title: `Answer: ${message.content.slice(0, 48)}` })
    });
    await refreshResearch(selectedProjectId);
    setStatus("Assistant answer saved to research notes");
  }

  async function archiveResearchNote(noteId: number) {
    if (!selectedProjectId) return;
    await request<ResearchNote>(`/api/research/notes/${noteId}`, {
      method: "PATCH",
      body: JSON.stringify({ status: "archived" })
    });
    await refreshResearch(selectedProjectId);
  }

  async function archiveResearchProject() {
    if (!selectedProjectId) return;
    await request<ResearchProject>(`/api/research/projects/${selectedProjectId}`, {
      method: "PATCH",
      body: JSON.stringify({ status: "archived" })
    });
    await refreshResearch(selectedProjectId);
  }

  function captureSelection(event: React.MouseEvent<HTMLElement>) {
    const selection = window.getSelection();
    if (!selection || selection.rangeCount === 0) return;
    const range = selection.getRangeAt(0);
    if (!event.currentTarget.contains(range.commonAncestorContainer)) return;
    const text = selection.toString().replace(/\s+/g, " ").trim();
    if (text.length >= 8) {
      const container =
        range.commonAncestorContainer.nodeType === Node.ELEMENT_NODE
          ? (range.commonAncestorContainer as Element)
          : range.commonAncestorContainer.parentElement;
      const pageElement = container?.closest<HTMLElement>("[data-page-number]");
      const pageNumber = Number(pageElement?.dataset.pageNumber || "");
      setSelectedText(text.slice(0, 1800));
      setSelectedTextPage(Number.isFinite(pageNumber) ? pageNumber : null);
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
                      <article className="pdf-page-card" key={page.page_number} data-page-number={page.page_number}>
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
                    <p>{selectedTextPage ? `Page ${selectedTextPage}: ` : ""}{selectedText}</p>
                    <button
                      onClick={() => {
                        setSelectedText("");
                        setSelectedTextPage(null);
                      }}
                    >
                      Clear
                    </button>
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
                          {message.role === "assistant" && selectedProjectId ? (
                            <button
                              className="inline-icon-button"
                              type="button"
                              onClick={() =>
                                saveAssistantMessageToResearch(message).catch((err) =>
                                  setError(String(err.message || err))
                                )
                              }
                              title="Save answer to research notes"
                            >
                              <Clipboard size={13} />
                            </button>
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
                  <h2><Tags size={18} /> Research</h2>
                  <span>{researchProjects.length} projects</span>
                </div>
                {researchDashboard ? (
                  <div className="research-list">
                    <strong>Status dashboard</strong>
                    <div className="metric-grid">
                      {[
                        ["Projects", researchDashboard.counts.projects],
                        ["Questions", researchDashboard.counts.questions],
                        ["Notes", researchDashboard.counts.notes],
                        ["Runs", researchDashboard.counts.experiment_runs],
                        ["Discussions", researchDashboard.counts.discussions],
                        ["Snapshots", researchDashboard.counts.grounding_snapshots]
                      ].map(([label, value]) => (
                        <span key={label}>
                          <b>{String(value || 0)}</b>
                          {label}
                        </span>
                      ))}
                    </div>
                    {researchDashboard.active_projects.slice(0, 3).map((project) => (
                      <article key={project.id} className="research-row">
                        <p>{project.title}</p>
                        <small>
                          {project.question_count} questions · {project.note_count} notes ·{" "}
                          {project.experiment_run_count} runs · {project.discussion_count} discussions
                        </small>
                      </article>
                    ))}
                  </div>
                ) : null}
                <div className="research-create-row">
                  <input
                    value={projectTitle}
                    onChange={(event) => setProjectTitle(event.target.value)}
                    aria-label="Research project title"
                  />
                  <button
                    type="button"
                    onClick={() => createResearchProject().catch((err) => setError(String(err.message || err)))}
                    title="Create research project"
                  >
                    <Plus size={15} />
                  </button>
                </div>
                {researchProjects.length > 0 ? (
                  <select
                    value={selectedProjectId || ""}
                    onChange={(event) => setSelectedProjectId(Number(event.target.value) || null)}
                    aria-label="Research project"
                  >
                    {researchProjects.map((project) => (
                      <option key={project.id} value={project.id}>
                        {project.title} · {project.status}
                      </option>
                    ))}
                  </select>
                ) : (
                  <div className="conversation-empty">Create a project to start persistent research notes.</div>
                )}
                <div className="research-list">
                  <strong>Search research</strong>
                  <div className="research-create-row">
                    <input
                      value={researchSearchQuery}
                      onChange={(event) => setResearchSearchQuery(event.target.value)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter") {
                          runResearchSearch().catch((err) => setError(String(err.message || err)));
                        }
                      }}
                      placeholder="Search notes, runs, discussions..."
                      aria-label="Search research"
                    />
                    <button
                      type="button"
                      onClick={() => runResearchSearch().catch((err) => setError(String(err.message || err)))}
                      title="Search research"
                    >
                      <Search size={15} />
                    </button>
                  </div>
                  <label className="inline-toggle">
                    <input
                      type="checkbox"
                      checked={searchSelectedProjectOnly}
                      onChange={(event) => setSearchSelectedProjectOnly(event.target.checked)}
                    />
                    Selected project only
                  </label>
                  {researchSearchResults.length === 0 ? (
                    <span>No search results.</span>
                  ) : (
                    researchSearchResults.map((result) => (
                      <article key={`${result.type}-${result.id}`} className="research-row">
                        <span>{result.type.replaceAll("_", " ")}</span>
                        <p>{result.title}</p>
                        {result.snippet ? <small>{result.snippet}</small> : null}
                      </article>
                    ))
                  )}
                </div>
                {selectedProjectId ? (
                  <div className="research-actions">
                    <a
                      className="quiet-button"
                      href={`${API_URL}/api/research/projects/${selectedProjectId}/export.md`}
                    >
                      <Download size={14} /> Export
                    </a>
                    <button
                      className="quiet-button"
                      type="button"
                      onClick={() => archiveResearchProject().catch((err) => setError(String(err.message || err)))}
                    >
                      Archive project
                    </button>
                  </div>
                ) : null}
                {selectedProjectId ? (
                  <>
                    <label className="field-label">
                      Project goal
                      <textarea
                        value={projectGoal}
                        onChange={(event) => setProjectGoal(event.target.value)}
                        placeholder="What does this research direction need to answer?"
                      />
                    </label>
                    <label className="field-label">
                      Current state
                      <textarea
                        value={projectCurrentState}
                        onChange={(event) => setProjectCurrentState(event.target.value)}
                        placeholder="What is known, blocked, or next?"
                      />
                    </label>
                    <button
                      className="quiet-button wide-button"
                      type="button"
                      onClick={() => saveProjectState().catch((err) => setError(String(err.message || err)))}
                    >
                      <Clipboard size={15} /> Save project state
                    </button>
                    <label className="field-label">
                      Research question
                      <input
                        value={researchQuestion}
                        onChange={(event) => setResearchQuestion(event.target.value)}
                        placeholder="What are we trying to learn?"
                      />
                    </label>
                    <button
                      className="primary wide"
                      type="button"
                      onClick={() => addResearchQuestion().catch((err) => setError(String(err.message || err)))}
                    >
                      <Plus size={16} /> Add question
                    </button>
                    <label className="field-label">
                      Note title
                      <input
                        value={noteTitle}
                        onChange={(event) => setNoteTitle(event.target.value)}
                        placeholder="Research note title"
                      />
                    </label>
                    <textarea
                      value={noteBody}
                      onChange={(event) => setNoteBody(event.target.value)}
                      placeholder="Write a Markdown research note..."
                    />
                    <button
                      className="primary wide"
                      type="button"
                      onClick={() => saveManualResearchNote().catch((err) => setError(String(err.message || err)))}
                    >
                      <Clipboard size={16} /> Save note
                    </button>
                    {selectedText ? (
                      <button
                        className="quiet-button wide-button"
                        type="button"
                        onClick={() =>
                          saveSelectedPassageToResearch().catch((err) => setError(String(err.message || err)))
                        }
                      >
                        <Quote size={15} /> Save selected passage
                      </button>
                    ) : null}
                    <label className="field-label">
                      Experiment title
                      <input
                        value={experimentTitle}
                        onChange={(event) => setExperimentTitle(event.target.value)}
                        placeholder="Attention baseline reproduction"
                      />
                    </label>
                    <label className="field-label">
                      Dataset
                      <input
                        value={experimentDataset}
                        onChange={(event) => setExperimentDataset(event.target.value)}
                        placeholder="WMT14 en-de"
                      />
                    </label>
                    <label className="field-label">
                      Code reference
                      <input
                        value={experimentCodeRef}
                        onChange={(event) => setExperimentCodeRef(event.target.value)}
                        placeholder="git:abc123 or path/to/commit"
                      />
                    </label>
                    <label className="field-label">
                      Command
                      <textarea
                        value={experimentCommand}
                        onChange={(event) => setExperimentCommand(event.target.value)}
                        placeholder="python train.py --config configs/baseline.yaml"
                      />
                    </label>
                    <label className="field-label">
                      Metrics JSON
                      <textarea
                        value={experimentMetrics}
                        onChange={(event) => setExperimentMetrics(event.target.value)}
                        placeholder='{"bleu": 29.1, "loss": 1.08}'
                      />
                    </label>
                    <label className="field-label">
                      Experiment summary
                      <textarea
                        value={experimentSummary}
                        onChange={(event) => setExperimentSummary(event.target.value)}
                        placeholder="What happened and what should change next?"
                      />
                    </label>
                    <button
                      className="primary wide"
                      type="button"
                      onClick={() => createExperimentRun().catch((err) => setError(String(err.message || err)))}
                    >
                      <Database size={16} /> Save experiment
                    </button>
                    <div className="research-list">
                      <strong>Questions</strong>
                      {researchQuestions.length === 0 ? (
                        <span>No questions yet.</span>
                      ) : (
                        researchQuestions.map((item) => (
                          <article key={item.id} className="research-row">
                            <span>{item.status}</span>
                            <p>{item.question}</p>
                            {item.current_answer ? <small>{item.current_answer}</small> : null}
                          </article>
                        ))
                      )}
                    </div>
                    <div className="research-list">
                      <strong>Experiment runs</strong>
                      {experimentRuns.length === 0 ? (
                        <span>No experiment runs yet.</span>
                      ) : (
                        experimentRuns.map((run) => (
                          <article key={run.id} className="research-row">
                            <div className="research-row-title">
                              <span>{run.status}</span>
                              <button
                                type="button"
                                onClick={() =>
                                  saveExperimentRunToResearch(run).catch((err) =>
                                    setError(String(err.message || err))
                                  )
                                }
                              >
                                Save note
                              </button>
                            </div>
                            <p>{run.title}</p>
                            <small>{run.dataset || "No dataset"} · {run.artifact_count} artifacts</small>
                            {Object.keys(run.metrics || {}).length > 0 ? (
                              <small>
                                {Object.entries(run.metrics)
                                  .map(([key, value]) => `${key}: ${String(value)}`)
                                  .join(", ")}
                              </small>
                            ) : null}
                          </article>
                        ))
                      )}
                    </div>
                    <label className="field-label">
                      Discussion title
                      <input
                        value={discussionTitle}
                        onChange={(event) => setDiscussionTitle(event.target.value)}
                        placeholder="Discuss current evidence"
                      />
                    </label>
                    <button
                      className="quiet-button wide-button"
                      type="button"
                      onClick={() => createResearchDiscussion().catch((err) => setError(String(err.message || err)))}
                    >
                      <MessageSquare size={15} /> Create discussion
                    </button>
                    {researchDiscussions.length > 0 ? (
                      <select
                        value={selectedDiscussionId || ""}
                        onChange={(event) => setSelectedDiscussionId(Number(event.target.value) || null)}
                        aria-label="Research discussion"
                      >
                        {researchDiscussions.map((discussion) => (
                          <option key={discussion.id} value={discussion.id}>
                            {discussion.title} · {discussion.message_count} messages
                          </option>
                        ))}
                      </select>
                    ) : null}
                    {selectedDiscussion ? (
                      <div className="research-list discussion-thread">
                        <strong>Discussion</strong>
                        {selectedDiscussion.messages?.length ? (
                          selectedDiscussion.messages.map((message) => (
                            <article key={message.id} className={`research-row discussion-message ${message.role}`}>
                              <div className="research-row-title">
                                <span>{message.role}</span>
                                <small>{new Date(message.created_at).toLocaleString()}</small>
                              </div>
                              <p>{message.content}</p>
                            </article>
                          ))
                        ) : (
                          <span>No messages yet.</span>
                        )}
                      </div>
                    ) : null}
                    <label className="field-label">
                      Discussion message
                      <textarea
                        value={discussionMessage}
                        onChange={(event) => setDiscussionMessage(event.target.value)}
                        placeholder="Record a project-level research discussion message..."
                      />
                    </label>
                    <div className="research-actions discussion-actions">
                      <button
                        className="quiet-button"
                        type="button"
                        disabled={!selectedDiscussionId || !discussionMessage.trim()}
                        onClick={() =>
                          addResearchDiscussionMessage().catch((err) => setError(String(err.message || err)))
                        }
                      >
                        <Clipboard size={15} /> Save
                      </button>
                      <button
                        className="primary"
                        type="button"
                        disabled={
                          researchCodexBusy ||
                          !selectedDiscussionId ||
                          !discussionMessage.trim() ||
                          !codexStatus?.codex_chat_available
                        }
                        onClick={() =>
                          askResearchDiscussionCodex().catch((err) => setError(String(err.message || err)))
                        }
                      >
                        <Sparkles size={15} /> {researchCodexBusy ? "Asking" : "Ask Codex"}
                      </button>
                    </div>
                    <label className="field-label">
                      Snapshot title
                      <input
                        value={snapshotTitle}
                        onChange={(event) => setSnapshotTitle(event.target.value)}
                        placeholder="Grounding snapshot"
                      />
                    </label>
                    <button
                      className="quiet-button wide-button"
                      type="button"
                      onClick={() => createGroundingSnapshot().catch((err) => setError(String(err.message || err)))}
                    >
                      <Database size={15} /> Save grounding snapshot
                    </button>
                    <div className="research-list">
                      <strong>Grounding snapshots</strong>
                      {groundingSnapshots.length === 0 ? (
                        <span>No grounding snapshots yet.</span>
                      ) : (
                        groundingSnapshots.map((snapshot) => (
                          <article key={snapshot.id} className="research-row">
                            <p>{snapshot.title}</p>
                            <small>
                              {String(snapshot.metadata.note_count || 0)} notes ·{" "}
                              {String(snapshot.metadata.experiment_run_count || 0)} runs
                            </small>
                          </article>
                        ))
                      )}
                    </div>
                    <div className="research-list">
                      <strong>Notes</strong>
                      {researchNotes.length === 0 ? (
                        <span>No notes yet.</span>
                      ) : (
                        researchNotes.map((note) => (
                          <article key={note.id} className="research-row">
                            <div className="research-row-title">
                              <span>{note.note_type}</span>
                              <button
                                type="button"
                                onClick={() =>
                                  archiveResearchNote(note.id).catch((err) => setError(String(err.message || err)))
                                }
                              >
                                Archive
                              </button>
                            </div>
                            <p>{note.title}</p>
                            {note.links.length > 0 ? (
                              <small>
                                {note.links.map((link) => link.label || link.link_type).join(", ")}
                              </small>
                            ) : null}
                          </article>
                        ))
                      )}
                    </div>
                  </>
                ) : null}
                <label className="field-label">
                  Paper tags
                  <input
                    defaultValue={selectedPaper.tags.join(", ")}
                    onBlur={(event) => saveTags(event.target.value)}
                  />
                </label>
                <div className="provider-list compact-providers">
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
