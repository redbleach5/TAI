import { useState, useEffect } from 'react'
import { 
  GitBranch, 
  GitCommit, 
  History, 
  FileEdit, 
  FilePlus, 
  FileMinus, 
  FileQuestion, 
  RefreshCw,
  X,
  Check,
  ArrowUp,
  ArrowDown
} from 'lucide-react'
import { useGitStatus } from './useGitStatus'
import type { GitFile, GitLogEntry } from './useGitStatus'
import { useToast } from '../toast/ToastContext'

interface GitPanelProps {
  onFileClick?: (path: string) => void
}

const STATUS_ICONS: Record<string, typeof FileEdit> = {
  'M': FileEdit,
  'A': FilePlus,
  'D': FileMinus,
  '?': FileQuestion,
  'R': FileEdit,
  'U': FileEdit,
}

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  'M': { label: 'Modified', color: '#e2b93d' },
  'A': { label: 'Added', color: '#73c991' },
  'D': { label: 'Deleted', color: '#f14c4c' },
  '?': { label: 'Untracked', color: '#6e6e6e' },
  'R': { label: 'Renamed', color: '#73c991' },
  'U': { label: 'Conflict', color: '#f14c4c' },
}

function FileItem({ file, onClick }: { file: GitFile; onClick?: () => void }) {
  const statusInfo = STATUS_LABELS[file.status] || { label: file.status, color: '#ccc' }
  const StatusIcon = STATUS_ICONS[file.status] || FileEdit
  
  return (
    <div className="git-file" onClick={onClick}>
      <span className="git-file__icon" style={{ color: statusInfo.color }}>
        <StatusIcon size={14} />
      </span>
      <span className="git-file__path">{file.path}</span>
      {file.staged && (
        <span className="git-file__staged">
          <Check size={10} />
          staged
        </span>
      )}
    </div>
  )
}

function LogEntry({ entry }: { entry: GitLogEntry }) {
  return (
    <div className="git-log-entry">
      <div className="git-log-entry__header">
        <GitCommit size={12} className="git-log-entry__icon" />
        <span className="git-log-entry__hash">{entry.short_hash}</span>
        <span className="git-log-entry__author">{entry.author}</span>
      </div>
      <div className="git-log-entry__message">{entry.message}</div>
      <div className="git-log-entry__date">{entry.date}</div>
    </div>
  )
}

export function GitPanel({ onFileClick }: GitPanelProps) {
  const { show: showToast } = useToast()
  const { status, log, loading, error, fetchStatus, commit, getDiff } = useGitStatus()
  const [commitMessage, setCommitMessage] = useState('')
  const [selectedDiff, setSelectedDiff] = useState<{ path: string; diff: string } | null>(null)
  const [activeTab, setActiveTab] = useState<'changes' | 'history'>('changes')

  useEffect(() => {
    if (!selectedDiff) return
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setSelectedDiff(null)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [selectedDiff])

  const handleCommit = async () => {
    if (!commitMessage.trim()) {
      showToast('Введи сообщение коммита', 'error')
      return
    }

    const result = await commit(commitMessage)
    if (result.success) {
      showToast('Готово', 'success')
      setCommitMessage('')
    } else {
      showToast(result.error || 'Что-то пошло не так', 'error')
    }
  }

  const handleViewDiff = async (path: string) => {
    const diff = await getDiff(path)
    if (diff) {
      setSelectedDiff({ path, diff })
    } else {
      showToast('Нет изменений для просмотра', 'info')
    }
  }

  const stagedFiles = status?.files.filter((f) => f.staged) || []
  const unstagedFiles = status?.files.filter((f) => !f.staged) || []

  if (error) {
    return (
      <div className="git-panel">
        <div className="git-panel__header">
          <span className="git-panel__title">Source Control</span>
        </div>
        <div className="git-panel__error">
          {error}
          <button onClick={fetchStatus}>
            <RefreshCw size={12} />
            Повторить
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="git-panel">
      <div className="git-panel__header">
        <span className="git-panel__title">Source Control</span>
        {status?.branch && (
          <span className="git-panel__branch">
            <GitBranch size={12} />
            {status.branch}
            {(status.ahead > 0 || status.behind > 0) && (
              <span className="git-panel__sync">
                {status.ahead > 0 && <><ArrowUp size={10} />{status.ahead}</>}
                {status.behind > 0 && <><ArrowDown size={10} />{status.behind}</>}
              </span>
            )}
          </span>
        )}
      </div>

      <div className="git-panel__tabs">
        <button
          className={`git-panel__tab ${activeTab === 'changes' ? 'git-panel__tab--active' : ''}`}
          onClick={() => setActiveTab('changes')}
        >
          <FileEdit size={14} />
          <span>Changes ({status?.files.length || 0})</span>
        </button>
        <button
          className={`git-panel__tab ${activeTab === 'history' ? 'git-panel__tab--active' : ''}`}
          onClick={() => setActiveTab('history')}
        >
          <History size={14} />
          <span>История</span>
        </button>
      </div>

      {activeTab === 'changes' && (
        <div className="git-panel__content">
          {/* Commit input */}
          <div className="git-panel__commit">
            <input
              type="text"
              className="git-panel__commit-input"
              value={commitMessage}
              onChange={(e) => setCommitMessage(e.target.value)}
              placeholder="Сообщение коммита"
              onKeyDown={(e) => e.key === 'Enter' && handleCommit()}
            />
            <button
              className="git-panel__commit-btn"
              onClick={handleCommit}
              disabled={loading || !commitMessage.trim()}
            >
              {loading ? '...' : 'Commit'}
            </button>
          </div>

          {/* Staged files */}
          {stagedFiles.length > 0 && (
            <div className="git-panel__section">
              <div className="git-panel__section-title">Staged Changes</div>
              {stagedFiles.map((file) => (
                <FileItem
                  key={file.path}
                  file={file}
                  onClick={() => handleViewDiff(file.path)}
                />
              ))}
            </div>
          )}

          {/* Unstaged files */}
          {unstagedFiles.length > 0 && (
            <div className="git-panel__section">
              <div className="git-panel__section-title">Changes</div>
              {unstagedFiles.map((file) => (
                <FileItem
                  key={file.path}
                  file={file}
                  onClick={() => {
                    handleViewDiff(file.path)
                    onFileClick?.(file.path)
                  }}
                />
              ))}
            </div>
          )}

          {status?.files.length === 0 && (
            <div className="git-panel__empty">
              Нет изменений
            </div>
          )}
        </div>
      )}

      {activeTab === 'history' && (
        <div className="git-panel__content git-panel__log">
          {log.map((entry) => (
            <LogEntry key={entry.hash} entry={entry} />
          ))}
          {log.length === 0 && (
            <div className="git-panel__empty">Нет коммитов</div>
          )}
        </div>
      )}

      {/* Diff modal */}
      {selectedDiff && (
        <div className="git-panel__diff-overlay" onClick={() => setSelectedDiff(null)}>
          <div className="git-panel__diff-modal" onClick={(e) => e.stopPropagation()}>
            <div className="git-panel__diff-header">
              <span>{selectedDiff.path}</span>
              <button onClick={() => setSelectedDiff(null)}>
                <X size={16} />
              </button>
            </div>
            <pre className="git-panel__diff-content">{selectedDiff.diff || 'Нет изменений'}</pre>
          </div>
        </div>
      )}
    </div>
  )
}
