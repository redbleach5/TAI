import { useRef, useEffect, useState } from 'react'
import { useChat } from './useChat'
import { ChatMessage } from './ChatMessage'
import { ChatInput } from './ChatInput'
import { useAssistant } from '../assistant/useAssistant'
import { ModeSelector } from '../assistant/ModeSelector'
import { TemplateSelector } from '../assistant/TemplateSelector'

export function ChatPanel() {
  const { messages, loading, streaming, error, send, clear } = useChat()
  const { modes, templates, categories, currentMode, setCurrentMode, getTemplate } = useAssistant()
  const [useStream, setUseStream] = useState(true)
  const [showTemplates, setShowTemplates] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages])

  const handleSend = (text: string, stream?: boolean, modeId?: string) => {
    send(text, stream, modeId || currentMode)
  }

  const handleTemplateSelect = async (template: { id: string; name: string }) => {
    const full = await getTemplate(template.id)
    if (full?.content) {
      // Send template as message (user can edit it in chat)
      send(full.content, useStream, currentMode)
    }
    setShowTemplates(false)
  }

  return (
    <div className="chat-panel">
      <div className="chat-panel__header">
        <span className="chat-panel__title">Chat</span>
        <div className="chat-panel__header-actions">
          {messages.length > 0 && (
            <button
              type="button"
              className="chat-panel__new-btn"
              onClick={clear}
              title="New chat"
            >
              + New
            </button>
          )}
        </div>
      </div>

      <ModeSelector 
        modes={modes} 
        currentMode={currentMode} 
        onSelect={setCurrentMode} 
      />

      <div className="chat-panel__messages" ref={scrollRef}>
        {messages.length === 0 && (
          <div className="chat-panel__empty">
            <p className="chat-panel__empty-title">Start a conversation</p>
            <p className="chat-panel__empty-hint">
              Try: @web search, @code file.py, or ask a question
            </p>
            <div className="chat-panel__empty-commands">
              <code>@web</code> web search
              <code>@code</code> include file
              <code>@rag</code> search codebase
            </div>
          </div>
        )}
        {messages.map((msg, i) => (
          <ChatMessage key={i} message={msg} />
        ))}
        {loading && !streaming && (
          <div className="chat-message chat-message--assistant">
            <span className="chat-message__role">AI</span>
            <div className="chat-message__content chat-message__content--loading">
              <span className="chat-loading-dots">
                <span></span><span></span><span></span>
              </span>
            </div>
          </div>
        )}
      </div>

      {error && <p className="chat-panel__error">{error}</p>}

      {showTemplates && (
        <TemplateSelector
          templates={templates}
          categories={categories}
          onSelect={handleTemplateSelect}
          onClose={() => setShowTemplates(false)}
        />
      )}

      <ChatInput
        onSend={handleSend}
        disabled={loading}
        useStream={useStream}
        onUseStreamChange={setUseStream}
        modeId={currentMode}
        onInsertTemplate={() => setShowTemplates(true)}
      />
    </div>
  )
}
