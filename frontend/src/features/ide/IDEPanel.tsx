import { useState, useCallback } from 'react'
import Editor from '@monaco-editor/react'
import { useToast } from '../toast/ToastContext'
import { useWorkflowCode } from './WorkflowCodeContext'

type IDETab = 'code' | 'tests' | 'plan'

const TAB_LABELS: Record<IDETab, string> = {
  code: 'Код',
  tests: 'Тесты',
  plan: 'План',
}

const TAB_FILES: Record<IDETab, string> = {
  code: 'generated.py',
  tests: 'test_generated.py',
  plan: 'plan.md',
}

const TAB_LANGUAGES: Record<IDETab, string> = {
  code: 'python',
  tests: 'python',
  plan: 'markdown',
}

export function IDEPanel() {
  const { state, setState } = useWorkflowCode()
  const { show: showToast } = useToast()
  const [activeTab, setActiveTab] = useState<IDETab>('code')
  const [copied, setCopied] = useState(false)
  const [running, setRunning] = useState(false)
  const [output, setOutput] = useState<string | null>(null)

  // Local editable state
  const [localCode, setLocalCode] = useState<string | null>(null)
  const [localTests, setLocalTests] = useState<string | null>(null)
  const [localPlan, setLocalPlan] = useState<string | null>(null)

  const getContent = useCallback((tab: IDETab) => {
    switch (tab) {
      case 'code':
        return localCode ?? state.code ?? ''
      case 'tests':
        return localTests ?? state.tests ?? ''
      case 'plan':
        return localPlan ?? state.plan ?? ''
    }
  }, [localCode, localTests, localPlan, state])

  const setContent = useCallback((tab: IDETab, value: string) => {
    switch (tab) {
      case 'code':
        setLocalCode(value)
        break
      case 'tests':
        setLocalTests(value)
        break
      case 'plan':
        setLocalPlan(value)
        break
    }
  }, [])

  const displayCode = getContent(activeTab)
  const hasContent = !!displayCode
  const hasAnyOutput = !!(getContent('code') || getContent('tests') || getContent('plan'))
  const fileName = TAB_FILES[activeTab]
  const language = TAB_LANGUAGES[activeTab]

  const handleEditorChange = (value: string | undefined) => {
    if (value !== undefined) {
      setContent(activeTab, value)
    }
  }

  const handleCopy = async () => {
    if (!displayCode) return
    try {
      await navigator.clipboard.writeText(displayCode)
      setCopied(true)
      showToast('Скопировано в буфер обмена', 'success')
      setTimeout(() => setCopied(false), 2000)
    } catch {
      const ta = document.createElement('textarea')
      ta.value = displayCode
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
      setCopied(true)
      showToast('Скопировано в буфер обмена', 'success')
      setTimeout(() => setCopied(false), 2000)
    }
  }

  const handleDownload = () => {
    if (!displayCode) return
    const blob = new Blob([displayCode], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = fileName
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleRun = async () => {
    const code = getContent('code')
    if (!code) {
      showToast('Нет кода для выполнения', 'error')
      return
    }
    setRunning(true)
    setOutput(null)
    try {
      const res = await fetch('/api/code/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code, tests: getContent('tests') }),
      })
      const data = await res.json()
      setOutput(data.output || data.error || 'Выполнено')
      if (data.success) {
        showToast('Код выполнен успешно', 'success')
      } else {
        showToast('Ошибка выполнения', 'error')
      }
    } catch (e) {
      setOutput(`Ошибка: ${e instanceof Error ? e.message : 'Unknown'}`)
      showToast('Не удалось выполнить код', 'error')
    } finally {
      setRunning(false)
    }
  }

  const handleSave = () => {
    // Sync local edits to workflow state
    setState({
      code: localCode ?? state.code ?? '',
      tests: localTests ?? state.tests ?? '',
      plan: localPlan ?? state.plan ?? '',
    })
    showToast('Изменения сохранены', 'success')
  }

  const hasUnsavedChanges =
    (localCode !== null && localCode !== state.code) ||
    (localTests !== null && localTests !== state.tests) ||
    (localPlan !== null && localPlan !== state.plan)

  return (
    <div className="ide-panel">
      <div className="ide-panel__tabs">
        {(Object.keys(TAB_LABELS) as IDETab[]).map((tab) => (
          <button
            key={tab}
            type="button"
            className={`ide-panel__tab ${activeTab === tab ? 'ide-panel__tab--active' : ''} ${getContent(tab) ? 'ide-panel__tab--has-content' : ''}`}
            onClick={() => setActiveTab(tab)}
          >
            {TAB_LABELS[tab]}
            {getContent(tab) && <span className="ide-panel__tab-dot" />}
          </button>
        ))}
      </div>
      <div className="ide-panel__toolbar">
        <span className="ide-panel__filename">
          {fileName}
          {hasUnsavedChanges && <span className="ide-panel__unsaved"> •</span>}
        </span>
        <div className="ide-panel__actions">
          {activeTab === 'code' && (
            <button
              type="button"
              className="ide-panel__btn ide-panel__btn--primary"
              onClick={handleRun}
              disabled={!hasContent || running}
              title="Выполнить код"
            >
              {running ? '⏳ Выполняется...' : '▶ Запустить'}
            </button>
          )}
          {hasUnsavedChanges && (
            <button
              type="button"
              className="ide-panel__btn"
              onClick={handleSave}
              title="Сохранить изменения"
            >
              💾 Сохранить
            </button>
          )}
          <button
            type="button"
            className={`ide-panel__btn ${copied ? 'ide-panel__btn--success' : ''}`}
            onClick={handleCopy}
            disabled={!hasContent}
            title="Копировать"
          >
            {copied ? '✓ Скопировано' : 'Копировать'}
          </button>
          <button
            type="button"
            className="ide-panel__btn"
            onClick={handleDownload}
            disabled={!hasContent}
            title="Скачать"
          >
            Скачать
          </button>
        </div>
      </div>
      <div className="ide-panel__editor">
        {hasContent || hasAnyOutput ? (
          <Editor
            height="100%"
            language={language}
            value={displayCode}
            onChange={handleEditorChange}
            theme="vs-dark"
            options={{
              minimap: { enabled: false },
              fontSize: 14,
              lineNumbers: 'on',
              scrollBeyondLastLine: false,
              automaticLayout: true,
              wordWrap: 'on',
              tabSize: 4,
              insertSpaces: true,
            }}
          />
        ) : (
          <div className="ide-panel__empty">
            <p>Сгенерированный код появится здесь после выполнения Workflow.</p>
            <p>Перейдите во вкладку Workflow и запустите задачу.</p>
          </div>
        )}
      </div>
      {output && (
        <div className="ide-panel__output">
          <div className="ide-panel__output-header">
            <span>Вывод</span>
            <button
              type="button"
              className="ide-panel__output-close"
              onClick={() => setOutput(null)}
            >
              ✕
            </button>
          </div>
          <pre className="ide-panel__output-content">{output}</pre>
        </div>
      )}
    </div>
  )
}
