import { useState, useEffect } from 'react';
import { PendingAction } from '../types/travel';
import { HITLModal } from './HITLModal';

interface AuditLog {
  entry_id: string;
  action_id: string;
  action_type: string;
  status: string;
  operator_id: string;
  notes?: string;
  timestamp: string;
}

export const HITLQueueView = () => {
  const [pendingActions, setPendingActions] = useState<PendingAction[]>([]);
  const [auditTrail, setAuditTrail] = useState<AuditLog[]>([]);
  const [selectedAction, setSelectedAction] = useState<PendingAction | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [pendingRes, auditRes] = await Promise.all([
        fetch('/api/v1/agents/hitl/pending').then((r) => r.json()).catch(() => []),
        fetch('/api/v1/agents/hitl/audit/trail').then((r) => r.json()).catch(() => []),
      ]);
      setPendingActions(Array.isArray(pendingRes) ? pendingRes : []);
      setAuditTrail(Array.isArray(auditRes) ? auditRes : []);
    } catch {
      // Ignored
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between pb-4 border-b border-slate-800">
        <div>
          <h2 className="text-xl font-bold text-white">Human-in-the-Loop Safety Queue</h2>
          <p className="text-xs text-slate-400">
            Mandatory authorization barrier for high-risk mutations, flight rebookings, and financial charges
          </p>
        </div>

        <button
          onClick={fetchData}
          className="px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-amber-600 hover:bg-amber-500 text-white transition-colors"
        >
          {loading ? 'Refreshing...' : '🔄 Refresh Queue'}
        </button>
      </div>

      {/* Pending Actions */}
      <div className="space-y-3">
        <h3 className="text-sm font-semibold text-slate-300 flex items-center space-x-2">
          <span>Pending Confirmation Proposals</span>
          <span className="px-2 py-0.2 rounded-full text-xs bg-amber-950 text-amber-300 border border-amber-800 font-bold">
            {pendingActions.length}
          </span>
        </h3>

        {pendingActions.length === 0 ? (
          <div className="p-8 text-center bg-slate-900 border border-slate-800 rounded-xl">
            <span className="text-3xl block mb-2">✅</span>
            <div className="text-sm font-semibold text-slate-300">Safety Queue Clear</div>
            <p className="text-xs text-slate-500 mt-1">
              No pending high-risk actions awaiting human authorization.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {pendingActions.map((action) => (
              <div
                key={action.action_id}
                className="bg-slate-900 border border-amber-600/40 p-5 rounded-xl space-y-3 shadow-lg shadow-amber-950/20"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono font-bold text-sky-400">
                    {action.action_id}
                  </span>
                  <span
                    className={`text-[11px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider ${
                      action.risk_level === 'CRITICAL'
                        ? 'bg-red-500/20 text-red-300 border border-red-500/40 animate-pulse'
                        : 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                    }`}
                  >
                    {action.risk_level}
                  </span>
                </div>

                <div>
                  <div className="text-sm font-semibold text-white">{action.action_type}</div>
                  <p className="text-xs text-slate-300 mt-1">{action.description}</p>
                </div>

                <div className="flex items-center justify-between pt-2 border-t border-slate-800">
                  <span className="text-[10px] text-slate-500">
                    {new Date(action.created_at).toLocaleString()}
                  </span>
                  <button
                    onClick={() => setSelectedAction(action)}
                    className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-amber-600 hover:bg-amber-500 text-white transition-colors"
                  >
                    Authorize / Reject
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Historical Audit Trail */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-3">
        <h3 className="text-base font-bold text-white">Immutable Safety Audit Trail</h3>
        <p className="text-xs text-slate-400">
          Cryptographically auditable log of operator confirmations and rejections
        </p>

        {auditTrail.length === 0 ? (
          <div className="text-xs text-slate-500 py-4 text-center">No audit entries recorded yet.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400">
                  <th className="py-2">Time</th>
                  <th className="py-2">Action ID</th>
                  <th className="py-2">Type</th>
                  <th className="py-2">Decision</th>
                  <th className="py-2">Operator</th>
                  <th className="py-2">Notes</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {auditTrail.map((entry) => (
                  <tr key={entry.entry_id} className="text-slate-300">
                    <td className="py-2 text-slate-500">{new Date(entry.timestamp).toLocaleTimeString()}</td>
                    <td className="py-2 text-sky-400">{entry.action_id}</td>
                    <td className="py-2">{entry.action_type}</td>
                    <td className="py-2">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          entry.status === 'APPROVED' || entry.status === 'EXECUTED'
                            ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                            : 'bg-red-950 text-red-300 border border-red-800'
                        }`}
                      >
                        {entry.status}
                      </span>
                    </td>
                    <td className="py-2 text-slate-400">{entry.operator_id}</td>
                    <td className="py-2 text-slate-400 truncate max-w-xs">{entry.notes || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {selectedAction && (
        <HITLModal
          action={selectedAction}
          onClose={() => setSelectedAction(null)}
          onActionComplete={() => {
            fetchData();
          }}
        />
      )}
    </div>
  );
};
