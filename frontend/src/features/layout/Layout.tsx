/**
 * Cursor-like layout: IDE + Chat always visible.
 * Sidebar | Editor | Chat — no tab switching.
 * Chat panel width is resizable and persisted.
 */
import { useState, useRef, useCallback, useEffect } from 'react'
import {
  Settings,
  FolderTree,
  GitBranch,
  Database,
  FolderOpen,
  MessageSquare,
  PanelRightClose,
} from 'lucide-react'

const CHAT_PANEL_WIDTH_KEY = 'tai-chat-panel-width'
const CHAT_PANEL_COLLAPSED_KEY = 'tai-chat-panel-collapsed'
const MIN_CHAT_WIDTH = 280
const MAX_CHAT_WIDTH = 720
const DEFAULT_CHAT_WIDTH = 380
const CHAT_STRIP_WIDTH = 48

function loadChatPanelWidth(): number {
  try {
    const w = localStorage.getItem(CHAT_PANEL_WIDTH_KEY)
    if (w != null) {
      const n = parseInt(w, 10)
      if (!Number.isNaN(n) && n >= MIN_CHAT_WIDTH && n <= MAX_CHAT_WIDTH) return n
    }
  } catch {
    // ignore
  }
  return DEFAULT_CHAT_WIDTH
}

function loadChatPanelCollapsed(): boolean {
  try {
    const v = localStorage.getItem(CHAT_PANEL_COLLAPSED_KEY)
    return v === '1' || v === 'true'
  } catch {
    return false
  }
}
import { ChatPanel } from '../chat/ChatPanel'
import { SettingsPanel } from '../settings/SettingsPanel'
import { Tooltip } from '../ui/Tooltip'
import { FileBrowser } from '../files/FileBrowser'
import { ProjectSelector } from '../projects/ProjectSelector'
import { FolderPicker } from '../workspace/FolderPicker'
import { CreateProjectDialog } from '../workspace/CreateProjectDialog'
import { useWorkspace } from '../workspace/useWorkspace'
import { MultiFileEditor } from '../editor/MultiFileEditor'
import { OpenFilesProvider } from '../editor/OpenFilesContext'
import { TerminalPanel } from '../terminal/TerminalPanel'
import { GitPanel } from '../git/GitPanel'
import { useGitStatus } from '../git/useGitStatus'
import { useToast } from '../toast/ToastContext'

type SidebarTab = 'files' | 'git' | 'projects'

