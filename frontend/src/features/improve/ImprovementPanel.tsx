import { useState, useEffect, useCallback } from 'react'
import { useToast } from '../toast/ToastContext'

interface Issue {
  file: string
  line: number | null
  type: string
  severity: string
  message: string
  suggestion: string | null
}

interface Suggestion {
  priority: number
  title: string
  description: string
  estimated_effort?: string
  files?: string[]
}

interface AnalysisResult {
  total_files: number
  total_lines: number
  total_functions: number
  total_classes: number
  avg_complexity: number
  issues: Issue[]
  suggestions: Suggestion[]
}

interface QueueTask {
  id: string
  file_path: string
  status: string
  progress: number
  error: string | null
}

interface QueueStatus {
  total_tasks: number
  completed: number
  failed: number
  pending: number
  current_task: QueueTask | null
  tasks: QueueTask[]
}

export function ImprovementPanel() {
  const { show: showToast } = useToast()
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null)
  const [queueStatus, setQueueStatus] = useState<QueueStatus | null>(null)
  const [loading, setLoading] = useState(false)
  const [analyzing, setAnalyzing] = useState(false)
  const [workerRunning, setWorkerRunning] = useState(false)
  const [selectedFile, setSelectedFile] = useState<string | null>(null)
  const [improvementLog, setImprovementLog] = useState<string[]>([])

  // Analyze project
  const handleAnalyze = async (useLlm = false) => {
    setAnalyzing(true)
    try {
      const res = await fetch('/api/improve/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: 'src', include_linter: true, use_llm: useLlm }),
      })
      const data = await res.json()
      setAnalysis(data)
      showToast(`Анализ завершён: ${data.issues.length} проблем найдено`, 'success')
    } catch (e) {
      showToast('Ошибка анализа', 'error')
    } finally {
      setAnalyzing(false)
    }
  }

  // Run single improvement
  const handleImprove = async (filePath: string, issue?: Issue) => {
    setLoading(true)
    setImprovementLog([`Улучшение ${filePath}...`])
    
    try {
      const res = await fetch('/api/improve/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          file_path: filePath,
          issue: issue ? {
            message: issue.message,
            severity: issue.severity,
            issue_type: issue.type,
            suggestion: issue.suggestion,
          } : null,
        }),
      })
      const data = await res.json()
      
      if (data.success) {
        setImprovementLog(prev => [...prev, `✓ Успешно улучшено`, `Backup: ${data.backup_path}`])
        showToast(`Файл улучшен: ${filePath}`, 'success')
      } else {
        setImprovementLog(prev => [...prev, `✗ Ошибка: ${data.error || 'Unknown'}`])
        showToast(`Не удалось улучшить: ${data.error}`, 'error')
      }
    } catch (e) {
      showToast('Ошибка запроса', 'error')
    } finally {
      setLoading(false)
    }
  }

  // Add to queue
  const handleAddToQueue = async (filePath: string, issue?: Issue) => {
    try {
      const res = await fetch('/api/improve/queue/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          file_path: filePath,
          issue: issue ? {
            message: issue.message,
            severity: issue.severity,
            issue_type: issue.type,
          } : null,
        }),
      })
      const data = await res.json()
      showToast(`Задача добавлена: ${data.task_id.slice(0, 8)}...`, 'info')
      fetchQueueStatus()
    } catch (e) {
      showToast('Ошибка добавления', 'error')
    }
  }

  // Queue management
  const fetchQueueStatus = useCallback(async () => {
    try {
      const res = await fetch('/api/improve/queue/status')
      const data = await res.json()
      setQueueStatus(data)
    } catch {
      // ignore
    }
  }, [])

  const handleStartWorker = async () => {
    try {
      await fetch('/api/improve/queue/start', { method: 'POST' })
      setWorkerRunning(true)
      showToast('Worker запущен', 'success')
    } catch {
      showToast('Ошибка запуска worker', 'error')
    }
  }

  const handleStopWorker = async () => {
    try {
      await fetch('/api/improve/queue/stop', { method: 'POST' })
      setWorkerRunning(false)
      showToast('Worker остановлен', 'info')
    } catch {
      showToast('Ошибка остановки worker', 'error')
    }
  }

  const handleClearQueue = async () => {
    try {
      const res = await fetch('/api/improve/queue/clear', { method: 'POST' })
      const data = await res.json()
      showToast(`Очищено задач: ${data.cleared}`, 'info')
      fetchQueueStatus()
    } catch {
      showToast('Ошибка очистки', 'error')
    }
  }

  // Poll queue status when worker running
  useEffect(() => {
    if (workerRunning) {
      const interval = setInterval(fetchQueueStatus, 2000)
      return () => clearInterval(interval)
    }
  }, [workerRunning, fetchQueueStatus])

  // Group issues by file
  const issuesByFile = analysis?.issues.reduce((acc, issue) => {
    if (!acc[issue.file]) acc[issue.file] = []
    acc[issue.file].push(issue)
    return acc
  }, {} as Record<string, Issue[]>) || {}

  const severityColor = (severity: string) => {
    switch (severity) {
      case 'critical': return '#ef4444'
      case 'high': return '#f97316'
      case 'medium': return '#eab308'
      case 'low': return '#22c55e'
      default: return '#888'
    }
  }

  return (
    <div className="improvement-panel">
      <div className="improvement-panel__header">
        <h2>Self-Improvement</h2>
        <div className="improvement-panel__actions">
          <button 
            onClick={() => handleAnalyze(false)} 
            disabled={analyzing}
            className="improvement-btn"
          >
            {analyzing ? '⏳ Анализ...' : '🔍 Анализировать'}
          </button>
          <button 
            onClick={() => handleAnalyze(true)} 
            disabled={analyzing}
            className="improvement-btn improvement-btn--secondary"
            title="Использовать LLM для глубокого анализа"
          >
            🤖 LLM анализ
          </button>
        </div>
      </div>

      {analysis && (
        <div className="improvement-panel__stats">
          <div className="stat">
            <span className="stat__value">{analysis.total_files}</span>
            <span className="stat__label">Файлов</span>
          </div>
          <div className="stat">
            <span className="stat__value">{analysis.total_lines}</span>
            <span className="stat__label">Строк</span>
          </div>
          <div className="stat">
            <span className="stat__value">{analysis.total_functions}</span>
            <span className="stat__label">Функций</span>
          </div>
          <div className="stat">
            <span className="stat__value">{analysis.avg_complexity.toFixed(1)}</span>
            <span className="stat__label">Сложность</span>
          </div>
          <div className="stat">
            <span className="stat__value" style={{ color: analysis.issues.length > 0 ? '#f97316' : '#22c55e' }}>
              {analysis.issues.length}
            </span>
            <span className="stat__label">Проблем</span>
          </div>
        </div>
      )}

      {analysis?.suggestions && analysis.suggestions.length > 0 && (
        <div className="improvement-panel__suggestions">
          <h3>Рекомендации</h3>
          {analysis.suggestions.map((s, i) => (
            <div key={i} className="suggestion">
              <span className="suggestion__priority">#{s.priority}</span>
              <div className="suggestion__content">
                <strong>{s.title}</strong>
                <p>{s.description}</p>
                {s.files && <small>Файлы: {s.files.slice(0, 3).join(', ')}</small>}
              </div>
              {s.estimated_effort && (
                <span className={`suggestion__effort suggestion__effort--${s.estimated_effort}`}>
                  {s.estimated_effort}
                </span>
              )}
            </div>
          ))}
        </div>
      )}

      {Object.keys(issuesByFile).length > 0 && (
        <div className="improvement-panel__issues">
          <h3>Проблемы по файлам</h3>
          <div className="file-list">
            {Object.entries(issuesByFile).map(([file, issues]) => (
              <div key={file} className="file-item">
                <div 
                  className="file-item__header"
                  onClick={() => setSelectedFile(selectedFile === file ? null : file)}
                >
                  <span className="file-item__name">{file.replace(/.*\/src\//, 'src/')}</span>
                  <span className="file-item__count">{issues.length}</span>
                  <button 
                    className="file-item__btn"
                    onClick={(e) => { e.stopPropagation(); handleAddToQueue(file) }}
                    title="Добавить в очередь"
                  >
                    +
                  </button>
                </div>
                {selectedFile === file && (
                  <div className="file-item__issues">
                    {issues.map((issue, i) => (
                      <div key={i} className="issue-item">
                        <span 
                          className="issue-item__severity"
                          style={{ backgroundColor: severityColor(issue.severity) }}
                        >
                          {issue.severity[0].toUpperCase()}
                        </span>
                        <div className="issue-item__content">
                          <span className="issue-item__type">[{issue.type}]</span>
                          {issue.line && <span className="issue-item__line">L{issue.line}</span>}
                          <span className="issue-item__message">{issue.message}</span>
                        </div>
                        <button 
                          className="issue-item__fix"
                          onClick={() => handleImprove(file, issue)}
                          disabled={loading}
                          title="Исправить"
                        >
                          🔧
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="improvement-panel__queue">
        <div className="queue-header">
          <h3>Очередь задач</h3>
          <div className="queue-controls">
            {!workerRunning ? (
              <button onClick={handleStartWorker} className="improvement-btn improvement-btn--small">
                ▶ Запустить
              </button>
            ) : (
              <button onClick={handleStopWorker} className="improvement-btn improvement-btn--small improvement-btn--danger">
                ⏹ Остановить
              </button>
            )}
            <button onClick={handleClearQueue} className="improvement-btn improvement-btn--small">
              🗑 Очистить
            </button>
          </div>
        </div>
        
        {queueStatus && (
          <div className="queue-stats">
            <span>Всего: {queueStatus.total_tasks}</span>
            <span className="queue-stats__success">✓ {queueStatus.completed}</span>
            <span className="queue-stats__failed">✗ {queueStatus.failed}</span>
            <span className="queue-stats__pending">⏳ {queueStatus.pending}</span>
          </div>
        )}

        {queueStatus?.current_task && (
          <div className="queue-current">
            <span>Текущая: {queueStatus.current_task.file_path}</span>
            <div className="progress-bar">
              <div 
                className="progress-bar__fill"
                style={{ width: `${queueStatus.current_task.progress * 100}%` }}
              />
            </div>
            <span>{queueStatus.current_task.status}</span>
          </div>
        )}
      </div>

      {improvementLog.length > 0 && (
        <div className="improvement-panel__log">
          <h3>Лог</h3>
          <pre>{improvementLog.join('\n')}</pre>
        </div>
      )}
    </div>
  )
}
