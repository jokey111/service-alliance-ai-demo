import { useEffect, useRef, useState } from 'react';
import {
  ArrowRight, BookOpen, CheckCircle2, CircleHelp, ClipboardCheck,
  ChevronDown, FileText, Headphones, LayoutDashboard, LogOut, Menu, MessageCircle, Plus, Search,
  Send, ShieldCheck, Sparkles, Ticket as TicketIcon, WandSparkles, X,
} from 'lucide-react';

type Role = 'employee' | 'agent' | 'qc' | 'admin';
type View = 'chat' | 'repair' | 'agent' | 'tickets' | 'qc' | 'knowledge';
type ModelId = 'glm-5.3-flash' | 'glm-5.3-flashx' | 'glm-5.3';
type User = { id: string; name: string; role: Role; department: string };
type Reimbursement = { id: string; title: string; amount_yuan: number; status: string };
type ChatResult = { conversation_id: string; trace_id: string; status: string; answer: string;
  evidence?: { status?: string; items?: Reimbursement[]; item?: Reimbursement;
    passages?: { id: string; title: string; text: string }[] }; citations?: { id: string; title: string; version: string }[]; model_used: boolean };
type Message = { role: string; content: string; trace_id?: string; result?: ChatResult };
type Ticket = { id: string; owner_id: string; conversation_id?: string | null; title: string; description: string; category: string;
  status: string; resolution?: string; created_at: string };
type QCReport = { id: string; ticket_id: string; status: string; rule_version: string;
  findings: { dimension: string; result: string; evidence: string; rule: string }[]; review_note?: string };

const profiles: { id: string; name: string; role: Role; label: string; color: string }[] = [
  { id: 'user', name: '张伟', role: 'employee', label: '普通员工', color: 'blue' },
  { id: 'agent', name: '李娜', role: 'agent', label: '客服坐席', color: 'mint' },
  { id: 'qc', name: '周雯', role: 'qc', label: '质检员', color: 'violet' },
  { id: 'admin', name: '陈建国', role: 'admin', label: '管理员', color: 'orange' },
];
const quickTasks = [
  { title: '查询报销进度', description: '查看本人单据的最新节点', prompt: '帮我查一下我的报销进度', icon: Search },
  { title: '了解报销流程', description: '材料、步骤与处理说明', prompt: '报销怎么弄？需要哪些材料？', icon: FileText },
  { title: '提交 IT 报修', description: '填写故障并确认后提交', prompt: '__repair__', icon: CircleHelp },
  { title: '联系人工坐席', description: '带着当前上下文交接', prompt: '__handoff__', icon: Headphones },
];
const defaultModels: ModelId[] = ['glm-5.3-flash', 'glm-5.3-flashx', 'glm-5.3'];

async function api<T>(path: string, token: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}), ...options.headers },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : `请求失败 (${response.status})`);
  return body as T;
}

