import { useEffect, useMemo, useState } from "react";
import {
  api,
  clearToken,
  isLoggedIn,
  type AgentEvent,
  type Citation,
  type Document,
  type KnowledgeBase,
  type Model,
  type PastedDocumentInput,
  type Task,
  type Workspace,
} from "./api";
import "./styles.css";

const demoQuestion = "FastAPI 返回 422，如何定位是 Pydantic 参数校验还是前端请求格式问题？";

function errorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

function Login({ onLoggedIn }: { onLoggedIn: () => void }) {
  const [email, setEmail] = useState("demo@devmind.local");
  const [password, setPassword] = useState("devmind-demo");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      await api.login(email, password);
      onLoggedIn();
    } catch (requestError) {
      setError(errorMessage(requestError, "登录失败"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="login-shell">
      <section className="login-card">
        <div className="brand-mark">DM</div>
        <span className="eyebrow">AI APPLICATION ENGINEERING PORTFOLIO</span>
        <h1>
          DevMind <span>Agent</span>
        </h1>
        <p className="muted">研发知识库诊断工作台 · RAG + Agent + 工具执行</p>
        <form onSubmit={submit} className="login-form">
          <label>
            邮箱
            <input value={email} onChange={(event) => setEmail(event.target.value)} />
          </label>
          <label>
            密码
            <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
          </label>
          {error && <div className="error-banner">{error}</div>}
          <button className="primary full" disabled={loading}>
            {loading ? "正在登录…" : "进入工作台"}
          </button>
        </form>
        <div className="demo-hint">
          <strong>Demo 账号</strong>
          <span>demo@devmind.local</span>
          <span>devmind-demo</span>
        </div>
      </section>
      <section className="login-visual">
        <div className="orb orb-a" />
        <div className="orb orb-b" />
        <div className="visual-copy">
          <span className="eyebrow">FROM QUESTION TO EVIDENCE</span>
          <h2>
            让每一次技术诊断，
            <br />
            都可追溯、可执行。
          </h2>
          <div className="mini-flow">
            <i>01</i><span>检索授权知识库</span>
            <i>02</i><span>执行安全诊断工具</span>
            <i>03</i><span>生成带引用的诊断报告</span>
          </div>
        </div>
      </section>
    </main>
  );
}

function StatusPill({ status }: { status: string }) {
  const labels: Record<string, string> = {
    ready: "已完成",
    succeeded: "已完成",
    running: "处理中",
    queued: "排队中",
    failed: "失败",
  };
  return <span className={`status-pill ${status}`}>{labels[status] || status}</span>;
}

function App() {
  const [loggedIn, setLoggedIn] = useState(isLoggedIn());
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [kb, setKb] = useState<KnowledgeBase | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [models, setModels] = useState<Model[]>([]);
  const [modelId, setModelId] = useState("mock-chat");
  const [embeddingId, setEmbeddingId] = useState("local-embedding");
  const [question, setQuestion] = useState("");
  const [code, setCode] = useState("");
  const [language, setLanguage] = useState("python");
  const [documentType, setDocumentType] = useState("");
  const [tags, setTags] = useState("");
  const [requestPatch, setRequestPatch] = useState(false);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [answer, setAnswer] = useState("");
  const [citations, setCitations] = useState<Citation[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [task, setTask] = useState<Task | null>(null);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState<"diagnose" | "documents">("diagnose");
  const [pasteName, setPasteName] = useState("troubleshooting-note.md");
  const [pasteType, setPasteType] = useState<PastedDocumentInput["document_type"]>("markdown");
  const [pasteContent, setPasteContent] = useState("");
  const [pasteTags, setPasteTags] = useState("");

  useEffect(() => {
    if (!loggedIn) return;
    Promise.all([api.workspaces(), api.models()])
      .then(([workspaceItems, modelItems]) => {
        setWorkspaces(workspaceItems);
        setWorkspace(workspaceItems[0] || null);
        setModels(modelItems);
        const chatModel = modelItems.find((model) => model.capabilities.includes("chat"));
        const embeddingModel = modelItems.find((model) => model.capabilities.includes("embedding"));
        if (chatModel) setModelId(chatModel.id);
        if (embeddingModel) setEmbeddingId(embeddingModel.id);
      })
      .catch((requestError) => setError(errorMessage(requestError, "初始化失败")));
  }, [loggedIn]);

  useEffect(() => {
    if (!workspace) return;
    api.knowledgeBases(workspace.id)
      .then((items) => {
        setKnowledgeBases(items);
        setKb((current) => items.find((item) => item.id === current?.id) || items[0] || null);
      })
      .catch((requestError) => setError(errorMessage(requestError, "知识库加载失败")));
  }, [workspace]);

  useEffect(() => {
    if (!kb) {
      setDocuments([]);
      return;
    }
    api.documents(kb.id)
      .then(setDocuments)
      .catch((requestError) => setError(errorMessage(requestError, "文档加载失败")));
  }, [kb]);

  useEffect(() => {
    if (!task || task.status === "succeeded" || task.status === "failed") return;
    const timer = window.setInterval(() => {
      api.task(task.id)
        .then((nextTask) => {
          setTask(nextTask);
          if (nextTask.status === "succeeded" && kb) {
            api.documents(kb.id).then(setDocuments).catch(() => undefined);
          }
        })
        .catch(() => undefined);
    }, 800);
    return () => window.clearInterval(timer);
  }, [task, kb]);

  const chatModels = useMemo(
    () => models.filter((model) => model.enabled && model.capabilities.includes("chat")),
    [models],
  );
  const embeddingModels = useMemo(
    () => models.filter((model) => model.enabled && model.capabilities.includes("embedding")),
    [models],
  );

  function logout() {
    clearToken();
    setLoggedIn(false);
  }

  async function upload(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file || !kb) return;
    setUploading(true);
    setError("");
    try {
      const result = await api.upload(kb.id, file);
      setTask(result.task);
      setDocuments((current) => [result.document, ...current]);
    } catch (requestError) {
      setError(errorMessage(requestError, "上传失败"));
    } finally {
      setUploading(false);
      event.target.value = "";
    }
  }

  async function pasteDocument(event: React.FormEvent) {
    event.preventDefault();
    if (!kb || !pasteContent.trim()) return;
    setUploading(true);
    setError("");
    try {
      const result = await api.pasteText(kb.id, {
        name: pasteName,
        document_type: pasteType,
        content: pasteContent,
        tags: pasteTags.split(",").map((tag) => tag.trim()).filter(Boolean),
      });
      setTask(result.task);
      setDocuments((current) => [result.document, ...current]);
      setPasteContent("");
      setPasteTags("");
    } catch (requestError) {
      setError(errorMessage(requestError, "文本导入失败"));
    } finally {
      setUploading(false);
    }
  }

  async function diagnose(event: React.FormEvent) {
    event.preventDefault();
    if (!question.trim() || !workspace || !kb) return;
    setLoading(true);
    setError("");
    setAnswer("");
    setCitations([]);
    setEvents([]);
    try {
      await api.streamChat(
        {
          workspace_id: workspace.id,
          knowledge_base_id: kb.id,
          question,
          model_id: modelId,
          embedding_model_id: embeddingId,
          code,
          language,
          require_patch: requestPatch,
          filters: {
            document_types: documentType ? [documentType] : [],
            tags: tags.split(",").map((tag) => tag.trim()).filter(Boolean),
          },
        },
        (nextEvent) => {
          setEvents((current) => [...current, nextEvent]);
          if (nextEvent.type === "answer_delta") {
            setAnswer((current) => current + String(nextEvent.data?.delta || ""));
          }
          if (nextEvent.type === "answer" && nextEvent.message) {
            setAnswer(nextEvent.message);
          }
          if (nextEvent.type === "retrieval" || nextEvent.type === "citation") {
            setCitations((nextEvent.data?.citations as Citation[]) || []);
          }
          if (nextEvent.type === "done" && typeof nextEvent.data?.answer === "string") {
            setAnswer(nextEvent.data.answer);
          }
        },
      );
    } catch (requestError) {
      setError(errorMessage(requestError, "诊断失败"));
    } finally {
      setLoading(false);
    }
  }

  if (!loggedIn) return <Login onLoggedIn={() => setLoggedIn(true)} />;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="side-brand">
          <div className="brand-mark small">DM</div>
          <div><strong>DevMind</strong><small>Agent workspace</small></div>
        </div>
        <div className="side-section">
          <span className="section-label">工作区</span>
          <select
            value={workspace?.id || ""}
            onChange={(event) => setWorkspace(workspaces.find((item) => item.id === event.target.value) || null)}
          >
            {workspaces.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
        </div>
        <div className="side-section grow">
          <div className="section-heading">
            <span className="section-label">知识库</span>
            <span className="count-badge">{knowledgeBases.length}</span>
          </div>
          {knowledgeBases.map((item) => (
            <button
              key={item.id}
              className={`kb-item ${kb?.id === item.id ? "active" : ""}`}
              onClick={() => setKb(item)}
            >
              <span className="kb-dot" />
              <span><strong>{item.name}</strong><small>{item.document_count} 个文档</small></span>
            </button>
          ))}
        </div>
        <div className="side-footer">
          <div className="user-chip">
            <span className="avatar">D</span>
            <span><strong>Demo Developer</strong><small>Owner · 在线</small></span>
          </div>
          <button className="ghost subtle" onClick={logout}>退出登录</button>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div>
            <span className="eyebrow">研发智能工作台 / {workspace?.name || "未选择"}</span>
            <h2>{activeTab === "diagnose" ? "技术问题诊断" : "知识库文档"}</h2>
          </div>
          <div className="top-actions">
            <span className="connection"><i /> 后端服务已连接</span>
            <button
              className="ghost"
              onClick={() => setActiveTab(activeTab === "diagnose" ? "documents" : "diagnose")}
            >
              {activeTab === "diagnose" ? "管理文档" : "返回诊断"}
            </button>
          </div>
        </header>
        {error && <div className="error-banner page-error"><span>{error}</span><button onClick={() => setError("")}>关闭</button></div>}

        {activeTab === "diagnose" ? (
          <DiagnosticWorkspace
            question={question}
            code={code}
            language={language}
            documentType={documentType}
            tags={tags}
            requestPatch={requestPatch}
            loading={loading}
            modelId={modelId}
            embeddingId={embeddingId}
            chatModels={chatModels}
            embeddingModels={embeddingModels}
            answer={answer}
            citations={citations}
            events={events}
            task={task}
            onQuestion={setQuestion}
            onCode={setCode}
            onLanguage={setLanguage}
            onDocumentType={setDocumentType}
            onTags={setTags}
            onRequestPatch={setRequestPatch}
            onModel={setModelId}
            onEmbedding={setEmbeddingId}
            onUseDemo={() => setQuestion(demoQuestion)}
            onSubmit={diagnose}
          />
        ) : (
          <DocumentPanel
            documents={documents}
            uploading={uploading}
            onUpload={upload}
            task={task}
            pasteName={pasteName}
            pasteType={pasteType}
            pasteContent={pasteContent}
            pasteTags={pasteTags}
            onPasteName={setPasteName}
            onPasteType={setPasteType}
            onPasteContent={setPasteContent}
            onPasteTags={setPasteTags}
            onPaste={pasteDocument}
          />
        )}
      </main>
    </div>
  );
}

type DiagnosticWorkspaceProps = {
  question: string;
  code: string;
  language: string;
  documentType: string;
  tags: string;
  requestPatch: boolean;
  loading: boolean;
  modelId: string;
  embeddingId: string;
  chatModels: Model[];
  embeddingModels: Model[];
  answer: string;
  citations: Citation[];
  events: AgentEvent[];
  task: Task | null;
  onQuestion: (value: string) => void;
  onCode: (value: string) => void;
  onLanguage: (value: string) => void;
  onDocumentType: (value: string) => void;
  onTags: (value: string) => void;
  onRequestPatch: (value: boolean) => void;
  onModel: (value: string) => void;
  onEmbedding: (value: string) => void;
  onUseDemo: () => void;
  onSubmit: (event: React.FormEvent) => void;
};

function DiagnosticWorkspace(props: DiagnosticWorkspaceProps) {
  return (
    <section className="workspace-grid">
      <div className="diagnose-column">
        <div className="panel hero-panel">
          <div className="panel-top">
            <div>
              <span className="eyebrow accent">EVIDENCE-GROUNDED AGENT</span>
              <h1>从报错到<em>可验证结论</em></h1>
              <p className="hero-desc">
                Agent 会先执行权限过滤与 RAG 混合检索，再按需运行静态检查和安全沙箱，最后用所选 LLM 生成带引用的诊断报告。
              </p>
              <div className="capability-row">
                <span>向量 + 关键词 + RRF</span><span>权限隔离</span><span>证据不足拒答</span><span>人工确认门</span>
              </div>
            </div>
            <div className="loop-icon"><span>PLAN</span><span>TOOL</span><span>ANSWER</span></div>
          </div>
        </div>

        <form className="panel composer" onSubmit={props.onSubmit}>
          <div className="composer-head">
            <span className="panel-title">描述问题</span>
            <button type="button" className="ghost" onClick={props.onUseDemo}>填入演示问题</button>
          </div>
          <textarea
            value={props.question}
            onChange={(event) => props.onQuestion(event.target.value)}
            placeholder="粘贴报错、日志或描述期望行为……"
          />
          <div className="code-tools">
            <select value={props.language} onChange={(event) => props.onLanguage(event.target.value)}>
              <option value="python">Python</option>
              <option value="javascript">JavaScript</option>
              <option value="typescript">TypeScript</option>
            </select>
            <label className="toggle">
              <input
                type="checkbox"
                checked={props.requestPatch}
                onChange={(event) => props.onRequestPatch(event.target.checked)}
              />
              <span className="toggle-ui" />
              请求 Patch 计划（需人工确认）
            </label>
          </div>
          <textarea
            className="code-input"
            value={props.code}
            onChange={(event) => props.onCode(event.target.value)}
            placeholder="可选：粘贴 Python / JavaScript / TypeScript 代码，Agent 将调用静态检查和安全沙箱。"
            spellCheck={false}
          />
          <div className="filter-row">
            <label>
              文档类型筛选
              <select value={props.documentType} onChange={(event) => props.onDocumentType(event.target.value)}>
                <option value="">全部类型</option>
                <option value="markdown">Markdown</option>
                <option value="pdf">PDF</option>
                <option value="word">Word</option>
                <option value="text">TXT</option>
                <option value="python">Python</option>
                <option value="javascript">JavaScript</option>
                <option value="typescript">TypeScript</option>
              </select>
            </label>
            <label>
              标签筛选
              <input value={props.tags} onChange={(event) => props.onTags(event.target.value)} placeholder="backend, fastapi" />
            </label>
          </div>
          <div className="composer-bottom">
            <div className="model-selects">
              <label>
                对话模型
                <select value={props.modelId} onChange={(event) => props.onModel(event.target.value)}>
                  {props.chatModels.map((model) => <option key={model.id} value={model.id}>{model.name}</option>)}
                </select>
              </label>
              <label>
                Embedding
                <select value={props.embeddingId} onChange={(event) => props.onEmbedding(event.target.value)}>
                  {props.embeddingModels.map((model) => <option key={model.id} value={model.id}>{model.name}</option>)}
                </select>
              </label>
            </div>
            <button className="primary send" disabled={props.loading || !props.question.trim()}>
              {props.loading ? "Agent 执行中…" : "开始诊断"}
            </button>
          </div>
        </form>

        <ResultPanel loading={props.loading} answer={props.answer} citations={props.citations} events={props.events} />
      </div>

      <aside className="right-column">
        <TaskCard task={props.task} />
        <Timeline events={props.events} loading={props.loading} />
        <TechStackPanel />
      </aside>
    </section>
  );
}

function TaskCard({ task }: { task: Task | null }) {
  return (
    <div className="panel task-panel">
      <div className="panel-title-row">
        <span className="panel-title">后台任务状态</span>
        <span className="task-id">{task ? `#${task.id.slice(0, 8)}` : "IDLE"}</span>
      </div>
      {task ? (
        <>
          <div className="task-message"><StatusPill status={task.status} /><span>{task.message}</span></div>
          <div className="progress"><i style={{ width: `${task.progress}%` }} /></div>
          <div className="task-meta"><span>{task.kind === "document_index" ? "文档索引" : task.kind}</span><strong>{task.progress}%</strong></div>
        </>
      ) : (
        <div className="task-empty"><span className="task-icon">◌</span><span>上传文档后，解析与 Embedding 任务会显示在这里</span></div>
      )}
    </div>
  );
}

function Timeline({ events, loading }: { events: AgentEvent[]; loading: boolean }) {
  return (
    <div className="panel timeline-panel">
      <div className="panel-title-row">
        <span className="panel-title">Agent 执行过程</span>
        {(loading || events.length > 0) && <span className="live-dot">LIVE</span>}
      </div>
      {events.length ? (
        <div className="timeline">
          {events.map((event, index) => (
            <div className={`timeline-item ${event.status || "running"}`} key={`${event.type}-${index}`}>
              <span className="timeline-marker">{index + 1}</span>
              <div><strong>{event.step || event.type}</strong><p>{event.message || "正在处理…"}</p></div>
            </div>
          ))}
        </div>
      ) : (
        <div className="empty-timeline">提交问题后，这里会实时展示计划、检索、工具、生成与确认事件。</div>
      )}
    </div>
  );
}

function TechStackPanel() {
  const items = [
    ["LLM 调用", "OpenAI-compatible / Ollama / Mock"],
    ["RAG 检索", "Embedding + 关键词 + RRF + 引用"],
    ["前端交互", "React + TypeScript + SSE"],
    ["服务编排", "FastAPI + Agent 状态机 + 后台任务"],
  ];
  return (
    <div className="panel stack-panel">
      <div className="panel-title">AI 应用技术栈</div>
      {items.map(([title, detail]) => (
        <div className="stack-item" key={title}>
          <span className="check">✓</span>
          <div><strong>{title}</strong><small>{detail}</small></div>
        </div>
      ))}
    </div>
  );
}

function DocumentPanel({
  documents,
  uploading,
  onUpload,
  task,
  pasteName,
  pasteType,
  pasteContent,
  pasteTags,
  onPasteName,
  onPasteType,
  onPasteContent,
  onPasteTags,
  onPaste,
}: {
  documents: Document[];
  uploading: boolean;
  onUpload: (event: React.ChangeEvent<HTMLInputElement>) => void;
  task: Task | null;
  pasteName: string;
  pasteType: PastedDocumentInput["document_type"];
  pasteContent: string;
  pasteTags: string;
  onPasteName: (value: string) => void;
  onPasteType: (value: PastedDocumentInput["document_type"]) => void;
  onPasteContent: (value: string) => void;
  onPasteTags: (value: string) => void;
  onPaste: (event: React.FormEvent) => void;
}) {
  return (
    <section className="document-page">
      <div className="panel upload-panel">
        <div>
          <span className="eyebrow accent">KNOWLEDGE INGESTION</span>
          <h1>构建你的<em>研发知识库</em></h1>
          <p>上传技术文档、代码文件或 ZIP 项目包。后端会安全解析、分块并生成向量索引，任务进度可实时查看。</p>
        </div>
        <label className="upload-drop">
          <input type="file" accept=".pdf,.docx,.md,.txt,.py,.js,.ts,.tsx,.jsx,.zip" onChange={onUpload} />
          <span className="upload-symbol">+</span>
          <strong>{uploading ? "正在提交…" : "选择文件上传"}</strong>
          <small>PDF · Word · Markdown · TXT · Code · ZIP · 最大 20MB</small>
        </label>
      </div>

      <form className="panel paste-panel" onSubmit={onPaste}>
        <div className="panel-title-row"><span className="panel-title">粘贴文本 / 代码</span><span className="hint">直接创建文档并进入索引任务</span></div>
        <div className="paste-fields">
          <label>名称<input value={pasteName} onChange={(event) => onPasteName(event.target.value)} /></label>
          <label>
            类型
            <select value={pasteType} onChange={(event) => onPasteType(event.target.value as PastedDocumentInput["document_type"])}>
              <option value="markdown">Markdown</option>
              <option value="text">TXT</option>
              <option value="python">Python</option>
              <option value="javascript">JavaScript</option>
              <option value="typescript">TypeScript</option>
            </select>
          </label>
          <label>????????<input value={pasteTags} onChange={(event) => onPasteTags(event.target.value)} placeholder="backend, fastapi" /></label>
        </div>
        <textarea
          className="paste-input"
          value={pasteContent}
          onChange={(event) => onPasteContent(event.target.value)}
          rows={7}
          spellCheck={false}
          placeholder="粘贴技术说明、报错记录或代码……"
        />
        <button className="primary" type="submit" disabled={uploading || !pasteContent.trim()}>
          {uploading ? "正在创建…" : "创建并索引"}
        </button>
      </form>

      <div className="panel table-panel">
        <div className="panel-title-row"><span className="panel-title">知识库文档</span><span className="count-badge">{documents.length}</span></div>
        <div className="document-list">
          {documents.map((document) => (
            <div className="document-row" key={document.id}>
              <span className="file-icon">{documentBadge(document.document_type)}</span>
              <div className="doc-info"><strong>{document.name}</strong><small>{document.source} · {document.document_type}</small></div>
              <StatusPill status={document.status} />
            </div>
          ))}
        </div>
        {!documents.length && <div className="empty-state">暂无文档，请上传文件或粘贴内容创建知识库。</div>}
      </div>
      <TaskCard task={task} />
    </section>
  );
}

function documentBadge(documentType: string) {
  const badges: Record<string, string> = {
    markdown: "MD",
    pdf: "PDF",
    word: "DOC",
    archive: "ZIP",
    python: "PY",
    javascript: "JS",
    typescript: "TS",
  };
  return badges[documentType] || "TXT";
}

function ResultPanel({
  loading,
  answer,
  citations,
  events,
}: {
  loading: boolean;
  answer: string;
  citations: Citation[];
  events: AgentEvent[];
}) {
  const approval = events.find((event) => event.type === "approval_required");
  return (
    <div className="panel result-panel">
      <div className="panel-title-row">
        <span className="panel-title">诊断报告</span>
        {answer && <span className="result-label">EVIDENCE-GROUNDED</span>}
      </div>
      {loading && !answer && <div className="loading-answer"><span className="spinner" />Agent 正在汇总证据和工具结果…</div>}
      {!loading && !answer && (
        <div className="empty-state report-empty"><span>✦</span><p>诊断结果将在这里生成</p><small>建议先使用演示问题体验完整链路</small></div>
      )}
      {answer && <div className="answer-text">{answer}</div>}
      {approval && (
        <div className="approval-card">
          <span className="warning-icon">!</span>
          <div>
            <strong>高风险操作需要人工确认</strong>
            <p>{approval.message} 当前 MVP 只展示确认门与 Patch 预览，不会修改宿主机文件。</p>
          </div>
          <button className="ghost" type="button" title="Patch apply 属于 P1" disabled>等待确认接口</button>
        </div>
      )}
      {citations.length > 0 && (
        <div className="citation-section">
          <div className="citation-heading"><span>引用来源</span><small>{citations.length} 条授权证据</small></div>
          <div className="citation-grid">
            {citations.map((citation, index) => (
              <details className="citation" key={citation.chunk_id}>
                <summary>
                  <span className="citation-index">{String(index + 1).padStart(2, "0")}</span>
                  <span><strong>{citation.document_name}</strong><small>{citation.locator} · score {citation.score}</small></span>
                  <span>⌄</span>
                </summary>
                <p>{citation.content}</p>
              </details>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
