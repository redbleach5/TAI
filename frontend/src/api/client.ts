/** API client for CodeGen AI backend */

export const API_BASE = import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? '/api' : '')

export interface HealthResponse {
  status: string
  service: string
  llm_provider: 'ollama' | 'lm_studio'
  llm_available: boolean
}

/** One proposed file edit from the agent (Cursor-like: apply or reject). */
export interface ProposedEdit {
  path: string
  content: string
  old_content?: string
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  /** Reasoning/thinking from <think> blocks (reasoning models). */
  thinking?: string
  /** Agent tool calls/results (inline in chat) */
  toolEvents?: Array<{ type: 'tool_call' | 'tool_result'; data: string }>
  /** Model that processed this message (watermark) */
  model?: string
  /** Path to analysis report file (docs/ANALYSIS_REPORT.md) — показать кнопку «Открыть отчёт» */
  reportPath?: string
  /** Proposed file edits from agent (apply or reject in UI, Cursor-like) */
  pendingEdits?: ProposedEdit[]
}

export interface ContextFile {
  path: string
  content: string
}

export interface ChatRequest {
  message: string
  history?: ChatMessage[]
  conversation_id?: string
  mode_id?: string
  model?: string  // Override model (Cursor-like)
  context_files?: ContextFile[]  // Open files — model sees them automatically (Cursor-like)
  active_file_path?: string     // Focused tab — "current file" for the model
  /** If true (default), agent write_file is proposed only; user applies or rejects in UI (Cursor-like) */
  apply_edits_required?: boolean
}

export interface ChatResponse {
  content: string
  model: string
  conversation_id?: string
}

// Config (Settings UI)
export interface ConfigResponse {
  llm: { provider: string }
  models: {
    defaults: { simple: string; medium: string; complex: string; fallback: string }
    lm_studio: { simple: string; medium: string; complex: string; fallback: string } | null
  }
  embeddings: { model: string }
  logging: { level: string }
}

export interface ConfigPatch {
  llm?: { provider?: string }
  models?: {
    defaults?: { simple?: string; medium?: string; complex?: string; fallback?: string }
    lm_studio?: { simple?: string; medium?: string; complex?: string; fallback?: string }
  }
  embeddings?: { model?: string }
  logging?: { level?: string }
}

export async function getConfig(): Promise<ConfigResponse> {
  const res = await fetch(`${API_BASE}/config`)
  if (!res.ok) throw new Error(`Config failed: ${res.status}`)
  return res.json()
}

export async function patchConfig(updates: ConfigPatch): Promise<{ ok: boolean; message: string }> {
  const res = await fetch(`${API_BASE}/config`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updates),
  })
  if (!res.ok) throw new Error(`Config update failed: ${res.status}`)
  return res.json()
}

export async function getModels(provider?: 'ollama' | 'lm_studio'): Promise<string[]> {
  const url = provider ? `${API_BASE}/models?provider=${provider}` : `${API_BASE}/models`
  const res = await fetch(url)
  if (!res.ok) throw new Error(`Models failed: ${res.status}`)
  return res.json()
}

export async function getHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE}/health`)
  if (!res.ok) throw new Error(`Health check failed: ${res.status}`)
  return res.json()
}

export async function postChat(request: ChatRequest): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })
  if (!res.ok) throw new Error(`Chat failed: ${res.status}`)
  return res.json()
}

export function getChatStreamUrl(message: string, conversationId?: string): string {
  const params = new URLSearchParams({ message })
  if (conversationId) params.set('conversation_id', conversationId)
  return `${API_BASE}/chat/stream?${params}`
}

/** POST stream - supports context_files (open files from IDE, Cursor-like) */
export async function postChatStream(request: ChatRequest): Promise<Response> {
  return fetch(`${API_BASE}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })
}

/** Write file in workspace (used when user applies a proposed edit from the agent). */
export async function writeFile(path: string, content: string): Promise<{ success: boolean; error?: string }> {
  const res = await fetch(`${API_BASE}/files/write`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path, content }),
  })
  const data = await res.json().catch(() => ({}))
  if (res.ok && data.success) return { success: true }
  return { success: false, error: data.error || data.detail || 'Write failed' }
}

// Conversations (list / load / delete — Cursor-like)
export interface ConversationListItem {
  id: string
  title: string
}

export async function getConversations(): Promise<ConversationListItem[]> {
  const res = await fetch(`${API_BASE}/conversations`)
  if (!res.ok) throw new Error(`Conversations list failed: ${res.status}`)
  const list = await res.json()
  return Array.isArray(list)
    ? list.map((x: { id?: string; title?: string }) => ({
        id: x.id ?? '',
        title: (x.title && String(x.title).trim()) ? String(x.title).trim() : 'Без названия',
      }))
    : []
}

export async function getConversation(conversationId: string): Promise<Array<{ role: string; content: string }>> {
  const res = await fetch(`${API_BASE}/conversations/${encodeURIComponent(conversationId)}`)
  if (!res.ok) throw new Error(`Conversation load failed: ${res.status}`)
  return res.json()
}

export async function deleteConversation(conversationId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/conversations/${encodeURIComponent(conversationId)}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`Conversation delete failed: ${res.status}`)
}

// Workflow
export interface WorkflowRequest {
  task: string
  session_id?: string
}

export interface WorkflowResponse {
  session_id: string
  content: string
  intent_kind: string
  plan?: string | null
  tests?: string | null
  code?: string | null
  validation_passed?: boolean | null
  validation_output?: string | null
  error?: string | null
}

export interface WorkflowStreamEvent {
  event_type: string
  chunk?: string | null
  payload?: Record<string, unknown> | null
}

export async function postWorkflow(request: WorkflowRequest): Promise<WorkflowResponse> {
  const res = await fetch(`${API_BASE}/workflow`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })
  if (!res.ok) throw new Error(`Workflow failed: ${res.status}`)
  return res.json()
}

// Improvement API
export interface ImprovementRequest {
  file_path: string
  issue?: { message?: string; severity?: string; issue_type?: string }
  auto_write?: boolean
  max_retries?: number
  related_files?: string[]
}

export interface ImprovementResponse {
  success: boolean
  file_path: string
  backup_path?: string | null
  validation_output?: string | null
  error?: string | null
  retries: number
}

export async function postImprove(request: ImprovementRequest): Promise<ImprovementResponse> {
  const res = await fetch(`${API_BASE}/improve/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })
  if (!res.ok) throw new Error(await res.text().catch(() => `Improve failed: ${res.status}`))
  return res.json()
}

export async function* streamWorkflow(
  request: WorkflowRequest
): AsyncGenerator<WorkflowStreamEvent> {
  const res = await fetch(`${API_BASE}/workflow?stream=true`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })
  if (!res.ok) throw new Error(`Workflow stream failed: ${res.status}`)
  const reader = res.body?.getReader()
  if (!reader) throw new Error('No response body')
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const blocks = buffer.split('\n\n')
    buffer = blocks.pop() ?? ''
    for (const block of blocks) {
      let data = ''
      for (const line of block.split('\n')) {
        if (line.startsWith('data: ')) data = line.slice(6)
      }
      if (data) {
        try {
          yield JSON.parse(data) as WorkflowStreamEvent
        } catch {
          // skip malformed
        }
      }
    }
  }
}