function App() {
  const [token, setToken] = useState(localStorage.getItem('demo_token') || '');
  const [user, setUser] = useState<User | null>(null);
  const [view, setView] = useState<View>('chat');
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [conversations, setConversations] = useState<{ id: string; title: string }[]>([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [trace, setTrace] = useState<{ id: string; steps: Record<string, unknown>[] } | null>(null);
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [reports, setReports] = useState<QCReport[]>([]);
  const [health, setHealth] = useState<{ model_configured: boolean; model?: string; models?: ModelId[] } | null>(null);
  const [selectedModel, setSelectedModel] = useState<ModelId>('glm-5.3-flash');
  const [serviceMenuOpen, setServiceMenuOpen] = useState(false);

  useEffect(() => {
    api<{ model_configured: boolean; model?: string; models?: ModelId[] }>('/health', '').then(setHealth).catch(() => {});
  }, []);
  useEffect(() => {
    if (!token) return;
    api<User>('/me', token).then(setUser).catch(() => { localStorage.removeItem('demo_token'); setToken(''); });
  }, [token]);
  useEffect(() => {
    if (!token || !user) return;
    api<{ id: string; title: string }[]>('/conversations', token).then(setConversations).catch(() => {});
  }, [token, user, conversationId]);
  useEffect(() => {
    if (!token || !user) return;
    if (view === 'tickets' || view === 'agent') api<Ticket[]>('/tickets', token).then(setTickets).catch(e => setError(e.message));
    if (view === 'qc') api<QCReport[]>('/qc-reports', token).then(setReports).catch(e => setError(e.message));
  }, [view, token, user]);

  async function login(identity: string) {
    setBusy(true); setError('');
    try {
      const result = await api<{ token: string; user: User }>('/auth/demo', '', { method: 'POST', body: JSON.stringify({ identity }) });
      localStorage.setItem('demo_token', result.token);
      setToken(result.token); setUser(result.user); setConversationId(null); setMessages([]);
      setView(result.user.role === 'qc' ? 'qc' : result.user.role === 'agent' ? 'agent' : 'chat');
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  function logout() {
    localStorage.removeItem('demo_token'); setToken(''); setUser(null); setConversationId(null);
    setMessages([]); setTrace(null); setView('chat'); setServiceMenuOpen(false);
  }
  function startNew() { setConversationId(null); setMessages([]); setView('chat'); setError(''); }
  async function openConversation(id: string) {
    try {
      const result = await api<{ messages: Message[] }>(`/conversations/${id}`, token);
      setConversationId(id); setMessages(result.messages); setView('chat'); setError('');
    } catch (e) { setError((e as Error).message); }
  }
  async function send(text = input, reimbursementId?: string) {
    const clean = text.trim(); if (!clean || busy) return;
    setBusy(true); setError(''); setInput('');
    setMessages(previous => [...previous, { role: 'user', content: clean }]);
    try {
      const result = await api<ChatResult>('/chat', token, { method: 'POST', body: JSON.stringify({ text: clean, conversation_id: conversationId, reimbursement_id: reimbursementId, model: selectedModel }) });
      setConversationId(result.conversation_id);
      setMessages(previous => [...previous, { role: 'assistant', content: result.answer, trace_id: result.trace_id, result }]);
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  async function handoff() {
    if (busy) return;
    setBusy(true); setError('');
    try {
      const result = await api<Ticket>('/handoffs', token, { method: 'POST', body: JSON.stringify({ conversation_id: conversationId }) });
      if (result.conversation_id) setConversationId(result.conversation_id);
      setMessages(previous => [...previous, { role: 'system', content: `已创建人工服务工单 ${result.id}，坐席可查看本次会话摘要。` }]);
      setView('tickets'); setTickets(previous => previous.some(item => item.id === result.id) ? previous : [result, ...previous]);
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  async function loadTrace(id: string) {
    try { setTrace(await api<{ id: string; steps: Record<string, unknown>[] }>(`/traces/${id}`, token)); }
    catch (e) { setError((e as Error).message); }
  }
  async function updateTicket(id: string, status: string, resolution?: string) {
    try {
      await api(`/tickets/${id}`, token, { method: 'PATCH', body: JSON.stringify({ status, resolution }) });
      setTickets(await api<Ticket[]>('/tickets', token));
    } catch (e) { setError((e as Error).message); }
  }
  async function reviewReport(id: string, decision: string, note: string) {
    try {
      await api(`/qc-reports/${id}/review`, token, { method: 'POST', body: JSON.stringify({ decision, note }) });
      setReports(await api<QCReport[]>('/qc-reports', token));
    } catch (e) { setError((e as Error).message); }
  }

  if (!user) return <Login onLogin={login} busy={busy} error={error} />;
  const available: { id: View; label: string; icon: typeof MessageCircle }[] = [
    { id: 'chat', label: '智能服务', icon: MessageCircle },
    ...(user.role !== 'qc' ? [{ id: 'repair' as View, label: 'IT 报修', icon: CircleHelp }] : []),
    ...(user.role !== 'employee' ? [{ id: 'agent' as View, label: '坐席工作台', icon: Headphones }] : []),
    { id: 'tickets', label: '工单中心', icon: TicketIcon },
    ...(user.role === 'qc' || user.role === 'admin' ? [{ id: 'qc' as View, label: '质检平台', icon: ClipboardCheck }] : []),
    ...(user.role === 'admin' ? [{ id: 'knowledge' as View, label: '知识与评测', icon: BookOpen }] : []),
  ];
  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand-row"><button className="service-menu-trigger" onClick={() => setServiceMenuOpen(true)} aria-label="打开服务菜单" aria-expanded={serviceMenuOpen} aria-controls="service-menu"><Menu size={21} /></button><div className="brand"><div className="brand-mark"><Sparkles size={19} /></div><div><strong>12345客服联盟</strong><small>智能服务工作台</small></div></div></div>
      <button className="new-task" onClick={startNew}><Plus size={17} /> 新建对话 <span>⌘ K</span></button>
      <div className="side-label recent-label">最近对话</div>
      <div className="recent-list">{conversations.slice(0, 5).map(item => <button key={item.id} onClick={() => openConversation(item.id)}><MessageCircle size={15} /><span>{item.title}</span></button>)}{conversations.length === 0 && <p>暂无历史对话</p>}</div>
      <div className="sidebar-bottom"><div className="synthetic-tag"><ShieldCheck size={15} /> 合成数据演示环境</div><button className="profile" onClick={logout}><span className="avatar">{user.name[0]}</span><span><strong>{user.name}</strong><small>{profiles.find(p => p.role === user.role)?.label}</small></span><LogOut size={16} /></button></div>
    </aside>
    {serviceMenuOpen && <><button className="service-menu-backdrop" onClick={() => setServiceMenuOpen(false)} aria-label="关闭服务菜单" /><nav id="service-menu" className="service-menu-panel" aria-label="服务菜单"><div className="service-menu-heading"><strong>服务</strong><button onClick={() => setServiceMenuOpen(false)} aria-label="关闭服务菜单"><X size={17} /></button></div><div className="service-menu-items">{available.map(item => <button key={item.id} className={view === item.id ? 'active' : ''} onClick={() => { setView(item.id); setError(''); setServiceMenuOpen(false); }}><item.icon size={18} />{item.label}</button>)}</div><div className="service-menu-reserve" /></nav></>}
    <main className="main-area">
      <header className="topbar"><div className="breadcrumb">服务 <span>/</span> {available.find(item => item.id === view)?.label}</div><div className="top-actions"><span className="top-avatar">{user.name[0]}</span></div></header>
      {error && <div className="error-banner">{error}<button onClick={() => setError('')}><X size={15} /></button></div>}
      {view === 'chat' && <ChatPage messages={messages} input={input} setInput={setInput} busy={busy} send={send} handoff={handoff} loadTrace={loadTrace} startRepair={() => setView('repair')} selectedModel={selectedModel} setSelectedModel={setSelectedModel} modelOptions={health?.models ?? defaultModels} modelConfigured={health?.model_configured ?? false} />}
      {view === 'repair' && <RepairPage token={token} loadTrace={loadTrace} />}
      {view === 'agent' && <AgentPage tickets={tickets} user={user} updateTicket={updateTicket} />}
      {view === 'tickets' && <TicketPage tickets={tickets} user={user} updateTicket={updateTicket} />}
      {view === 'qc' && <QCPage reports={reports} review={reviewReport} token={token} loadTrace={loadTrace} />}
      {view === 'knowledge' && <KnowledgePage token={token} loadTrace={loadTrace} />}
    </main>
    {trace && <div className="overlay" onClick={() => setTrace(null)}><div className="trace-panel" onClick={e => e.stopPropagation()}><div className="drawer-head"><div><span className="eyebrow">EXECUTION TRACE</span><h2>本次运行轨迹</h2><p>{trace.id}</p></div><button onClick={() => setTrace(null)}><X size={20} /></button></div><div className="trace-steps">{trace.steps.map((step, index) => <div className="trace-step" key={index}><span>{String(index + 1).padStart(2, '0')}</span><div><strong>{String(step.kind)}</strong><pre>{JSON.stringify(step, null, 2)}</pre></div></div>)}</div></div></div>}
  </div>;
}

function Login({ onLogin, busy, error }: { onLogin: (id: string) => void; busy: boolean; error: string }) {
  return <div className="login-page"><div className="login-inner"><div className="login-brand"><div className="brand-mark"><Sparkles size={22} /></div>12345客服联盟</div><div className="login-copy"><span className="eyebrow">INTERVIEW DEMO · SYNTHETIC DATA</span><h1>让每一次服务<br/><em>都有答案，也有依据。</em></h1><p>从员工自助、坐席协同到质检复盘，体验一条完整的智能服务链路。</p></div><div className="login-panel"><div className="panel-title"><span>选择演示身份</span><span>01 / 04</span></div><div className="role-grid">{profiles.map(profile => <button key={profile.id} onClick={() => onLogin(profile.id)} disabled={busy}><div className={'role-icon ' + profile.color}>{profile.name[0]}</div><span><strong>{profile.label}</strong><small>{profile.name} · 进入工作台</small></span><ArrowRight size={17} /></button>)}</div>{error && <p className="login-error">{error}</p>}<div className="login-note"><ShieldCheck size={16} /> 所有账号和业务记录均为合成演示数据</div></div><div className="login-footer">FDE PORTFOLIO PROJECT <span>© 2026 12345客服联盟</span></div></div></div>;
}

function ChatPage({ messages, input, setInput, busy, send, handoff, loadTrace, startRepair, selectedModel, setSelectedModel, modelOptions, modelConfigured }: {
  messages: Message[]; input: string; setInput: (value: string) => void; busy: boolean;
  send: (text?: string, reimbursementId?: string) => void; handoff: () => void;
  loadTrace: (id: string) => void; startRepair: () => void;
  selectedModel: ModelId; setSelectedModel: (model: ModelId) => void; modelOptions: ModelId[]; modelConfigured: boolean;
}) {
  return <div className={'chat-page ' + (messages.length ? 'has-messages' : '')}>
    {messages.length === 0 ? <div className="hero"><div className="hero-orb"><WandSparkles size={31} /></div><div className="hero-kicker">YOUR SERVICE COPILOT</div><h1>你好，今天需要什么帮助？</h1><p>从制度查询到业务进度，让服务过程更清晰、更省心。</p><div className="hero-cards">{quickTasks.map(task => <button key={task.title} onClick={() => task.prompt === '__repair__' ? startRepair() : task.prompt === '__handoff__' ? handoff() : send(task.prompt)} disabled={busy}><task.icon size={22} /><strong>{task.title}</strong><small>{task.description}</small><ArrowRight size={17} className="card-arrow" /></button>)}</div></div> : <div className="message-scroll"><div className="conversation-title"><span className="eyebrow">SERVICE CONVERSATION</span><h2>智能服务对话</h2><p>业务结果来自合成数据。点击“查看轨迹”可核对实际处理步骤。</p></div>{messages.map((message, index) => <div className={'message-row ' + message.role} key={index}><div className="message-avatar">{message.role === 'user' ? '我' : message.role === 'system' ? 'i' : <Sparkles size={17} />}</div><div className="message-body"><div className="message-author">{message.role === 'user' ? '你' : message.role === 'system' ? '系统通知' : '12345 智能服务'}</div><div className="message-text">{message.content}</div>{message.result?.evidence?.items && message.result.status === 'selection_required' && <div className="result-list">{message.result.evidence.items.map(item => <button key={item.id} onClick={() => send('查询这张报销单的详细进度', item.id)}><span><strong>{item.title}</strong><small>{item.id} · ¥{item.amount_yuan}</small></span><span className="result-status">{item.status}</span><ArrowRight size={16} /></button>)}</div>}{message.result?.citations && message.result.citations.length > 0 && <div className="citations">{message.result.citations.map(item => <span key={item.id}><BookOpen size={13} />{item.title} · {item.version}</span>)}</div>}{message.result?.evidence?.passages && <details className="source-passages"><summary>查看引用原文</summary>{message.result.evidence.passages.map(item => <div key={item.id}><strong>{item.title} · {item.id}</strong><p>{item.text}</p></div>)}</details>}{message.trace_id && <button className="trace-link" onClick={() => loadTrace(message.trace_id!)}><LayoutDashboard size={14} /> 查看运行轨迹 <ArrowRight size={13} /></button>}</div></div>)}{busy && <div className="message-row assistant"><div className="message-avatar"><Sparkles size={17} /></div><div className="message-body"><div className="message-author">12345 智能服务</div><div className="typing"><i/><i/><i/> 正在处理你的请求</div></div></div>}</div>}
    <div className="composer-wrap"><div className="composer"><textarea value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } }} placeholder="描述你的问题，例如：帮我查一下报销进度…" rows={2} /><div className="composer-actions"><ModelPicker selectedModel={selectedModel} setSelectedModel={setSelectedModel} modelOptions={modelOptions} modelConfigured={modelConfigured} busy={busy} /><div><button className="human-btn" onClick={handoff} disabled={busy}><Headphones size={15} /> 转人工</button><button className="send-btn" onClick={() => send()} disabled={busy || !input.trim()}><Send size={17} /></button></div></div></div><p className="composer-hint">演示环境使用合成数据。AI 可能出错，涉及业务办理请核对状态与依据。</p></div>
  </div>;
}

function ModelPicker({ selectedModel, setSelectedModel, modelOptions, modelConfigured, busy }: {
  selectedModel: ModelId; setSelectedModel: (model: ModelId) => void;
  modelOptions: ModelId[]; modelConfigured: boolean; busy: boolean;
}) {
  const [open, setOpen] = useState(false);
  const pickerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function closeOutside(event: PointerEvent) {
      if (!pickerRef.current?.contains(event.target as Node)) setOpen(false);
    }
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') setOpen(false);
    }
    document.addEventListener('pointerdown', closeOutside);
    document.addEventListener('keydown', closeOnEscape);
    return () => {
      document.removeEventListener('pointerdown', closeOutside);
      document.removeEventListener('keydown', closeOnEscape);
    };
  }, [open]);

  return <div className="model-picker" ref={pickerRef}>
    <button className={'model-select ' + (modelConfigured ? 'online' : '')} type="button" aria-label={`选择对话模型，当前 ${selectedModel}`} aria-haspopup="listbox" aria-expanded={open} aria-controls="chat-model-options" onClick={() => setOpen(value => !value)} disabled={busy}>
      <span className="status-dot" /><span className="model-name">{selectedModel}</span><ChevronDown size={14} className={open ? 'expanded' : ''} /><span className="model-state">{modelConfigured ? '已配置' : '未配置'}</span>
    </button>
    {open && <div className="model-menu" id="chat-model-options" role="listbox" aria-label="可选对话模型">
      <div className="model-menu-title">选择对话模型</div>
      {modelOptions.map(model => <button key={model} type="button" role="option" aria-selected={selectedModel === model} className={selectedModel === model ? 'selected' : ''} onClick={() => { setSelectedModel(model); setOpen(false); }}>
        <span>{model}</span>{selectedModel === model && <CheckCircle2 size={15} />}
      </button>)}
      {!modelConfigured && <p>模型 API 尚未配置，当前仅展示可选项。</p>}
    </div>}
  </div>;
}

function Status({ value }: { value: string }) { return <span className={'status-tag ' + value}>{({ pending: '待受理', processing: '处理中', resolved: '已解决', closed: '已关闭', draft: '待复核', confirmed: '已确认', rejected: '已撤销', needs_evidence: '待补证' } as Record<string, string>)[value] || value}</span>; }

function RepairPage({ token, loadTrace }: { token: string; loadTrace: (id: string) => void }) {
  const [device, setDevice] = useState('');
  const [issue, setIssue] = useState('');
  const [location, setLocation] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [result, setResult] = useState<{ status: string; ticket_id?: string; trace_id: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function prepare() {
    setBusy(true); setError('');
    try {
      const body = await api<{ confirmation_token: string }>('/it-repair/prepare', token, {
        method: 'POST', body: JSON.stringify({ device, issue, location }),
      });
      setConfirmation(body.confirmation_token);
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  async function submit() {
    setBusy(true); setError('');
    try {
      const body = await api<{ status: string; ticket_id?: string; trace_id: string }>('/it-repair/confirm', token, {
        method: 'POST', body: JSON.stringify({ confirmation_token: confirmation }),
      });
      setResult(body);
      if (body.status !== 'ok') setError('提交结果尚未确认。可用同一确认信息重试，不会重复创建工单。');
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  return <div className="workspace-page"><div className="page-intro"><span className="eyebrow">EXECUTABLE SKILL · MCP TOOL</span><h1>IT 报修申请</h1><p>填写设备、故障和地点；核对后由独立业务工具创建工单。</p></div>
    <div className="repair-card">{result?.status === 'ok' ? <><CheckCircle2 size={30} /><h2>报修已提交</h2><p>工单号：<strong>{result.ticket_id}</strong></p><button className="trace-link" onClick={() => loadTrace(result.trace_id)}>查看 Skill 与 MCP 调用轨迹 <ArrowRight size={14} /></button></> : <>
      <label>设备名称<input value={device} onChange={e => { setDevice(e.target.value); setConfirmation(''); }} placeholder="例如：办公笔记本" disabled={busy} /></label>
      <label>故障描述<textarea value={issue} onChange={e => { setIssue(e.target.value); setConfirmation(''); }} placeholder="例如：开机后无法连接公司 Wi-Fi" disabled={busy} /></label>
      <label>所在地点<input value={location} onChange={e => { setLocation(e.target.value); setConfirmation(''); }} placeholder="例如：上海办公区 A 座 3 楼" disabled={busy} /></label>
      {!confirmation ? <button className="primary-btn" onClick={prepare} disabled={busy || device.trim().length < 2 || issue.trim().length < 4 || location.trim().length < 2}>预览报修内容 <ArrowRight size={16} /></button> : <div className="repair-preview"><strong>请确认以下信息</strong><p>设备：{device}</p><p>故障：{issue}</p><p>地点：{location}</p><button className="primary-btn" onClick={submit} disabled={busy}>确认提交报修</button></div>}
      {error && <p className="repair-error">{error}</p>}
    </>}</div></div>;
}

function AgentPage({ tickets, user, updateTicket }: { tickets: Ticket[]; user: User; updateTicket: (id: string, status: string, resolution?: string) => void }) {
  const [selected, setSelected] = useState<string | null>(null);
  const [resolution, setResolution] = useState('');
  const current = tickets.find(item => item.id === selected) || tickets[0];
  return <div className="workspace-page"><div className="page-intro"><span className="eyebrow">HUMAN-IN-THE-LOOP</span><h1>坐席工作台</h1><p>接收携带上下文的人工请求，核实信息后推进工单。</p></div><div className="agent-layout"><div className="queue-panel"><div className="section-title">待处理队列 <span>{tickets.filter(item => item.status !== 'closed').length}</span></div>{tickets.map(item => <button className={'queue-item ' + (current?.id === item.id ? 'selected' : '')} key={item.id} onClick={() => setSelected(item.id)}><div><strong>{item.title}</strong><Status value={item.status} /></div><p>{item.description.slice(0, 68)}</p><small>{item.id}</small></button>)}{tickets.length === 0 && <Empty text="目前没有待处理的工单。员工转人工后会出现在这里。" />}</div><div className="detail-panel">{current ? <><div className="detail-header"><span className="eyebrow">CASE DETAIL</span><h2>{current.title}</h2><div><span>{current.id}</span><Status value={current.status} /></div></div><div className="section-title">交接上下文</div><div className="evidence-box">{current.description}</div><div className="section-title">坐席处理</div><p className="muted">AI 提供整理与建议，工单状态和处理承诺由坐席确认。</p>{user.role !== 'qc' && <div className="action-area">{current.status === 'pending' && <button className="primary-btn" onClick={() => updateTicket(current.id, 'processing')}>接单处理 <ArrowRight size={16} /></button>}{current.status === 'processing' && <><textarea value={resolution} onChange={e => setResolution(e.target.value)} placeholder="填写已核实的处理结果" /><button className="primary-btn" onClick={() => updateTicket(current.id, 'resolved', resolution)} disabled={!resolution.trim()}>标记已解决</button></>}{current.status === 'resolved' && <button className="primary-btn" onClick={() => updateTicket(current.id, 'closed')}>关闭工单并触发质检</button>}</div>}</> : <Empty text="请选择一张工单查看详情。" />}</div><div className="assist-panel"><div className="assist-icon"><Sparkles size={21} /></div><h3>AI 辅助区</h3><p>这里将承载会话摘要、知识推荐、回复草稿与工单预填，并记录坐席的采纳方式。</p><div className="assist-placeholder"><CheckCircle2 size={18} /> 当前阶段：交接摘要已接通</div></div></div></div>;
}

function TicketPage({ tickets, user, updateTicket }: { tickets: Ticket[]; user: User; updateTicket: (id: string, status: string, resolution?: string) => void }) {
  const [filter, setFilter] = useState('all');
  const rows = tickets.filter(item => filter === 'all' || item.status === filter);
  return <div className="workspace-page"><div className="page-intro spread"><div><span className="eyebrow">SERVICE OPERATIONS</span><h1>工单中心</h1><p>查看受理、处理与关闭状态，跟踪每一次人工服务。</p></div><div className="metric-mini"><strong>{tickets.length}</strong><span>全部工单</span></div></div><div className="tab-row">{[['all','全部'],['pending','待受理'],['processing','处理中'],['resolved','已解决'],['closed','已关闭']].map(([key,label]) => <button className={filter === key ? 'selected' : ''} key={key} onClick={() => setFilter(key)}>{label}</button>)}</div><div className="table-card"><div className="table-head"><span>工单 / 主题</span><span>业务分类</span><span>状态</span><span>操作</span></div>{rows.map(item => <div className="table-row" key={item.id}><div><strong>{item.title}</strong><small>{item.id} · {new Date(item.created_at).toLocaleDateString('zh-CN')}</small></div><span>{item.category}</span><Status value={item.status} /><div>{user.role !== 'employee' && user.role !== 'qc' && item.status === 'pending' ? <button className="text-btn" onClick={() => updateTicket(item.id, 'processing')}>受理 <ArrowRight size={15} /></button> : <span className="muted">{item.status === 'closed' ? '已归档' : '跟进中'}</span>}</div></div>)}{rows.length === 0 && <Empty text="该状态下暂无工单。" />}</div></div>;
}

function QCPage({ reports, review, token, loadTrace }: { reports: QCReport[]; review: (id: string, decision: string, note: string) => void; token: string; loadTrace: (id: string) => void }) {
  const [active, setActive] = useState<'single' | 'analysis'>('single');
  const [note, setNote] = useState('已核对工单证据与规则版本');
  return <div className="workspace-page"><div className="page-intro"><span className="eyebrow">QUALITY INTELLIGENCE</span><h1>服务质检平台</h1><p>规则检查、证据定位与人工复核共同形成可追溯的结论。</p></div><div className="tab-row"><button className={active === 'single' ? 'selected' : ''} onClick={() => setActive('single')}>单工单质检</button><button className={active === 'analysis' ? 'selected' : ''} onClick={() => setActive('analysis')}>异常分析 Agent</button></div>{active === 'single' ? <div className="qc-grid">{reports.map(report => <div className="qc-card" key={report.id}><div className="qc-top"><span className="eyebrow">{report.id}</span><Status value={report.status} /></div><h3>关联工单 {report.ticket_id}</h3><p className="muted">质检规则版本 {report.rule_version}</p><div className="finding-list">{report.findings.map(item => <div key={item.dimension}><strong>{item.dimension}</strong><span>{item.result}</span><small>依据：{item.evidence}</small></div>)}</div>{report.status === 'draft' && <div className="review-actions"><input value={note} onChange={e => setNote(e.target.value)} aria-label="复核意见" /><button onClick={() => review(report.id, 'confirmed', note)}>确认</button><button onClick={() => review(report.id, 'needs_evidence', note)}>待补证</button></div>}{report.review_note && <p className="review-note">复核意见：{report.review_note}</p>}</div>)}{reports.length === 0 && <div className="wide-empty"><Empty text="暂无质检草稿。坐席关闭工单后将在这里生成待复核报告。" /></div>}</div> : <QCAnalysisPage token={token} loadTrace={loadTrace} />}</div>;
}

function QCAnalysisPage({ token, loadTrace }: { token: string; loadTrace: (id: string) => void }) {
  type Analysis = { trace_id: string; status: string; headline: string; limitation: string; hypothesis?: string;
    metrics?: { ticket_count: number; report_count: number; ticket_status: Record<string, number>; review_status: Record<string, number> };
    evidence?: { ticket_id: string; category: string; status: string; qc_report_id?: string; qc_status?: string }[] };
  const [category, setCategory] = useState('全部');
  const [result, setResult] = useState<Analysis | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function run() {
    setBusy(true); setError('');
    try { setResult(await api<Analysis>('/qc-analysis', token, { method: 'POST', body: JSON.stringify({ category }) })); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  return <div className="analysis-card"><div className="assist-icon"><WandSparkles size={25} /></div><h2>跨工单只读分析</h2><p>先查询统计，再抽取最多五条证据；所有结论均为合成数据的演示口径。</p><div className="analysis-controls"><select value={category} onChange={e => setCategory(e.target.value)}><option>全部</option><option>报销服务</option><option>IT报修</option></select><button className="primary-btn" onClick={run} disabled={busy}>{busy ? '分析中…' : '生成分析草稿'}</button></div>{error && <p className="repair-error">{error}</p>}{result && <div className="analysis-result"><h3>{result.headline}</h3>{result.metrics && <p>待受理 {result.metrics.ticket_status.pending} · 已关闭 {result.metrics.ticket_status.closed} · 待补证 {result.metrics.review_status.needs_evidence}</p>}<h4>抽样证据</h4>{result.evidence?.length ? result.evidence.map(item => <p key={item.ticket_id}>{item.ticket_id} · {item.category} · {item.status} · 质检：{item.qc_status || '无报告'}</p>) : <p>当前范围暂无工单样本。</p>}<h4>分析边界</h4><p>{result.limitation}</p>{result.hypothesis && <p><strong>待验证排查方向：</strong>{result.hypothesis}</p>}<button className="trace-link" onClick={() => loadTrace(result.trace_id)}>查看 MCP 调用轨迹 <ArrowRight size={14} /></button></div>}</div>;
}

function KnowledgePage({ token, loadTrace }: { token: string; loadTrace: (id: string) => void }) {
  type Doc = { id: string; domain: string; title: string; version: string; status: string; active: boolean; body: string };
  type Eval = { trace_id: string; suite: string; passed: number; total: number;
    cases: { id: string; name: string; expected: string; observed: unknown; passed: boolean }[] };
  const [docs, setDocs] = useState<Doc[]>([]);
  const [evalRun, setEvalRun] = useState<Eval | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => { api<Doc[]>('/knowledge-documents', token).then(setDocs).catch(e => setError(e.message)); }, [token]);
  async function evaluate() {
    setBusy(true); setError('');
    try { setEvalRun(await api<Eval>('/evals/run', token, { method: 'POST' })); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  return <div className="workspace-page"><div className="page-intro"><span className="eyebrow">KNOWLEDGE & EVALUATION</span><h1>知识与评测</h1><p>合成知识带业务域、版本和有效期；固定回归集检查路由、过期过滤和数据边界。</p></div>
    {error && <p className="repair-error">{error}</p>}
    <div className="knowledge-section"><div className="section-title">知识文档 <span>{docs.filter(item => item.active).length} 条生效</span></div><div className="doc-grid">{docs.map(item => <div className="doc-card" key={item.id}><div className="doc-card-top"><span>{item.domain}</span><span className={item.active ? 'doc-active' : 'doc-retired'}>{item.active ? '当前有效' : '已停用/过期'}</span></div><h3>{item.title}</h3><p>{item.body}</p><small>{item.id} · {item.version}</small></div>)}</div></div>
    <div className="knowledge-section"><div className="section-title">固定回归评测</div><p className="muted">本集只验证确定性路由、知识过滤和权限数据边界；不把它当作模型回答质量得分。</p><button className="primary-btn" onClick={evaluate} disabled={busy}>{busy ? '运行中…' : '运行 10 条关键案例'}</button>{evalRun && <div className="eval-panel"><div className="eval-summary"><strong>{evalRun.passed} / {evalRun.total}</strong><span>通过 · {evalRun.suite}</span><button className="trace-link" onClick={() => loadTrace(evalRun.trace_id)}>查看评测轨迹 <ArrowRight size={14} /></button></div>{evalRun.cases.map(item => <div className="eval-row" key={item.id}><span className={item.passed ? 'eval-pass' : 'eval-fail'}>{item.passed ? '通过' : '失败'}</span><strong>{item.id} · {item.name}</strong><small>预期：{item.expected}</small><small>实际：{typeof item.observed === 'string' ? item.observed : JSON.stringify(item.observed)}</small></div>)}</div>}</div>
  </div>;
}
function Empty({ text }: { text: string }) { return <div className="empty-state"><div><CircleHelp size={23} /></div><p>{text}</p></div>; }

export default App;
