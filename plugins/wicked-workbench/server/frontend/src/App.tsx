import { usePlugins } from './hooks/usePlugins'
import { Layout } from './components/Layout'

function App() {
  const { loading, error } = usePlugins()

  if (loading) {
    return (
      <div className="h-screen w-screen flex items-center justify-center bg-[var(--bg-primary)]">
        <div className="text-center">
          <div className="flex gap-1 justify-center mb-4">
            <span className="w-2 h-2 rounded-full bg-violet-400 streaming-dot" style={{ animationDelay: '0s' }} />
            <span className="w-2 h-2 rounded-full bg-violet-400 streaming-dot" style={{ animationDelay: '0.2s' }} />
            <span className="w-2 h-2 rounded-full bg-violet-400 streaming-dot" style={{ animationDelay: '0.4s' }} />
          </div>
          <p className="text-sm text-[var(--text-muted)]">Discovering plugins...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="h-screen w-screen flex items-center justify-center bg-[var(--bg-primary)]">
        <div className="text-center max-w-md">
          <h2 className="text-lg font-bold text-red-400 mb-2">Connection Error</h2>
          <p className="text-sm text-[var(--text-muted)] mb-4">{error}</p>
          <p className="text-xs text-[var(--text-muted)]">
            Make sure the workbench server is running on port 18889.
          </p>
        </div>
      </div>
    )
  }

  return <Layout />
}

export default App
