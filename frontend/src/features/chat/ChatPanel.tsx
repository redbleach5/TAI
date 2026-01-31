/**
 * Chat panel — Cursor-like: modes, Analyze, Generate inline.
 */
import { useRef, useEffect, useState, useCallback } from 'react'
import { Plus, Globe, Code, Search, Wand2, Workflow, Loader2, Bot } from 'lucide-react'
import { useChat, isAnalyzeIntent } from './useChat'
import { ChatMessage } from './ChatMessage'
import { ChatInput } from './ChatInput'
import { useAssistant } from '../assistant/useAssistant'
import { ModeSelector } from '../assistant/ModeSelector'
import { ModelSelector } from './ModelSelector'
import { TemplateSelector } from '../assistant/TemplateSelector'
import { useWorkspace } from '../workspace/useWorkspace'
import { useOpenFilesContext } from '../editor/OpenFilesContext'
import { useToast } from '../toast/ToastContext'

interface ChatPanelProps {
  hasEditorContext?: boolean
}

export function ChatPanel({ hasEditorContext }: ChatPanelProps) {
  const openFilesCtx = useOpenFilesContext()
  const getContextFiles = (hasEditorContext && openFilesCtx) ? openFilesCtx.getContextFiles : () => []
  const { show: showToast } = useToast()
  const { workspace } = useWorkspace()
  const { modes, templates, categories, currentMode, setCurrentMode, getTemplate } = useAssistant()
  const [analyzing, setAnalyzing] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [generateTask, setGenerateTask] = useState('')

  const handleAnalyzeRef = useRef<(skipUserMessage?: boolean) => Promise<void>>()
  const { messages, loading, streaming, error, send, clear, addMessage, updateLastAssistant } = useChat({
    getContextFiles,
    onToolCall: (toolAndArgs) => showToast(`Агент: ${toolAndArgs}`, 'info'),
    onAnalyzeRequest: (skipUserMessage?: boolean) => handleAnalyzeRef.current?.(skipUserMessage),
  })

  const handleAnalyze = useCallback(async (skipUserMessage?: boolean) => {
    if (analyzing) return
    if (!workspace) {
      addMessage('assistant', 'Откройте рабочую папку для анализа проекта.')
      showToast('Сначала откройте папку', 'error')
      return
    }
    setAnalyzing(true)
    if (!skipUserMessage) addMessage('user', 'Проанализировать проект')
    try {
      const res = await fetch('/api/analyze/project/deep', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: workspace.path }),
      })
      if (!res.ok) throw new Error(await res.text().catch(() => `${res.status}`))
      const report = await res.text()
      addMessage('assistant', report)
      showToast('Анализ завершён', 'success')
    } catch (e) {
      addMessage('assistant', `Ошибка анализа: ${e instanceof Error ? e.message : 'Unknown'}`)
      showToast('Ошибка анализа', 'error')
    } finally {
      setAnalyzing(false)
    }
  }, [workspace, analyzing, addMessage, showToast])
  handleAnalyzeRef.current = handleAnalyze
  const [useStream, setUseStream] = useState(true)
  const [model, setModel] = useState('')
  const [searchWeb, setSearchWeb] = useState(false)
  const [showTemplates, setShowTemplates] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages])

  const handleSend = (text: string, stream?: boolean, modeId?: string, modelId?: string) => {
    const m = (modelId ?? model) || undefined
    send(text, stream ?? useStream, modeId ?? currentMode, m)
  }

  const handleTemplateSelect = async (template: { id: string; name: string }) => {
    const full = await getTemplate(template.id)
    if (full?.content) send(full.content, useStream, currentMode, model || undefined)
    setShowTemplates(false)
  }

  const handleGenerate = async () => {
    const task = generateTask.trim() || 'Напиши функцию hello world на Python'
    if (generating) return
    setGenerating(true)
    setGenerateTask('')
    addMessage('user', `Сгенерировать: ${task}`)
    try {
      const res = await fetch('/api/workflow?stream=true', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task }),
      })
      if (!res.ok || !res.body) throw new Error('Workflow failed')
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let content = ''
      let buffer = ''
      addMessage('assistant', '')
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
          if (data) {
            try {
              const evt = JSON.parse(data)
              const chunk = evt.chunk ?? ''
              if (chunk && ['plan', 'tests', 'code'].includes(evt.event_type ?? eventType)) {
                content += chunk
                updateLastAssistant(content)
              }
              if (evt.payload?.code) {
                content = [evt.payload.plan, evt.payload.tests, evt.payload.code].filter(Boolean).join('\n\n')
                updateLastAssistant(content)
              }
            } catch {
              // skip
            }
          }
        }
      }
      if (!content) updateLastAssistant('(Пустой ответ)')
      showToast('Код сгенерирован', 'success')
    } catch (e) {
      addMessage('assistant', `Ошибка: ${e instanceof Error ? e.message : 'Unknown'}`)
      showToast('Ошибка генерации', 'error')
    } finally {
      setGenerating(false)
    }
  }

  const busy = loading || analyzing || generating

  return (
    <div className="chat-panel">
      <div className="chat-panel__header">
        <span className="chat-panel__title">
          Помощник
          {hasEditorContext && openFilesCtx && openFilesCtx.files.size > 0 && (
            <span className="chat-panel__context-hint" title="AI видит открытые файлы">
              {openFilesCtx.files.size}
            </span>
          )}
        </span>
        {messages.length > 0 && (
          <button type="button" className="chat-panel__new-btn" onClick={clear} title="Новый разговор">
            <Plus size={14} />
            <span>Новый</span>
          </button>
        )}
      </div>

      {/* Quick actions — Cursor-like, refined */}
      {workspace && (
        <div className="chat-panel__actions">
          <div className="chat-panel__actions-row">
            <button
              type="button"
              className="chat-panel__action"
              onClick={handleAnalyze}
              disabled={busy}
              title="Анализ кода"
            >
              {analyzing ? <Loader2 size={14} className="icon-spin" /> : <Wand2 size={14} />}
              <span>Анализ</span>
            </button>
            <div className="chat-panel__generate">
              <input
                type="text"
                className="chat-panel__generate-input"
                placeholder="Чем помочь?"
                value={generateTask}
                onChange={(e) => setGenerateTask(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    if (isAnalyzeIntent(generateTask)) {
                      addMessage('user', generateTask.trim())
                      handleAnalyze(true)
                      setGenerateTask('')
                    } else {
                      handleGenerate()
                    }
                  }
                }}
                disabled={busy}
              />
              <button
                type="button"
                className="chat-panel__action chat-panel__action--primary"
                onClick={() => {
                  if (isAnalyzeIntent(generateTask)) {
                    addMessage('user', generateTask.trim())
                    handleAnalyze(true)
                    setGenerateTask('')
                  } else {
                    handleGenerate()
                  }
                }}
                disabled={busy}
                title="Сгенерировать код"
              >
                {generating ? <Loader2 size={14} className="icon-spin" /> : <Workflow size={14} />}
                <span>Generate</span>
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="chat-panel__messages" ref={scrollRef}>
        {messages.length === 0 && (
          <div className="chat-panel__empty">
            <p className="chat-panel__empty-title">Чем помочь?</p>
            <div className="chat-panel__empty-commands">
              <span className="chat-panel__empty-command"><Globe size={14} /><code>@web</code> поиск</span>
              <span className="chat-panel__empty-command"><Code size={14} /><code>@code</code> файл</span>
              <span className="chat-panel__empty-command"><Search size={14} /><code>@rag</code> код</span>
            </div>
          </div>
        )}
        {messages.map((msg, i) => (
          <ChatMessage key={i} message={msg} />
        ))}
        {loading && !streaming && (
          <div className="chat-message chat-message--assistant">
            <div className="chat-message__avatar">
              <Bot size={12} />
            </div>
            <div className="chat-message__body">
              <span className="chat-message__role">AI</span>
              <div className="chat-message__content chat-message__content--loading">
                <span className="chat-loading-dots"><span></span><span></span><span></span></span>
              </div>
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
        disabled={busy}
        useStream={useStream}
        onUseStreamChange={setUseStream}
        modeId={currentMode}
        modelId={model}
        searchWeb={searchWeb}
        onSearchWebChange={setSearchWeb}
        onInsertTemplate={() => setShowTemplates(true)}
        modeSelector={<ModeSelector modes={modes} currentMode={currentMode} onSelect={setCurrentMode} compact />}
        modelSelector={<ModelSelector value={model} onChange={setModel} />}
      />
    </div>
  )
}
