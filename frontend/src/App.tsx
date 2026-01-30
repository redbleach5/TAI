import { HealthStatus } from './features/health/HealthStatus'
import { WorkflowCodeProvider } from './features/ide/WorkflowCodeContext'
import { Layout } from './features/layout/Layout'
import { ToastProvider } from './features/toast/ToastContext'
import './App.css'

function App() {
  return (
    <ToastProvider>
      <div className="app">
        <header className="header">
          <h1>TAi</h1>
          <p className="tagline">Локальная генерация кода на ИИ — альтернатива Cursor</p>
          <HealthStatus />
        </header>
        <main className="main">
          <WorkflowCodeProvider>
            <Layout />
          </WorkflowCodeProvider>
        </main>
      </div>
    </ToastProvider>
  )
}

export default App
