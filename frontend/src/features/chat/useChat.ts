import { useState, useCallback } from 'react'
import { postChat, getChatStreamUrl, type ChatMessage } from '../../api/client'

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [streaming, setStreaming] = useState(false)

  const send = useCallback(
    async (text: string, useStream = false, modeId = 'default') => {
      if (!text.trim() || loading) return

      const userMessage: ChatMessage = { role: 'user', content: text.trim() }
      setMessages((prev) => [...prev, userMessage])
      setLoading(true)
      setStreaming(useStream)
      setError(null)

      try {
        if (useStream) {
          // Note: streaming doesn't support mode_id yet in URL params
          const url = getChatStreamUrl(text.trim(), conversationId ?? undefined)
          const eventSource = new EventSource(url)
          let content = ''
          let thinking = ''
          setMessages((prev) => [...prev, { role: 'assistant', content: '', thinking: '' }])

          const updateMessage = () => {
            setMessages((prev) => {
              const next = [...prev]
              next[next.length - 1] = { role: 'assistant', content, thinking }
              return next
            })
          }

          await new Promise<void>((resolve) => {
            eventSource.addEventListener('content', (e: MessageEvent) => {
              if (e.data) {
                content += e.data
                updateMessage()
              }
            })
            eventSource.addEventListener('thinking', (e: MessageEvent) => {
              if (e.data) {
                thinking += e.data
                updateMessage()
              }
            })
            eventSource.addEventListener('done', () => {
              eventSource.close()
              resolve()
            })
            eventSource.onerror = () => {
              eventSource.close()
              resolve()
            }
          })
        } else {
          const history = messages.map((m) => ({ role: m.role, content: m.content }))
          const response = await postChat({
            message: text.trim(),
            history: history.length > 0 ? history : undefined,
            conversation_id: conversationId ?? undefined,
            mode_id: modeId,
          })
          setMessages((prev) => [
            ...prev,
            { role: 'assistant', content: response.content },
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
    [messages, loading, conversationId]
  )

  const clear = useCallback(() => {
    setMessages([])
    setConversationId(null)
    setError(null)
  }, [])

  return { messages, loading, streaming, error, send, clear, conversationId }
}
