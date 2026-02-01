import { useState, useCallback, useEffect, useRef } from 'react'
import {
  postChat,
  postChatStream,
  writeFile,
  getConversations,
  getConversation,
  deleteConversation as apiDeleteConversation,
  type ChatMessage,
  type ProposedEdit,
} from '../../api/client'

const CHAT_STORAGE_KEY = 'tai-chat'
const CHAT_TITLES_KEY = 'tai-chat-titles'
const TITLE_MAX_LEN = 48

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
          messages: messages.map((m) => ({
            role: m.role,
            content: m.content,
            thinking: m.thinking,
            toolEvents: m.toolEvents,
            model: m.model,
            reportPath: m.reportPath,
            pendingEdits: m.pendingEdits,
          })),
          conversationId,
        })
      )
  } catch {
    // ignore
  }
}

function loadTitles(): Record<string, string> {
  try {
    const raw = localStorage.getItem(CHAT_TITLES_KEY)
    if (!raw) return {}
    const data = JSON.parse(raw)
    return typeof data === 'object' && data !== null ? data : {}
  } catch {
    return {}
  }
}

function saveTitle(conversationId: string, title: string) {
  const titles = loadTitles()
  if (title.trim()) {
    titles[conversationId] = title.trim().slice(0, TITLE_MAX_LEN)
    try {
      localStorage.setItem(CHAT_TITLES_KEY, JSON.stringify(titles))
    } catch {
      // ignore
    }
  }
}

function removeTitle(conversationId: string) {
  const titles = loadTitles()
  delete titles[conversationId]
  try {
    localStorage.setItem(CHAT_TITLES_KEY, JSON.stringify(titles))
  } catch {
    // ignore
  }
}

function firstUserMessageTitle(messages: ChatMessage[]): string {
  const first = messages.find((m) => m.role === 'user')
  if (!first?.content?.trim()) return 'Новый чат'
  return first.content.trim().replace(/\s+/g, ' ').slice(0, TITLE_MAX_LEN)
}

export const ANALYZE_PATTERNS = [
  'проанализируй', 'проанализировать', 'анализ проекта', 'анализируй проект',
  'analyze project', 'analyze the project', 'проанализируйте',
]

/** Question-like phrases: do not trigger full analyze, send to chat instead (Cursor-like). */
const QUESTION_LIKE = /\?|может ли|можно ли|как (это|сделать|работает|устроен)|какой|что такое/i

export function isAnalyzeIntent(text: string): boolean {
  const lower = text.trim().toLowerCase()
  if (QUESTION_LIKE.test(lower)) return false
  return ANALYZE_PATTERNS.some((p) => lower.includes(p))
}

export interface UseChatOptions {
  /** Get open files to include as context (Cursor-like — model sees them automatically) */
  getContextFiles?: () => Array<{ path: string; content: string }>
  /** Get path of the focused tab — "current file" for the model */
  getActiveFilePath?: () => string | undefined
  /** Callback when agent executes a tool (mode=agent) */
  onToolCall?: (toolAndArgs: string) => void
  /** Callback when agent receives tool result */
  onToolResult?: (result: string) => void
  /** Callback to trigger analysis (when user says "проанализируй проект"). skipUserMessage=true when useChat already added the message. */
  onAnalyzeRequest?: (skipUserMessage?: boolean) => Promise<void>
}

export interface ConversationItem {
  id: string
  title: string
}

