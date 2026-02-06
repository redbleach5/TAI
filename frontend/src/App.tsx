import { Sparkles } from 'lucide-react'
import { HealthStatus } from './features/health/HealthStatus'
import { Layout } from './features/layout/Layout'
import { ToastProvider } from './features/toast/ToastContext'
import { ErrorBoundary } from './features/ui/ErrorBoundary'
import './App.css'

function App() {
  return (
    <ErrorBoundary>
      <ToastProvider>
        <div className="app">
          <header className="header">
            <div className="header__left">
              <div className="header__logo">
                <Sparkles className="header__logo-icon" size={20} />
                <h1 className="header__title">TAi</h1>
              </div>
              <span className="tagline">AI Code Assistant</span>
            </div>
            <HealthStatus />
          </header>
          <main className="main">
            <ErrorBoundary>
              <Layout />
            </ErrorBoundary>
          </main>
        </div>
      </ToastProvider>
    </ErrorBoundary>
  )
}

export default App
