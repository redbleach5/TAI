import { useState, useCallback, useEffect } from 'react'
import { postChat, postChatStream, type ChatMessage } from '../../api/client'

const CHAT_STORAGE_KEY = 'tai-chat'

function loadFromStorage(): { messages: ChatMessage[]; conversationId: string | null } {
  try {
    const raw = localStorage.getItem(CHAT_STORAGE_KEY)
    if (!raw) return { messages: [], conversationId: null }
    const data = JSON.parse(raw)
    return {
      messages: Array.isArray(data.messages) ? data.messages : [],
      conversationId: typeof data.conversationId === 'string' ? data.conversationId : null,
    }
  } catch {
    return { messages: [], conversationId: null }
  }
}

function saveToStorage(messages: ChatMessage[], conversationId: string | null) {
  try {
    localStorage.setItem(
      CHAT_STORAGE_KEY,
      JSON.stringify({
        messages: messages.map((m) => ({ role: m.role, content: m.content, thinking: m.thinking, toolEvents: m.toolEvents, model: m.model })),
        conversationId,
      })
    )
  } catch {
    // ignore
  }
}

export const ANALYZE_PATTERNS = [
  'проанализируй', 'проанализировать', 'анализ проекта', 'анализируй проект',
  'analyze project', 'analyze the project', 'проанализируйте',
]

export function isAnalyzeIntent(text: string): boolean {
  const lower = text.trim().toLowerCase()
  return ANALYZE_PATTERNS.some((p) => lower.includes(p))
}

export interface UseChatOptions {
  /** Get open files to include as context (Cursor-like) */
  getContextFiles?: () => Array<{ path: string; content: string }>
  /** Callback when agent executes a tool (mode=agent) */
  onToolCall?: (toolAndArgs: string) => void
  /** Callback when agent receives tool result */
  onToolResult?: (result: string) => void
  /** Callback to trigger analysis (when user says "проанализируй проект"). skipUserMessage=true when useChat already added the message. */
  onAnalyzeRequest?: (skipUserMessage?: boolean) => Promise<void>
}

export function useChat(options: UseChatOptions = {}) {
  const { getContextFiles, onToolCall, onToolResult, onAnalyzeRequest } = options
  const [messages, setMessages] = useState<ChatMessage[]>(() => loadFromStorage().messages)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [conversationId, setConversationId] = useState<string | null>(() => loadFromStorage().conversationId)
  const [streaming, setStreaming] = useState(false)

  useEffect(() => {
    saveToStorage(messages, conversationId)
  }, [messages, conversationId])

  const send = useCallback(
    async (text: string, useStream = false, modeId = 'default', model?: string) => {
      if (!text.trim() || loading) return

      // "Проанализируй проект" → запуск анализа
      if (isAnalyzeIntent(text) && onAnalyzeRequest) {
        const userMessage: ChatMessage = { role: 'user', content: text.trim() }
        setMessages((prev) => [...prev, userMessage])
        setLoading(true)
        try {
          await onAnalyzeRequest(true)
        } finally {
          setLoading(false)
        }
        return
      }

      const contextFiles = getContextFiles?.() ?? []
      const userMessage: ChatMessage = { role: 'user', content: text.trim() }
      setMessages((prev) => [...prev, userMessage])
      setLoading(true)
      setStreaming(useStream)
      setError(null)

      const req = {
        message: text.trim(),
        conversation_id: conversationId ?? undefined,
        mode_id: modeId,
        model: model || undefined,
        context_files: contextFiles.length ? contextFiles : undefined,
      }

      try {
        if (useStream) {
          const response = await postChatStream(req)
          if (!response.ok) throw new Error(`Stream failed: ${response.status}`)
          if (!response.body) throw new Error('No stream')
          const reader = response.body.getReader()
          const decoder = new TextDecoder()
          let content = ''
          let thinking = ''
          const toolEvents: Array<{ type: 'tool_call' | 'tool_result'; data: string }> = []
          let modelName = ''
          setMessages((prev) => [...prev, { role: 'assistant', content: '', thinking: '', toolEvents: [] }])

          const updateMessage = () => {
            setMessages((prev) => {
              const next = [...prev]
              next[next.length - 1] = { role: 'assistant', content, thinking, toolEvents: [...toolEvents], model: modelName || undefined }
              return next
            })
          }

          let buffer = ''
          while (true) {
            const { done, value } = await reader.read()
            if (done) break
            buffer += decoder.decode(value, { stream: true })
            const blocks = buffer.split(/\r?\n\r?\n/)
            buffer = blocks.pop() ?? ''
            for (const block of blocks) {
              let eventType = ''
              let data = ''
              for (const line of block.split(/\r?\n/)) {
                if (line.startsWith('event: ')) eventType = line.slice(7).trim()
                if (line.startsWith('data: ')) data = line.slice(6).trim()
              }
              if (eventType === 'content' && data) content += data
              else if (eventType === 'thinking' && data) thinking += data
              else if (eventType === 'tool_call' && data) {
                toolEvents.push({ type: 'tool_call', data })
                onToolCall?.(data)
              } else if (eventType === 'tool_result' && data) {
                toolEvents.push({ type: 'tool_result', data })
                onToolResult?.(data)
              }               else if (eventType === 'done' && data) {
                try {
                  const parsed = JSON.parse(data)
                  if (parsed.conversation_id) setConversationId(parsed.conversation_id)
                  if (parsed.model) modelName = parsed.model
                } catch {
                  setConversationId(data)
                }
              }
              updateMessage()
              if (eventType === 'done') break
            }
          }
        } else {
          const history = messages.map((m) => ({ role: m.role, content: m.content }))
          const response = await postChat({
            ...req,
            history: history.length > 0 ? history : undefined,
          })
          setMessages((prev) => [
            ...prev,
            { role: 'assistant', content: response.content, model: response.model },
          ])
          if (response.conversation_id) {
            setConversationId(response.conversation_id)
          }
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Unknown error')
      } finally {
        setLoading(false)
        setStreaming(false)
      }
    },
    [messages, loading, conversationId, getContextFiles, onToolCall, onToolResult, onAnalyzeRequest]
  )

  const clear = useCallback(() => {
    setMessages([])
    setConversationId(null)
    setError(null)
    saveToStorage([], null)
  }, [])

  /** Add message (for Analyze, Generate results) */
  const addMessage = useCallback((role: 'user' | 'assistant', content: string) => {
    setMessages((prev) => [...prev, { role, content }])
  }, [])

  /** Update last assistant message (for streaming Generate) */
  const updateLastAssistant = useCallback((content: string) => {
    setMessages((prev) => {
      const next = [...prev]
      const lastIdx = next.length - 1
      if (lastIdx >= 0 && next[lastIdx].role === 'assistant') {
        next[lastIdx] = { ...next[lastIdx], content }
      } else {
        next.push({ role: 'assistant', content })
      }
      return next
    })
  }, [])

  return { messages, loading, streaming, error, send, clear, addMessage, updateLastAssistant, conversationId }
}
