import { useState } from 'react'
import { useGitStatus } from './useGitStatus'
import type { GitFile, GitLogEntry } from './useGitStatus'
import { useToast } from '../toast/ToastContext'

interface GitPanelProps {
  onFileClick?: (path: string) => void
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
  
  return (
    <div className="git-file" onClick={onClick}>
      <span className="git-file__icon" style={{ color: statusInfo.color }}>
        {file.status}
      </span>
      <span className="git-file__path">{file.path}</span>
      {file.staged && <span className="git-file__staged">staged</span>}
    </div>
  )
}

function LogEntry({ entry }: { entry: GitLogEntry }) {
  return (
    <div className="git-log-entry">
      <div className="git-log-entry__header">
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

  const handleCommit = async () => {
    if (!commitMessage.trim()) {
      showToast('Commit message is required', 'error')
      return
    }

    const result = await commit(commitMessage)
    if (result.success) {
      showToast(`Committed: ${result.hash}`, 'success')
      setCommitMessage('')
    } else {
      showToast(result.error || 'Commit failed', 'error')
    }
  }

  const handleViewDiff = async (path: string) => {
    const diff = await getDiff(path)
    if (diff) {
      setSelectedDiff({ path, diff })
    } else {
      showToast('No diff available', 'info')
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
          <button onClick={fetchStatus}>Retry</button>
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
            {status.branch}
            {(status.ahead > 0 || status.behind > 0) && (
              <span className="git-panel__sync">
                {status.ahead > 0 && `↑${status.ahead}`}
                {status.behind > 0 && `↓${status.behind}`}
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
          Changes ({status?.files.length || 0})
        </button>
        <button
          className={`git-panel__tab ${activeTab === 'history' ? 'git-panel__tab--active' : ''}`}
          onClick={() => setActiveTab('history')}
        >
          History
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
              placeholder="Commit message"
              onKeyDown={(e) => e.key === 'Enter' && handleCommit()}
            />
            <button
              className="git-panel__commit-btn"
              onClick={handleCommit}
              disabled={loading || !commitMessage.trim()}
            >
              {loading ? '...' : 'Commit All'}
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
              No changes
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
            <div className="git-panel__empty">No commits yet</div>
          )}
        </div>
      )}

      {/* Diff modal */}
      {selectedDiff && (
        <div className="git-panel__diff-overlay" onClick={() => setSelectedDiff(null)}>
          <div className="git-panel__diff-modal" onClick={(e) => e.stopPropagation()}>
            <div className="git-panel__diff-header">
              <span>{selectedDiff.path}</span>
              <button onClick={() => setSelectedDiff(null)}>✕</button>
            </div>
            <pre className="git-panel__diff-content">{selectedDiff.diff || 'No changes'}</pre>
          </div>
        </div>
      )}
    </div>
  )
}
