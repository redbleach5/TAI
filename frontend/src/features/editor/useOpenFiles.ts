import { useState, useCallback } from 'react'

export interface OpenFile {
  path: string
  name: string
  content: string
  originalContent: string
  language: string
  isDirty: boolean
}

const LANGUAGE_MAP: Record<string, string> = {
  py: 'python',
  ts: 'typescript',
  tsx: 'typescript',
  js: 'javascript',
  jsx: 'javascript',
  json: 'json',
  md: 'markdown',
  toml: 'toml',
  yaml: 'yaml',
  yml: 'yaml',
  css: 'css',
  html: 'html',
  sh: 'shell',
  txt: 'plaintext',
}

function getLanguage(path: string): string {
  const ext = path.split('.').pop()?.toLowerCase() || ''
  return LANGUAGE_MAP[ext] || 'plaintext'
}

function getFileName(path: string): string {
  return path.split('/').pop() || path
}

export function useOpenFiles() {
  const [files, setFiles] = useState<Map<string, OpenFile>>(new Map())
  const [activeFile, setActiveFile] = useState<string | null>(null)

  const openFile = useCallback(async (path: string) => {
    // Skip if path is empty, a dot, or a directory path
    if (!path || path === '.' || path === './' || path.endsWith('/')) {
      return
    }

    // If already open, just activate
    if (files.has(path)) {
      setActiveFile(path)
      return
    }

    // Fetch file content
    try {
      const res = await fetch('/api/files/read', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path }),
      })
      const data = await res.json()
      
      if (!data.success) {
        console.error('Failed to open file:', data.error)
        return
      }

      const newFile: OpenFile = {
        path,
        name: getFileName(path),
        content: data.content || '',
        originalContent: data.content || '',
        language: getLanguage(path),
        isDirty: false,
      }

      setFiles((prev) => {
        const next = new Map(prev)
        next.set(path, newFile)
        return next
      })
      setActiveFile(path)
    } catch (e) {
      console.error('Failed to open file:', e)
    }
  }, [files])

  const closeFile = useCallback((path: string) => {
    setFiles((prev) => {
      const next = new Map(prev)
      next.delete(path)
      return next
    })
    if (activeFile === path) {
      const remaining = Array.from(files.keys()).filter((p) => p !== path)
      setActiveFile(remaining.length > 0 ? remaining[remaining.length - 1] : null)
    }
  }, [files, activeFile])

  const updateContent = useCallback((path: string, content: string) => {
    setFiles((prev) => {
      const file = prev.get(path)
      if (!file) return prev
      
      const next = new Map(prev)
      next.set(path, {
        ...file,
        content,
        isDirty: content !== file.originalContent,
      })
      return next
    })
  }, [])

  const saveFile = useCallback(async (path: string) => {
    const file = files.get(path)
    if (!file) return { success: false, error: 'File not found' }

    try {
      const res = await fetch('/api/files/write', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path, content: file.content }),
      })
      const data = await res.json()
      
      if (data.success) {
        setFiles((prev) => {
          const next = new Map(prev)
          const f = next.get(path)
          if (f) {
            next.set(path, {
              ...f,
              originalContent: f.content,
              isDirty: false,
            })
          }
          return next
        })
        return { success: true }
      }
      return { success: false, error: data.error || data.detail }
    } catch (e) {
      return { success: false, error: e instanceof Error ? e.message : 'Save failed' }
    }
  }, [files])

  const saveAllFiles = useCallback(async () => {
    const dirtyFiles = Array.from(files.values()).filter((f) => f.isDirty)
    const results = await Promise.all(dirtyFiles.map((f) => saveFile(f.path)))
    return results.every((r) => r.success)
  }, [files, saveFile])

  const getActiveFile = useCallback(() => {
    return activeFile ? files.get(activeFile) : null
  }, [files, activeFile])

  const hasDirtyFiles = useCallback(() => {
    return Array.from(files.values()).some((f) => f.isDirty)
  }, [files])

  return {
    files,
    activeFile,
    setActiveFile,
    openFile,
    closeFile,
    updateContent,
    saveFile,
    saveAllFiles,
    getActiveFile,
    hasDirtyFiles,
  }
}
