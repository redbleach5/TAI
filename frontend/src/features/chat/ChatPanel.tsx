/**
 * Chat panel — Cursor-like: modes, Analyze, Improve, Generate inline.
 */
import { useRef, useEffect, useState, useCallback } from 'react'
import { Plus, Globe, Code, Search, Wand2, Workflow, Loader2, Bot, Sparkles, MessageSquare, ChevronDown, Trash2, PanelRightClose } from 'lucide-react'
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
import { Tooltip } from '../ui/Tooltip'
import { postImprove } from '../../api/client'

interface ChatPanelProps {
  hasEditorContext?: boolean
  /** Свернуть панель чата — освободить место для редактора */
  onCollapse?: () => void
}

export function ChatPanel({ hasEditorContext, onCollapse }: ChatPanelProps) {
  const openFilesCtx = useOpenFilesContext()
  const getContextFiles = (hasEditorContext && openFilesCtx) ? openFilesCtx.getContextFiles : () => []
  const { show: showToast } = useToast()
  const { workspace } = useWorkspace()
  const { modes, templates, categories, currentMode, setCurrentMode, getTemplate } = useAssistant()
  const [analyzing, setAnalyzing] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [generateTask, setGenerateTask] = useState('')
  const [improving, setImproving] = useState(false)
  const [showImproveForm, setShowImproveForm] = useState(false)
  const [improveIssue, setImproveIssue] = useState('')
  const [improveRelatedFiles, setImproveRelatedFiles] = useState('')

  const handleAnalyzeRef = useRef<((skipUserMessage?: boolean) => Promise<void>) | null>(null)
  const {
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
  } = useChat({
    getContextFiles,
    getActiveFilePath: () => openFilesCtx?.getActiveFile()?.path,
    onToolCall: (toolAndArgs) => showToast(`Агент: ${toolAndArgs}`, 'info'),
    onAnalyzeRequest: (skipUserMessage?: boolean) => {
      const fn = handleAnalyzeRef.current
      if (fn) return fn(skipUserMessage ?? false)
      return Promise.resolve()
    },
  })
  const [showConversations, setShowConversations] = useState(false)
  const conversationsRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!showConversations) return
    refreshConversations()
  }, [showConversations, refreshConversations])

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (conversationsRef.current && !conversationsRef.current.contains(e.target as Node)) {
        setShowConversations(false)
      }
    }
    if (showConversations) {
      document.addEventListener('click', handleClickOutside)
      return () => document.removeEventListener('click', handleClickOutside)
    }
  }, [showConversations])

  useEffect(() => {
    function handleEscape(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        setShowConversations(false)
        setShowTemplates(false)
      }
    }
    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [])

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
      const data = await res.json()
      const { summary, report_path: reportPath } = data
      addMessage('assistant', summary, reportPath)
      showToast('Анализ завершён. Отчёт в проекте.', 'success')
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

  const handleImprove = useCallback(async () => {
    const activeFile = openFilesCtx?.getActiveFile?.()
    if (!activeFile?.path) {
      showToast('Откройте файл для улучшения', 'error')
      return
    }
    if (improving) return
    setImproving(true)
    const issueMsg = improveIssue.trim() || 'Общее улучшение кода'
    addMessage('user', `Улучшить ${activeFile.path}: ${issueMsg}`)
    try {
      const related = improveRelatedFiles
        .split(/[,\s]+/)
        .map((s) => s.trim())
        .filter(Boolean)
        .filter((p) => p !== activeFile.path)
      const result = await postImprove({
        file_path: activeFile.path,
        issue: { message: issueMsg, severity: 'medium', issue_type: 'refactor' },
        related_files: related,
      })
      if (result.success) {
        addMessage('assistant', `Готово. Файл обновлён: ${result.file_path}${result.backup_path ? ` (бэкап: ${result.backup_path})` : ''}`)
        showToast('Улучшение применено', 'success')
        setShowImproveForm(false)
        setImproveIssue('')
        setImproveRelatedFiles('')
        window.dispatchEvent(new CustomEvent('file-updated', { detail: { path: result.file_path } }))
      } else {
        addMessage('assistant', `Ошибка: ${result.error || 'Не удалось применить изменения'}`)
        showToast(result.error || 'Ошибка улучшения', 'error')
      }
    } catch (e) {
      addMessage('assistant', `Ошибка: ${e instanceof Error ? e.message : 'Unknown'}`)
      showToast('Ошибка улучшения', 'error')
    } finally {
      setImproving(false)
    }
  }, [openFilesCtx, improving, improveIssue, improveRelatedFiles, addMessage, showToast])

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

  const busy = loading || analyzing || generating || improving

  return (
    <div className="chat-panel">
      <div className="chat-panel__header">
        <div className="chat-panel__conversations" ref={conversationsRef}>
          <Tooltip text="Чаты: переключение и новый чат" side="bottom">
            <button
              type="button"
              className="chat-panel__conversations-trigger"
              onClick={() => setShowConversations((v) => !v)}
              aria-label="Чаты"
            >
              <MessageSquare size={14} />
              <span className="chat-panel__conversations-title">{currentTitle}</span>
              <ChevronDown size={12} className={showConversations ? 'chat-panel__chevron--open' : ''} />
            </button>
          </Tooltip>
          {showConversations && (
            <div className="chat-panel__conversations-dropdown">
              <Tooltip text="Начать новый разговор" side="right">
                <button
                  type="button"
                  className="chat-panel__conversations-item chat-panel__conversations-item--new"
                  onClick={() => {
                    startNewConversation()
                    setShowConversations(false)
                  }}
                  aria-label="Новый чат"
                >
                  <Plus size={14} />
                  <span>Новый чат</span>
                </button>
              </Tooltip>
              {conversations.length === 0 && (
                <div className="chat-panel__conversations-empty">Нет сохранённых чатов</div>
              )}
              {conversations.map((c) => (
                <div
                  key={c.id}
                  className={`chat-panel__conversations-row ${c.id === conversationId ? 'chat-panel__conversations-item--active' : ''}`}
                >
                  <button
                    type="button"
                    className="chat-panel__conversations-item"
                    onClick={() => {
                      switchConversation(c.id)
                      setShowConversations(false)
                    }}
                    title={c.title}
                  >
                    <MessageSquare size={12} />
                    <span>{c.title}</span>
                  </button>
                  <button
                    type="button"
                    className="chat-panel__conversations-delete"
                    onClick={(e) => {
                      e.stopPropagation()
                      if (window.confirm(`Удалить чат «${c.title}»?`)) {
                        deleteConversation(c.id)
                        setShowConversations(false)
                      }
                    }}
                    title="Удалить чат"
                  >
                    <Trash2 size={12} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
        <div className="chat-panel__header-actions">
          {hasEditorContext && openFilesCtx && openFilesCtx.files.size > 0 && (
            <Tooltip
              text={Array.from(openFilesCtx.files.keys()).join('\n')}
              side="bottom"
            >
              <span className="chat-panel__context-hint" title="AI видит эти открытые файлы (как в Cursor)">
                {openFilesCtx.files.size} файл{openFilesCtx.files.size === 1 ? '' : openFilesCtx.files.size >= 2 && openFilesCtx.files.size <= 4 ? 'а' : 'ов'}
              </span>
            </Tooltip>
          )}
          {onCollapse && (
            <Tooltip text="Свернуть чат — больше места для кода" side="bottom">
              <button
                type="button"
                className="chat-panel__collapse-btn"
                onClick={onCollapse}
                aria-label="Свернуть чат"
              >
                <PanelRightClose size={14} />
              </button>
            </Tooltip>
          )}
        </div>
      </div>

      {/* Quick actions — Cursor-like, refined */}
      {workspace && (
        <div className="chat-panel__actions">
          <div className="chat-panel__actions-row">
            <Tooltip text="Анализ проекта" side="bottom">
              <button
                type="button"
                className="chat-panel__action"
                onClick={() => handleAnalyze()}
                disabled={busy}
                aria-label="Анализ проекта"
              >
                {analyzing ? <Loader2 size={14} className="icon-spin" /> : <Wand2 size={14} />}
                <span>Анализ</span>
              </button>
            </Tooltip>
            <div className="chat-panel__improve">
              <Tooltip text="Улучшить открытый файл" side="bottom">
                <button
                  type="button"
                  className={`chat-panel__action ${showImproveForm ? 'chat-panel__action--active' : ''}`}
                  onClick={() => setShowImproveForm((v) => !v)}
                  disabled={busy}
                  aria-label="Улучшить открытый файл"
                >
                  {improving ? <Loader2 size={14} className="icon-spin" /> : <Sparkles size={14} />}
                  <span>Improve</span>
                </button>
              </Tooltip>
              {showImproveForm && openFilesCtx?.getActiveFile?.() && (
                <div className="chat-panel__improve-form">
                  <div className="chat-panel__improve-file">
                    Файл: {openFilesCtx.getActiveFile()?.path}
                  </div>
                  <input
                    type="text"
                    className="chat-panel__improve-input"
                    placeholder="Проблема или задача (опционально)"
                    value={improveIssue}
                    onChange={(e) => setImproveIssue(e.target.value)}
                    disabled={improving}
                  />
                  <input
                    type="text"
                    className="chat-panel__improve-input"
                    placeholder="Связанные файлы через запятую (опционально)"
                    value={improveRelatedFiles}
                    onChange={(e) => setImproveRelatedFiles(e.target.value)}
                    disabled={improving}
                  />
                  <Tooltip text="Запустить улучшение" side="bottom">
                    <button
                      type="button"
                      className="chat-panel__action chat-panel__action--primary chat-panel__improve-run"
                      onClick={handleImprove}
                      disabled={improving}
                      aria-label="Запустить улучшение"
                    >
                      {improving ? <Loader2 size={14} className="icon-spin" /> : <Sparkles size={14} />}
                      Запустить
                    </button>
                  </Tooltip>
                </div>
              )}
              {showImproveForm && !openFilesCtx?.getActiveFile?.() && (
                <div className="chat-panel__improve-hint">Откройте файл в редакторе</div>
              )}
            </div>
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
              <Tooltip text="Сгенерировать код" side="bottom">
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
                  aria-label="Сгенерировать код"
                >
                  {generating ? <Loader2 size={14} className="icon-spin" /> : <Workflow size={14} />}
                  <span>Generate</span>
                </button>
              </Tooltip>
            </div>
          </div>
        </div>
      )}

      <div className="chat-panel__messages" ref={scrollRef}>
        {messages.length === 0 && (
          <div className="chat-panel__empty">
            <p className="chat-panel__empty-head">
              Чем помочь? <span className="chat-panel__empty-hint">Напишите запрос или выберите подсказку</span>
            </p>
            <div className="chat-panel__empty-suggestions">
              {[
                'Объясни этот код простыми словами',
                'Напиши юнит-тесты для этой функции',
                'Найди возможные баги и улучши код',
                'Сделай рефакторинг для читаемости',
              ].map((text) => (
                <button
                  key={text}
                  type="button"
                  className="chat-panel__empty-suggestion"
                  onClick={() => handleSend(text)}
                  disabled={busy}
                >
                  {text}
                </button>
              ))}
            </div>
            <div className="chat-panel__empty-commands">
              <span className="chat-panel__empty-command"><Globe size={14} /><code>@web</code> поиск</span>
              <span className="chat-panel__empty-command"><Code size={14} /><code>@code</code> файл</span>
              <span className="chat-panel__empty-command"><Search size={14} /><code>@rag</code> код</span>
            </div>
          </div>
        )}
        {messages.map((msg, i) => (
          <ChatMessage
            key={i}
            message={msg}
            messageIndex={i}
            onApplyEdit={applyEdit}
            onRejectEdit={rejectEdit}
          />
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
        hasEditorContext={hasEditorContext && (openFilesCtx?.files.size ?? 0) > 0}
        modeSelector={<ModeSelector modes={modes} currentMode={currentMode} onSelect={setCurrentMode} compact />}
        modelSelector={<ModelSelector value={model} onChange={setModel} />}
      />
    </div>
  )
}
