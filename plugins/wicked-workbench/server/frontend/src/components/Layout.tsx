import { useState } from 'react'
import { PluginNav } from './PluginNav'
import { PluginView } from './PluginView'
import { ChatPanel } from './ChatPanel'

export function Layout() {
  const [chatOpen, setChatOpen] = useState(true)

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[var(--bg-primary)]">
      {/* Sidebar - Plugin Navigation */}
      <aside className="w-56 flex-shrink-0 border-r border-[var(--border)] bg-[var(--bg-secondary)]">
        <PluginNav />
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col min-w-0">
        <PluginView />
      </main>

      {/* Chat Panel (collapsible) */}
      <div className={`flex-shrink-0 border-l border-[var(--border)] transition-all duration-300 ${
        chatOpen ? 'w-96' : 'w-0'
      }`}>
        {chatOpen && <ChatPanel />}
      </div>

      {/* Chat toggle button */}
      <button
        onClick={() => setChatOpen(!chatOpen)}
        className="fixed bottom-4 right-4 z-50 w-10 h-10 rounded-full bg-violet-600 text-white flex items-center justify-center shadow-lg hover:bg-violet-500 transition-colors"
        title={chatOpen ? 'Close chat' : 'Open chat'}
      >
        {chatOpen ? '\u00d7' : '\ud83d\udcac'}
      </button>
    </div>
  )
}
