import { createContext, useContext, useState, useCallback, type ReactNode } from 'react'
import { useOpenFiles, type OpenFile } from './useOpenFiles'

/** B6: minimal editor API for selection (avoids importing monaco in context). */
export interface EditorInstance {
  getSelection(): { startLineNumber: number; endLineNumber: number; startColumn: number; endColumn: number } | null
  getModel(): { getValueInRange(r: { startLineNumber: number; startColumn: number; endLineNumber: number; endColumn: number }): string } | null
}

export interface EditorSelection {
  startLine: number
  endLine: number
  text: string
}

export interface OpenFilesContextValue {
  files: Map<string, OpenFile>
  activeFile: string | null
  setActiveFile: (path: string | null) => void
  openFile: (path: string) => Promise<void>
  closeFile: (path: string) => void
  updateContent: (path: string, content: string) => void
  saveFile: (path: string) => Promise<{ success: boolean; error?: string }>
  getActiveFile: () => OpenFile | undefined | null
  /** Get open files for chat context - active file first */
  getContextFiles: () => Array<{ path: string; content: string }>
  /** B6: set Monaco editor ref (called from MultiFileEditor onMount). */
  setEditorRef: (editor: EditorInstance | null) => void
  /** B6: get current selection in active editor (for "Improve selected"). */
  getActiveSelection: () => EditorSelection | null
}

const OpenFilesContext = createContext<OpenFilesContextValue | null>(null)

export function OpenFilesProvider({ children }: { children: ReactNode }) {
  const value = useOpenFiles()
  const [editorRef, setEditorRef] = useState<EditorInstance | null>(null)

  const getContextFiles = useCallback(() => {
    const arr = Array.from(value.files.entries())
    if (value.activeFile) {
      const active = arr.find(([p]) => p === value.activeFile)
      if (active) {
        const rest = arr.filter(([p]) => p !== value.activeFile)
        return [active, ...rest].map(([path, f]) => ({ path, content: f.content }))
      }
    }
    return arr.map(([path, f]) => ({ path, content: f.content }))
  }, [value.files, value.activeFile])

  const getActiveSelection = useCallback((): EditorSelection | null => {
    if (!editorRef) return null
    const sel = editorRef.getSelection()
    if (!sel) return null
    const model = editorRef.getModel()
    if (!model) return null
    const text = model.getValueInRange(sel)
    if (!text.trim()) return null
    return { startLine: sel.startLineNumber, endLine: sel.endLineNumber, text }
  }, [editorRef])

  return (
    <OpenFilesContext.Provider
      value={{
        ...value,
        getContextFiles,
        setEditorRef,
        getActiveSelection,
      }}
    >
      {children}
    </OpenFilesContext.Provider>
  )
}

export function useOpenFilesContext(): OpenFilesContextValue | null {
  return useContext(OpenFilesContext)
}
