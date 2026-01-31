import { createContext, useContext, type ReactNode } from 'react'
import { useOpenFiles, type OpenFile } from './useOpenFiles'

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
}

const OpenFilesContext = createContext<OpenFilesContextValue | null>(null)

export function OpenFilesProvider({ children }: { children: ReactNode }) {
  const value = useOpenFiles()
  const getContextFiles = () => {
    const arr = Array.from(value.files.entries())
    // Active file first
    if (value.activeFile) {
      const active = arr.find(([p]) => p === value.activeFile)
      if (active) {
        const rest = arr.filter(([p]) => p !== value.activeFile)
        return [active, ...rest].map(([path, f]) => ({ path, content: f.content }))
      }
    }
    return arr.map(([path, f]) => ({ path, content: f.content }))
  }
  return (
    <OpenFilesContext.Provider value={{ ...value, getContextFiles }}>
      {children}
    </OpenFilesContext.Provider>
  )
}

export function useOpenFilesContext(): OpenFilesContextValue | null {
  return useContext(OpenFilesContext)
}
