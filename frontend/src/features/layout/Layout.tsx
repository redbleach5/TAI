import { useState } from 'react'
import { ChatPanel } from '../chat/ChatPanel'
import { IDEPanel } from '../ide/IDEPanel'
import { ImprovementPanel } from '../improve/ImprovementPanel'
import { SettingsPanel } from '../settings/SettingsPanel'
import { WorkflowPanel } from '../workflow/WorkflowPanel'
import { FileBrowser } from '../files/FileBrowser'
import { MultiFileEditor } from '../editor/MultiFileEditor'
import { TerminalPanel } from '../terminal/TerminalPanel'
import { GitPanel } from '../git/GitPanel'
import { useGitStatus } from '../git/useGitStatus'

type LayoutMode = 'chat' | 'workflow' | 'ide' | 'editor' | 'split' | 'improve' | 'settings'
type SidebarTab = 'files' | 'git'

export function Layout() {
  const [mode, setMode] = useState<LayoutMode>('chat')
  const [sidebarTab, setSidebarTab] = useState<SidebarTab>('files')
  const [terminalCollapsed, setTerminalCollapsed] = useState(true)
  const [selectedFile, setSelectedFile] = useState<string | null>(null)
  const { fileStatusMap } = useGitStatus()

  const handleFileSelect = (path: string) => {
    setSelectedFile(path)
  }

  return (
    <div className={`layout layout--${mode}`}>
      <div className="layout__tabs">
        <button
          type="button"
          className={`layout__tab ${mode === 'chat' ? 'layout__tab--active' : ''}`}
          onClick={() => setMode('chat')}
        >
          Чат
        </button>
        <button
          type="button"
          className={`layout__tab ${mode === 'workflow' ? 'layout__tab--active' : ''}`}
          onClick={() => setMode('workflow')}
        >
          Workflow
        </button>
        <button
          type="button"
          className={`layout__tab ${mode === 'editor' ? 'layout__tab--active' : ''}`}
          onClick={() => setMode('editor')}
        >
          IDE
        </button>
        <button
          type="button"
          className={`layout__tab ${mode === 'ide' ? 'layout__tab--active' : ''}`}
          onClick={() => setMode('ide')}
        >
          Результат
        </button>
        <button
          type="button"
          className={`layout__tab ${mode === 'split' ? 'layout__tab--active' : ''}`}
          onClick={() => setMode('split')}
        >
          Раздельно
        </button>
        <button
          type="button"
          className={`layout__tab ${mode === 'improve' ? 'layout__tab--active' : ''}`}
          onClick={() => setMode('improve')}
        >
          Улучшение
        </button>
        <button
          type="button"
          className={`layout__tab ${mode === 'settings' ? 'layout__tab--active' : ''}`}
          onClick={() => setMode('settings')}
        >
          Настройки
        </button>
      </div>

      <div className="layout__content">
        {/* Chat Mode */}
        {(mode === 'chat' || mode === 'split') && (
          <div className="layout__chat">
            <ChatPanel />
          </div>
        )}

        {/* Workflow Mode */}
        {mode === 'workflow' && (
          <div className="layout__workflow">
            <WorkflowPanel />
          </div>
        )}

        {/* Full IDE Mode with sidebar, editor, terminal */}
        {mode === 'editor' && (
          <div className="layout__full-editor">
            {/* Sidebar */}
            <div className="layout__sidebar">
              <div className="layout__sidebar-tabs">
                <button
                  className={`layout__sidebar-tab ${sidebarTab === 'files' ? 'layout__sidebar-tab--active' : ''}`}
                  onClick={() => setSidebarTab('files')}
                  title="Files"
                >
                  📁
                </button>
                <button
                  className={`layout__sidebar-tab ${sidebarTab === 'git' ? 'layout__sidebar-tab--active' : ''}`}
                  onClick={() => setSidebarTab('git')}
                  title="Source Control"
                >
                  🔀
                </button>
              </div>
              <div className="layout__sidebar-content">
                {sidebarTab === 'files' && (
                  <FileBrowser
                    onFileSelect={handleFileSelect}
                    gitStatus={fileStatusMap()}
                  />
                )}
                {sidebarTab === 'git' && (
                  <GitPanel onFileClick={handleFileSelect} />
                )}
              </div>
            </div>

            {/* Main editor area */}
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
          </div>
        )}

        {/* Improvement Mode */}
        {mode === 'improve' && (
          <div className="layout__improve">
            <ImprovementPanel />
          </div>
        )}

        {/* Settings Mode */}
        {mode === 'settings' && (
          <div className="layout__settings">
            <SettingsPanel />
          </div>
        )}

        {/* Old IDE for workflow results */}
        {(mode === 'ide' || mode === 'split') && (
          <div className="layout__ide">
            <IDEPanel />
          </div>
        )}
      </div>
    </div>
  )
}