export function useChat(options: UseChatOptions = {}) {
  const { getContextFiles, getActiveFilePath, onToolCall, onToolResult, onAnalyzeRequest } = options
  const [messages, setMessages] = useState<ChatMessage[]>(() => loadFromStorage().messages)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [conversationId, setConversationId] = useState<string | null>(() => loadFromStorage().conversationId)
  const [streaming, setStreaming] = useState(false)
  const [conversations, setConversations] = useState<ConversationItem[]>([])

  // Ref so sync postChat always uses latest messages for history (avoids stale closure).
  // Backend contract: history = previous turns only; current message is sent as `message` and appended server-side.
  const messagesRef = useRef<ChatMessage[]>(messages)
  messagesRef.current = messages

  useEffect(() => {
    saveToStorage(messages, conversationId)
  }, [messages, conversationId])

  const refreshConversations = useCallback(async () => {
    try {
      const list = await getConversations()
      setConversations(list.map((c) => ({ id: c.id, title: c.title || 'Без названия' })))
    } catch {
      setConversations([])
    }
  }, [])

  const startNewConversation = useCallback(() => {
    if (conversationId && messages.length > 0) {
      saveTitle(conversationId, firstUserMessageTitle(messages))
    }
    setMessages([])
    setConversationId(null)
    setError(null)
    saveToStorage([], null)
    refreshConversations()
  }, [conversationId, messages.length, refreshConversations])

  const switchConversation = useCallback(
    async (id: string) => {
      if (id === conversationId) return
      try {
        const list = await getConversation(id)
        const msgs: ChatMessage[] = list.map((m) => ({ role: m.role as 'user' | 'assistant', content: m.content }))
        const title = list.find((m) => m.role === 'user')?.content?.trim()
        if (title) saveTitle(id, title.slice(0, TITLE_MAX_LEN))
        setMessages(msgs)
        setConversationId(id)
        setError(null)
        saveToStorage(msgs, id)
      } catch {
        setError('Не удалось загрузить чат')
      }
    },
    [conversationId]
  )

  const deleteConversation = useCallback(
    async (id: string) => {
      try {
        await apiDeleteConversation(id)
        removeTitle(id)
        await refreshConversations()
        if (conversationId === id) {
          startNewConversation()
        }
      } catch {
        setError('Не удалось удалить чат')
      }
    },
    [conversationId, refreshConversations, startNewConversation]
  )

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
        active_file_path: getActiveFilePath?.() ?? undefined,
        apply_edits_required: modeId === 'agent',
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
          const pendingEdits: ProposedEdit[] = []
          let modelName = ''
          setMessages((prev) => [...prev, { role: 'assistant', content: '', thinking: '', toolEvents: [], pendingEdits: [] }])

          const updateMessage = () => {
            setMessages((prev) => {
              const next = [...prev]
              next[next.length - 1] = {
                role: 'assistant',
                content,
                thinking,
                toolEvents: [...toolEvents],
                pendingEdits: [...pendingEdits],
                model: modelName || undefined,
              }
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
              } else if (eventType === 'proposed_edit' && data) {
                try {
                  const edit = JSON.parse(data) as ProposedEdit
                  if (edit?.path != null && edit?.content != null) {
                    pendingEdits.push({
                      path: edit.path,
                      content: edit.content,
                      old_content: edit.old_content,
                    })
                    updateMessage()
                  }
                } catch {
                  // skip malformed
                }
              } else if (eventType === 'done') {
                if (data) {
                  try {
                    const parsed = JSON.parse(data)
                    if (parsed.conversation_id) {
                      setConversationId(parsed.conversation_id)
                      saveTitle(parsed.conversation_id, firstUserMessageTitle(messagesRef.current))
                    }
                    if (parsed.model != null && parsed.model !== '') modelName = String(parsed.model)
                  } catch {
                    setConversationId(data)
                  }
                }
                updateMessage()
                break
              }
            }
          }
          // Final update so watermark (model) is applied after stream ends
          updateMessage()
        } else {
          // Use ref so history is the latest at call time (avoids stale closure after async setState).
          // API contract: history = previous turns only; current message is in req.message, backend appends it.
          const previousMessages = messagesRef.current
          const historyForRequest = previousMessages.map((m) => ({ role: m.role, content: m.content }))
          const response = await postChat({
            ...req,
            history: historyForRequest.length > 0 ? historyForRequest : undefined,
          })
          setMessages((prev) => [
            ...prev,
            { role: 'assistant', content: response.content, model: response.model },
          ])
          if (response.conversation_id) {
            setConversationId(response.conversation_id)
            saveTitle(response.conversation_id, firstUserMessageTitle(messagesRef.current))
          }
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Unknown error')
      } finally {
        setLoading(false)
        setStreaming(false)
      }
    },
    [messages, loading, conversationId, getContextFiles, getActiveFilePath, onToolCall, onToolResult, onAnalyzeRequest]
  )

  /** New chat: save current title and clear (Cursor-like). Use this instead of clear. */
  const clear = useCallback(() => {
    startNewConversation()
  }, [startNewConversation])

  /** Add message (for Analyze, Generate results) */
  const addMessage = useCallback((role: 'user' | 'assistant', content: string, reportPath?: string) => {
    setMessages((prev) => [...prev, { role, content, ...(reportPath ? { reportPath } : {}) }])
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

  /** Apply a proposed edit from the agent (Cursor-like). Writes file and removes from pendingEdits. */
  const applyEdit = useCallback(async (messageIndex: number, path: string, content: string) => {
    const result = await writeFile(path, content)
    if (!result.success) return result
    setMessages((prev) => {
      const next = [...prev]
      const msg = next[messageIndex]
      if (!msg?.pendingEdits?.length) return prev
      next[messageIndex] = {
        ...msg,
        pendingEdits: msg.pendingEdits.filter((e) => e.path !== path),
      }
      return next
    })
    return result
  }, [])

  /** Reject a proposed edit (remove from list, Cursor-like). */
  const rejectEdit = useCallback((messageIndex: number, path: string) => {
    setMessages((prev) => {
      const next = [...prev]
      const msg = next[messageIndex]
      if (!msg?.pendingEdits?.length) return prev
      next[messageIndex] = {
        ...msg,
        pendingEdits: msg.pendingEdits.filter((e) => e.path !== path),
      }
      return next
    })
  }, [])

  const currentTitle =
    conversationId && messages.length > 0
      ? (loadTitles()[conversationId] || firstUserMessageTitle(messages))
      : 'Новый чат'

  return {
    messages,
    loading,
    streaming,
    error,
    send,
    clear,
    addMessage,
    updateLastAssistant,
    applyEdit,
    rejectEdit,
    conversationId,
    conversations,
    refreshConversations,
    startNewConversation,
    switchConversation,
    deleteConversation,
    currentTitle,
  }
}
