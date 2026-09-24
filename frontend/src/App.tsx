import { useState, useEffect } from 'react';
import { Navbar } from './components/Navbar';
import { ChatConsole } from './components/ChatConsole';
import { HITLQueueView } from './components/HITLQueueView';
import { DiagnosticsView } from './components/DiagnosticsView';

export default function App() {
  const [activeTab, setActiveTab] = useState<'chat' | 'hitl' | 'diagnostics'>('chat');
  const [pendingCount, setPendingCount] = useState(0);

  const checkPendingActions = async () => {
    try {
      const res = await fetch('/api/v1/agents/hitl/pending');
      if (res.ok) {
        const data = await res.json();
        setPendingCount(Array.isArray(data) ? data.length : 0);
      }
    } catch {
      // Backend not yet reachable
    }
  };

  useEffect(() => {
    checkPendingActions();
    const interval = setInterval(checkPendingActions, 8000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-sky-500 selection:text-white">
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        pendingCount={pendingCount}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 lg:p-8">
        {activeTab === 'chat' && <ChatConsole />}
        {activeTab === 'hitl' && <HITLQueueView />}
        {activeTab === 'diagnostics' && <DiagnosticsView />}
      </main>
    </div>
  );
}
