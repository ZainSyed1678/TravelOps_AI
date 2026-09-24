interface NavbarProps {
  activeTab: 'chat' | 'hitl' | 'diagnostics';
  setActiveTab: (tab: 'chat' | 'hitl' | 'diagnostics') => void;
  pendingCount: number;
}

export const Navbar = ({ activeTab, setActiveTab, pendingCount }: NavbarProps) => {
  return (
    <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <span className="text-2xl">✈️</span>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-lg font-bold text-sky-400">TravelOps AI</h1>
              <span className="text-xs px-2 py-0.5 rounded-full bg-sky-950 text-sky-400 border border-sky-800 font-mono">
                v0.1.0
              </span>
            </div>
            <p className="text-xs text-slate-400 hidden sm:block">
              Agentic Travel Operations & Intelligence Platform
            </p>
          </div>
        </div>

        <nav className="flex items-center space-x-1 sm:space-x-2">
          <button
            onClick={() => setActiveTab('chat')}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              activeTab === 'chat'
                ? 'bg-sky-600 text-white shadow-sm'
                : 'text-slate-300 hover:bg-slate-800 hover:text-white'
            }`}
          >
            🤖 AI Assistant
          </button>

          <button
            onClick={() => setActiveTab('hitl')}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors relative ${
              activeTab === 'hitl'
                ? 'bg-amber-600 text-white shadow-sm'
                : 'text-slate-300 hover:bg-slate-800 hover:text-white'
            }`}
          >
            🛡️ HITL Safety
            {pendingCount > 0 && (
              <span className="ml-1.5 px-1.5 py-0.2 rounded-full text-xs bg-red-500 text-white font-bold animate-pulse">
                {pendingCount}
              </span>
            )}
          </button>

          <button
            onClick={() => setActiveTab('diagnostics')}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              activeTab === 'diagnostics'
                ? 'bg-indigo-600 text-white shadow-sm'
                : 'text-slate-300 hover:bg-slate-800 hover:text-white'
            }`}
          >
            📊 Diagnostics
          </button>
        </nav>
      </div>
    </header>
  );
};
