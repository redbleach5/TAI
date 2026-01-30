/** API client for CodeGen AI backend */

const API_BASE = import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? '/api' : '')

export interface HealthResponse {
  status: string
  service: string
  llm_provider: 'ollama' | 'lm_studio'
  llm_available: boolean
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  /** Reasoning/thinking from <think> blocks (reasoning models). */
  thinking?: string
}

export interface ChatRequest {
  message: string
  history?: ChatMessage[]
  conversation_id?: string
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

export async function getModels(): Promise<string[]> {
  const res = await fetch(`${API_BASE}/models`)
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
