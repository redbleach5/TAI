import { useEffect, useCallback, useState } from 'react'
import Editor from '@monaco-editor/react'
import { useToast } from '../toast/ToastContext'
import { useOpenFiles } from './useOpenFiles'
import { EditorTabs } from './EditorTabs'

interface MultiFileEditorProps {
  onOpenFile?: (path: string) => void
  externalOpenFile?: string | null
}

export function MultiFileEditor({ externalOpenFile }: MultiFileEditorProps) {
  const { show: showToast } = useToast()
  const {
    files,
    activeFile,
    setActiveFile,
    openFile,
    closeFile,
    updateContent,
    saveFile,
    getActiveFile,
  } = useOpenFiles()

  const [output, setOutput] = useState<string | null>(null)
  const [running, setRunning] = useState(false)

  // Open file when requested externally
  useEffect(() => {
    if (externalOpenFile) {
      openFile(externalOpenFile)
    }
  }, [externalOpenFile, openFile])

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ctrl/Cmd + S to save
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault()
        if (activeFile) {
          handleSave()
        }
      }
      // Ctrl/Cmd + W to close tab
      if ((e.ctrlKey || e.metaKey) && e.key === 'w') {
        e.preventDefault()
        if (activeFile) {
          closeFile(activeFile)
        }
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [activeFile, closeFile])

  const handleEditorChange = useCallback((value: string | undefined) => {
    if (activeFile && value !== undefined) {
      updateContent(activeFile, value)
    }
  }, [activeFile, updateContent])

  const handleSave = async () => {
    if (!activeFile) return
    const result = await saveFile(activeFile)
    if (result.success) {
      showToast('Saved', 'success')
    } else {
      showToast(result.error || 'Save failed', 'error')
    }
  }

  const handleRun = async () => {
    const file = getActiveFile()
    if (!file || file.language !== 'python') {
      showToast('Only Python files can be run', 'error')
      return
    }

    setRunning(true)
    setOutput(null)

    try {
      const res = await fetch('/api/code/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code: file.content }),
      })
      const data = await res.json()
      setOutput(data.output || data.error || 'Done')
      if (data.success) {
        showToast('Executed successfully', 'success')
      } else {
        showToast('Execution failed', 'error')
      }
    } catch (e) {
      setOutput(`Error: ${e instanceof Error ? e.message : 'Unknown'}`)
      showToast('Execution failed', 'error')
    } finally {
      setRunning(false)
    }
  }

  const handleCopy = async () => {
    const file = getActiveFile()
    if (!file) return
    
    try {
      await navigator.clipboard.writeText(file.content)
      showToast('Copied to clipboard', 'success')
    } catch {
      showToast('Copy failed', 'error')
    }
  }

  const handleDownload = () => {
    const file = getActiveFile()
    if (!file) return
    
    const blob = new Blob([file.content], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = file.name
    a.click()
    URL.revokeObjectURL(url)
  }

  const currentFile = getActiveFile()
  const canRun = currentFile?.language === 'python'

  return (
    <div className="multi-editor">
      <EditorTabs
        files={files}
        activeFile={activeFile}
        onSelect={setActiveFile}
        onClose={closeFile}
      />
      
      <div className="multi-editor__toolbar">
        {currentFile && (
          <>
            <span className="multi-editor__path">
              {currentFile.path}
              {currentFile.isDirty && <span className="multi-editor__unsaved"> ●</span>}
            </span>
            <div className="multi-editor__actions">
              {canRun && (
                <button
                  className="multi-editor__btn multi-editor__btn--primary"
                  onClick={handleRun}
                  disabled={running}
                  title="Run (Python)"
                >
                  {running ? '⏳' : '▶'} Run
                </button>
              )}
              {currentFile.isDirty && (
                <button
                  className="multi-editor__btn"
                  onClick={handleSave}
                  title="Save (Ctrl+S)"
                >
                  Save
                </button>
              )}
              <button
                className="multi-editor__btn"
                onClick={handleCopy}
                title="Copy"
              >
                Copy
              </button>
              <button
                className="multi-editor__btn"
                onClick={handleDownload}
                title="Download"
              >
                Download
              </button>
            </div>
          </>
        )}
      </div>

      <div className="multi-editor__content">
        {currentFile ? (
          <Editor
            height="100%"
            language={currentFile.language}
            value={currentFile.content}
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
          <div className="multi-editor__empty">
            <p>Select a file from the sidebar to edit</p>
            <p className="multi-editor__hint">
              Double-click a file to open it
            </p>
          </div>
        )}
      </div>

      {output && (
        <div className="multi-editor__output">
          <div className="multi-editor__output-header">
            <span>Output</span>
            <button
              className="multi-editor__output-close"
              onClick={() => setOutput(null)}
            >
              ✕
            </button>
          </div>
          <pre className="multi-editor__output-content">{output}</pre>
        </div>
      )}
    </div>
  )
}
