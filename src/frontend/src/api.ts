export type Workspace = { id: string; name: string; role: "owner" | "editor" | "viewer" };
export type KnowledgeBase = { id: string; workspace_id: string; name: string; description: string; document_count: number };
export type Model = { id: string; provider: string; name: string; capabilities: string[]; enabled: boolean };
export type Document = { id: string; name: string; document_type: string; status: string; source: string; tags: string[] };
export type Task = {
  id: string;
  kind: string;
  workspace_id?: string;
  knowledge_base_id?: string;
  status: "queued" | "running" | "succeeded" | "failed";
  progress: number;
  message: string;
  created_at: string;
  updated_at: string;
};
export type Citation = {
  chunk_id: string;
  document_id: string;
  document_name: string;
  document_type: string;
  locator: string;
  content: string;
  score: number;
};
export type AgentEvent = {
  type: string;
  step?: string;
  status?: string;
  message?: string;
  data?: Record<string, unknown>;
};
export type PastedDocumentInput = {
  name: string;
  content: string;
  document_type: "markdown" | "text" | "python" | "javascript" | "typescript";
  tags: string[];
};

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
let token = localStorage.getItem("devmind_token") || "";

export function setToken(value: string) {
  token = value;
  localStorage.setItem("devmind_token", value);
}

export function clearToken() {
  token = "";
  localStorage.removeItem("devmind_token");
}

export function isLoggedIn() {
  return Boolean(token);
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const response = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail || `请求失败 (${response.status})`);
  }
  return response.json() as Promise<T>;
}

function parseSseBlock(block: string, onEvent: (event: AgentEvent) => void) {
  const payload = block
    .split(/\r?\n/)
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).trimStart())
    .join("\n")
    .trim();
  if (!payload) return;
  try {
    onEvent(JSON.parse(payload) as AgentEvent);
  } catch {
    // 忽略代理或服务端发送的 keep-alive / 不完整片段。
  }
}

export const api = {
  async login(email: string, password: string) {
    const result = await request<{ access_token: string; user: { display_name: string; email: string } }>(
      "/api/auth/login",
      { method: "POST", body: JSON.stringify({ email, password }) },
    );
    setToken(result.access_token);
    return result;
  },
  workspaces: () => request<Workspace[]>("/api/workspaces"),
  knowledgeBases: (workspaceId: string) => request<KnowledgeBase[]>(`/api/workspaces/${workspaceId}/knowledge-bases`),
  documents: (kbId: string) => request<Document[]>(`/api/knowledge-bases/${kbId}/documents`),
  models: () => request<Model[]>("/api/models"),
  upload: (kbId: string, file: File) => {
    const body = new FormData();
    body.append("file", file);
    return request<{ document: Document; task: Task }>(`/api/knowledge-bases/${kbId}/documents`, { method: "POST", body });
  },
  pasteText: (kbId: string, payload: PastedDocumentInput) =>
    request<{ document: Document; task: Task }>(`/api/knowledge-bases/${kbId}/documents/text`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  task: (taskId: string) => request<Task>(`/api/tasks/${taskId}`),
  async staticCheck(code: string, language: string) {
    return request<{
      ok: boolean;
      summary: string;
      findings: { level: string; line?: number; message: string; rule: string }[];
    }>("/api/diagnostics/static-check", { method: "POST", body: JSON.stringify({ code, language }) });
  },
  async streamChat(payload: Record<string, unknown>, onEvent: (event: AgentEvent) => void) {
    // AI TECH STACK: FRONTEND INTERACTION
    const headers = new Headers({ "Content-Type": "application/json", Accept: "text/event-stream" });
    if (token) headers.set("Authorization", `Bearer ${token}`);
    const response = await fetch(`${API_BASE}/api/chat/stream`, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
    });
    if (!response.ok || !response.body) {
      const body = (await response.json().catch(() => ({}))) as { detail?: string };
      throw new Error(body.detail || `流式请求失败 (${response.status})`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });
      const blocks = buffer.split(/\r?\n\r?\n/);
      buffer = blocks.pop() || "";
      blocks.forEach((block) => parseSseBlock(block, onEvent));
      if (done) break;
    }
    if (buffer.trim()) parseSseBlock(buffer, onEvent);
  },
};
