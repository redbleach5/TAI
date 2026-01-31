import type { OpenFile } from './useOpenFiles'

interface EditorTabsProps {
  files: Map<string, OpenFile>
  activeFile: string | null
  onSelect: (path: string) => void
  onClose: (path: string) => void
}

export function EditorTabs({ files, activeFile, onSelect, onClose }: EditorTabsProps) {
  const fileList = Array.from(files.values())

  if (fileList.length === 0) {
    return null
  }

  const handleClose = (e: React.MouseEvent, path: string) => {
    e.preventDefault()
    e.stopPropagation()
    onClose(path)
  }

  const handleMiddleClick = (e: React.MouseEvent, path: string) => {
    if (e.button === 1) {  // Middle click
      e.preventDefault()
      onClose(path)
    }
  }

  return (
    <div className="editor-tabs">
      {fileList.map((file) => (
        <div
          key={file.path}
          className={`editor-tabs__tab ${activeFile === file.path ? 'editor-tabs__tab--active' : ''} ${file.isDirty ? 'editor-tabs__tab--dirty' : ''}`}
          onClick={() => onSelect(file.path)}
          onMouseDown={(e) => handleMiddleClick(e, file.path)}
          title={file.path}
        >
          <span className="editor-tabs__name">
            {file.name}
            {file.isDirty && <span className="editor-tabs__dirty-dot">●</span>}
          </span>
          <button
            type="button"
            className="editor-tabs__close"
            onClick={(e) => handleClose(e, file.path)}
            onMouseDown={(e) => e.stopPropagation()}
            title="Close"
          >
            ×
          </button>
        </div>
      ))}
    </div>
  )
}
