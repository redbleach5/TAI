/**
 * Cursor-like layout: IDE + Chat always visible.
 * Sidebar | Editor | Chat — no tab switching.
 */
import { useState } from 'react'
import {
  Settings,
  FolderTree,
  GitBranch,
  Database,
  FolderOpen,
} from 'lucide-react'
import { ChatPanel } from '../chat/ChatPanel'
import { SettingsPanel } from '../settings/SettingsPanel'
import { FileBrowser } from '../files/FileBrowser'
import { ProjectSelector } from '../projects/ProjectSelector'
import { FolderPicker } from '../workspace/FolderPicker'
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
  const [showSettings, setShowSettings] = useState(false)
  const { fileStatusMap } = useGitStatus()
  const { show: showToast } = useToast()
  const { workspace, openFolder } = useWorkspace()

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
          className="layout__settings-btn"
          onClick={() => setShowSettings(!showSettings)}
          title="Настройки"
        >
          <Settings size={14} />
        </button>
      </div>

      <div className="layout__content">
        {showSettings ? (
          <div className="layout__settings-overlay">
            <SettingsPanel onClose={() => setShowSettings(false)} />
          </div>
        ) : (
          <OpenFilesProvider>
            <div className="layout__main">
              {/* Sidebar */}
              <div className="layout__sidebar">
                <div className="layout__sidebar-tabs">
                  <button
                    className={`layout__sidebar-tab ${sidebarTab === 'files' ? 'layout__sidebar-tab--active' : ''}`}
                    onClick={() => setSidebarTab('files')}
                    title="Файлы"
                  >
                    <FolderTree size={18} />
                  </button>
                  <button
                    className={`layout__sidebar-tab ${sidebarTab === 'git' ? 'layout__sidebar-tab--active' : ''}`}
                    onClick={() => setSidebarTab('git')}
                    title="Git"
                  >
                    <GitBranch size={18} />
                  </button>
                  <button
                    className={`layout__sidebar-tab ${sidebarTab === 'projects' ? 'layout__sidebar-tab--active' : ''}`}
                    onClick={() => setSidebarTab('projects')}
                    title="RAG индекс"
                  >
                    <Database size={18} />
                  </button>
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

              {/* Chat — Cursor-like, always visible */}
              <div className="layout__chat-panel">
                <ChatPanel hasEditorContext />
              </div>
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