export function Layout() {
  const [sidebarTab, setSidebarTab] = useState<SidebarTab>('files')
  const [terminalCollapsed, setTerminalCollapsed] = useState(true)
  const [selectedFile, setSelectedFile] = useState<string | null>(null)
  const [showFolderPicker, setShowFolderPicker] = useState(false)
  const [showCreateProject, setShowCreateProject] = useState(false)
  const [showSettings, setShowSettings] = useState(false)
  const [chatPanelWidth, setChatPanelWidth] = useState(loadChatPanelWidth)
  const [chatPanelCollapsed, setChatPanelCollapsed] = useState(loadChatPanelCollapsed)
  const [resizing, setResizing] = useState(false)
  const mainRef = useRef<HTMLDivElement>(null)
  const { fileStatusMap } = useGitStatus()
  const { show: showToast } = useToast()
  const { workspace, openFolder, createProject } = useWorkspace()

  useEffect(() => {
    try {
      localStorage.setItem(CHAT_PANEL_WIDTH_KEY, String(chatPanelWidth))
    } catch {
      // ignore
    }
  }, [chatPanelWidth])

  useEffect(() => {
    try {
      localStorage.setItem(CHAT_PANEL_COLLAPSED_KEY, chatPanelCollapsed ? '1' : '0')
    } catch {
      // ignore
    }
  }, [chatPanelCollapsed])

  const handleResizeStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    setResizing(true)
  }, [])

  useEffect(() => {
    if (!resizing) return
    const move = (e: MouseEvent) => {
      const main = mainRef.current?.getBoundingClientRect()
      if (!main) return
      const newWidth = main.right - e.clientX
      setChatPanelWidth((w) => Math.min(MAX_CHAT_WIDTH, Math.max(MIN_CHAT_WIDTH, newWidth)))
    }
    const up = () => setResizing(false)
    document.addEventListener('mousemove', move)
    document.addEventListener('mouseup', up)
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
    return () => {
      document.removeEventListener('mousemove', move)
      document.removeEventListener('mouseup', up)
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }
  }, [resizing])

  const handleFileSelect = (path: string) => setSelectedFile(path)

  const handleOpenFolder = async (path: string) => {
    setShowFolderPicker(false)
    try {
      await openFolder(path)
      showToast(`Открыта папка: ${path.split('/').pop() || path}`, 'success')
      window.dispatchEvent(new CustomEvent('workspace-changed'))
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Что-то пошло не так', 'error')
    }
  }

  const handleCreateProject = async (path: string, name?: string) => {
    try {
      const data = await createProject(path, name)
      showToast(`Проект создан: ${data.name}`, 'success')
      window.dispatchEvent(new CustomEvent('workspace-changed'))
    } catch (e) {
      throw e
    }
  }

  return (
    <div className="layout layout--ide">
      <div className="layout__workspace-bar">
        <button
          type="button"
          className="layout__workspace-btn"
          onClick={() => setShowFolderPicker(true)}
          title={workspace ? workspace.path : 'Открыть папку'}
        >
          <FolderOpen size={14} />
          <span>{workspace ? workspace.name : 'Открыть папку...'}</span>
        </button>
        <button
          type="button"
          className="layout__workspace-btn layout__workspace-btn--create"
          onClick={() => setShowCreateProject(true)}
          title="Создать новый проект (папка будет создана)"
        >
          Создать проект
        </button>
        <Tooltip text="Настройки" side="bottom">
          <button
            type="button"
            className="layout__settings-btn"
            onClick={() => setShowSettings(!showSettings)}
            aria-label="Настройки"
          >
            <Settings size={14} />
          </button>
        </Tooltip>
      </div>

      <div className="layout__content">
        {showCreateProject ? (
          <CreateProjectDialog
            onCreate={handleCreateProject}
            onCancel={() => setShowCreateProject(false)}
          />
        ) : showSettings ? (
          <div className="layout__settings-overlay">
            <SettingsPanel onClose={() => setShowSettings(false)} />
          </div>
        ) : null}
        {!showCreateProject && !showSettings && (
          <OpenFilesProvider>
            <div className="layout__main" ref={mainRef}>
              {/* Sidebar */}
              <div className="layout__sidebar">
                <div className="layout__sidebar-tabs">
                  <Tooltip text="Файлы проекта" side="right">
                    <button
                      type="button"
                      className={`layout__sidebar-tab ${sidebarTab === 'files' ? 'layout__sidebar-tab--active' : ''}`}
                      onClick={() => setSidebarTab('files')}
                      aria-label="Файлы проекта"
                    >
                      <FolderTree size={18} />
                    </button>
                  </Tooltip>
                  <Tooltip text="Git: статус и коммиты" side="right">
                    <button
                      type="button"
                      className={`layout__sidebar-tab ${sidebarTab === 'git' ? 'layout__sidebar-tab--active' : ''}`}
                      onClick={() => setSidebarTab('git')}
                      aria-label="Git"
                    >
                      <GitBranch size={18} />
                    </button>
                  </Tooltip>
                  <Tooltip text="RAG: индекс и поиск по коду" side="right">
                    <button
                      type="button"
                      className={`layout__sidebar-tab ${sidebarTab === 'projects' ? 'layout__sidebar-tab--active' : ''}`}
                      onClick={() => setSidebarTab('projects')}
                      aria-label="RAG индекс"
                    >
                      <Database size={18} />
                    </button>
                  </Tooltip>
                </div>
                <div className="layout__sidebar-content">
                  {sidebarTab === 'files' && (
                    <FileBrowser
                      onFileSelect={handleFileSelect}
                      gitStatus={fileStatusMap()}
                      onOpenFolder={() => setShowFolderPicker(true)}
                    />
                  )}
                  {sidebarTab === 'git' && <GitPanel onFileClick={handleFileSelect} />}
                  {sidebarTab === 'projects' && <ProjectSelector />}
                </div>
              </div>

              {/* Editor + Terminal */}
              <div className="layout__editor-main">
                <div className="layout__editor-area">
                  <MultiFileEditor externalOpenFile={selectedFile} />
                </div>
                <div className={`layout__terminal ${terminalCollapsed ? 'layout__terminal--collapsed' : ''}`}>
                  <TerminalPanel
                    collapsed={terminalCollapsed}
                    onToggle={() => setTerminalCollapsed(!terminalCollapsed)}
                  />
                </div>
              </div>

              {/* Resizer — only when chat expanded */}
              {!chatPanelCollapsed && (
                <div
                  className={`layout__chat-resizer ${resizing ? 'layout__chat-resizer--active' : ''}`}
                  onMouseDown={handleResizeStart}
                  title="Тянуть для изменения ширины чата"
                />
              )}
              {/* Chat — full panel or collapsed strip */}
              {chatPanelCollapsed ? (
                <div
                  className="layout__chat-panel layout__chat-panel--collapsed"
                  style={{ width: CHAT_STRIP_WIDTH, minWidth: CHAT_STRIP_WIDTH, maxWidth: CHAT_STRIP_WIDTH }}
                >
                  <Tooltip text="Открыть чат" side="left">
                    <button
                      type="button"
                      className="layout__chat-strip-btn"
                      onClick={() => setChatPanelCollapsed(false)}
                      aria-label="Открыть чат"
                    >
                      <MessageSquare size={20} />
                    </button>
                  </Tooltip>
                </div>
              ) : (
                <div
                  className="layout__chat-panel"
                  style={{ width: chatPanelWidth, minWidth: MIN_CHAT_WIDTH, maxWidth: MAX_CHAT_WIDTH }}
                >
                  <ChatPanel hasEditorContext onCollapse={() => setChatPanelCollapsed(true)} />
                </div>
              )}
            </div>
          </OpenFilesProvider>
        )}
      </div>

      {showFolderPicker && (
        <FolderPicker
          onSelect={handleOpenFolder}
          onCancel={() => setShowFolderPicker(false)}
        />
      )}
    </div>
  )
}
