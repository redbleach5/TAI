import { useEffect, useCallback, useState, useRef } from 'react'
import Editor from '@monaco-editor/react'
import { API_BASE } from '../../api/client'
import { useToast } from '../toast/ToastContext'
import { useOpenFilesContext, type OpenFilesContextValue } from './OpenFilesContext'
import { useOpenFiles } from './useOpenFiles'
import { EditorTabs } from './EditorTabs'

interface MultiFileEditorProps {
  onOpenFile?: (path: string) => void
  externalOpenFile?: string | null
}

export function MultiFileEditor({ externalOpenFile }: MultiFileEditorProps) {
  const { show: showToast } = useToast()
  const ctx = useOpenFilesContext()
  const fallback = useOpenFiles()
  const {
    files,
    activeFile,
    setActiveFile,
    openFile,
    closeFile,
    updateContent,
    saveFile,
    getActiveFile,
  } = ctx ?? fallback

  const [output, setOutput] = useState<string | null>(null)
  const [running, setRunning] = useState(false)
  const openFileRef = useRef(openFile)
  openFileRef.current = openFile

  // Open file when user selects from sidebar — only when externalOpenFile CHANGES.
  // Must NOT depend on openFile: it changes when files change (e.g. on close), which would re-open the closed file.
  useEffect(() => {
    if (externalOpenFile) {
      openFileRef.current(externalOpenFile)
    }
  }, [externalOpenFile])

  // B6: unregister editor ref on unmount
  useEffect(() => {
    return () => {
      (ctx as OpenFilesContextValue | null)?.setEditorRef?.(null)
    }
  }, [ctx])

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
      showToast('Готово', 'success')
    } else {
      showToast(result.error || 'Что-то пошло не так', 'error')
    }
  }

  const handleRun = async () => {
    const file = getActiveFile()
    if (!file || file.language !== 'python') {
      showToast('Только Python-файлы можно запустить', 'error')
      return
    }

    setRunning(true)
    setOutput(null)

    try {
      const res = await fetch(`${API_BASE}/code/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code: file.content }),
      })
      const data = await res.json()
      setOutput(data.output || data.error || 'Done')
      if (data.success) {
        showToast('Готово', 'success')
      } else {
        showToast('Что-то пошло не так', 'error')
      }
    } catch (e) {
      setOutput(`Error: ${e instanceof Error ? e.message : 'Unknown'}`)
      showToast('Что-то пошло не так', 'error')
    } finally {
      setRunning(false)
    }
  }

  const handleCopy = async () => {
    const file = getActiveFile()
    if (!file) return
    
    try {
      await navigator.clipboard.writeText(file.content)
      showToast('Скопировано в буфер обмена', 'success')
    } catch {
      showToast('Не удалось скопировать', 'error')
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
      <div className="multi-editor__header">
        <EditorTabs
          files={files}
          activeFile={activeFile}
          onSelect={setActiveFile}
          onClose={closeFile}
        />
        {currentFile && (
          <div className="multi-editor__toolbar">
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
          </div>
        )}
      </div>

      <div className="multi-editor__content">
        {currentFile ? (
          <Editor
            height="100%"
            language={currentFile.language}
            value={currentFile.content}
            onChange={handleEditorChange}
            onMount={(editor) => {
              (ctx as OpenFilesContextValue | null)?.setEditorRef?.(editor)
            }}
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
            <p>Открой файл или начни с подсказки</p>
            <p className="multi-editor__hint">
              Двойной клик по файлу в боковой панели
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
