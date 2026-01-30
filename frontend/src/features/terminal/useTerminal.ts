import { useState, useCallback } from 'react'

interface TerminalOutput {
  type: 'input' | 'stdout' | 'stderr' | 'error' | 'info'
  text: string
}

export function useTerminal() {
  const [output, setOutput] = useState<TerminalOutput[]>([])
  const [running, setRunning] = useState(false)
  const [history, setHistory] = useState<string[]>([])
  const [historyIndex, setHistoryIndex] = useState(-1)

  const clearOutput = useCallback(() => {
    setOutput([])
  }, [])

  const addOutput = useCallback((type: TerminalOutput['type'], text: string) => {
    setOutput((prev) => [...prev, { type, text }])
  }, [])

  const executeCommand = useCallback(async (command: string) => {
    if (!command.trim()) return

    // Add to history
    setHistory((prev) => {
      const filtered = prev.filter((c) => c !== command)
      return [...filtered, command].slice(-100)  // Keep last 100 commands
    })
    setHistoryIndex(-1)

    // Show input
    addOutput('input', `$ ${command}`)
    setRunning(true)

    try {
      const res = await fetch('/api/terminal/exec', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command, timeout: 30 }),
      })
      const data = await res.json()

      if (data.stdout) {
        addOutput('stdout', data.stdout)
      }
      if (data.stderr) {
        addOutput('stderr', data.stderr)
      }
      if (data.error) {
        addOutput('error', data.error)
      }
      if (!data.success && !data.error && !data.stderr) {
        addOutput('error', `Exit code: ${data.exit_code}`)
      }
    } catch (e) {
      addOutput('error', e instanceof Error ? e.message : 'Command failed')
    } finally {
      setRunning(false)
    }
  }, [addOutput])

  const getPrevCommand = useCallback(() => {
    if (history.length === 0) return ''
    const newIndex = historyIndex < 0 
      ? history.length - 1 
      : Math.max(0, historyIndex - 1)
    setHistoryIndex(newIndex)
    return history[newIndex] || ''
  }, [history, historyIndex])

  const getNextCommand = useCallback(() => {
    if (historyIndex < 0) return ''
    const newIndex = historyIndex + 1
    if (newIndex >= history.length) {
      setHistoryIndex(-1)
      return ''
    }
    setHistoryIndex(newIndex)
    return history[newIndex] || ''
  }, [history, historyIndex])

  return {
    output,
    running,
    clearOutput,
    executeCommand,
    getPrevCommand,
    getNextCommand,
  }
}
