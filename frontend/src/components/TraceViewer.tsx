import { useState } from 'react';

interface TraceViewerProps {
  trace: string[];
  workflow: string;
}

export const TraceViewer = ({ trace, workflow }: TraceViewerProps) => {
  const [isOpen, setIsOpen] = useState(false);

  if (!trace || trace.length === 0) return null;

  return (
    <div className="mt-3 border border-slate-800 rounded-lg overflow-hidden bg-slate-950/60">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-3 py-2 text-xs font-medium text-slate-400 hover:text-slate-200 flex items-center justify-between bg-slate-900/60"
      >
        <div className="flex items-center space-x-2">
          <span>⚙️ Agent Graph Execution Trace</span>
          <span className="px-1.5 py-0.2 rounded text-[10px] bg-sky-950 text-sky-400 border border-sky-800 uppercase font-mono">
            {workflow}
          </span>
          <span className="text-[11px] text-slate-500">({trace.length} steps)</span>
        </div>
        <span>{isOpen ? '▲ Hide' : '▼ Inspect'}</span>
      </button>

      {isOpen && (
        <div className="p-3 space-y-1.5 font-mono text-[11px] border-t border-slate-800/80 bg-slate-950">
          {trace.map((step, idx) => (
            <div key={idx} className="flex items-start space-x-2 text-slate-300">
              <span className="text-slate-600 select-none">{String(idx + 1).padStart(2, '0')}.</span>
              <span className="text-sky-300/90">{step}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
