import { useState } from 'react';
import { PendingAction } from '../types/travel';

interface HITLModalProps {
  action: PendingAction;
  onClose: () => void;
  onActionComplete: (updatedAction: any) => void;
}

export const HITLModal = ({ action, onClose, onActionComplete }: HITLModalProps) => {
  const [operatorId, setOperatorId] = useState('ops_agent_console');
  const [notes, setNotes] = useState('');
  const [rejectionReason, setRejectionReason] = useState('');
  const [isRejecting, setIsRejecting] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleConfirm = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch(`/api/v1/agents/hitl/actions/${action.action_id}/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          operator_id: operatorId,
          notes: notes || 'Confirmed by operations operator via console',
          waiver_override: false,
        }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to authorize action');
      }

      const result = await res.json();
      onActionComplete(result);
      onClose();
    } catch (err: any) {
      setError(err.message || 'Confirmation failed');
    } finally {
      setSubmitting(false);
    }
  };

  const handleReject = async () => {
    if (!rejectionReason.trim()) {
      setError('Please provide a reason for rejecting this proposal.');
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch(`/api/v1/agents/hitl/actions/${action.action_id}/reject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          operator_id: operatorId,
          reason: rejectionReason,
        }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to reject action');
      }

      const result = await res.json();
      onActionComplete(result);
      onClose();
    } catch (err: any) {
      setError(err.message || 'Rejection failed');
    } finally {
      setSubmitting(false);
    }
  };

  const isCritical = action.risk_level === 'CRITICAL';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fadeIn">
      <div className="bg-slate-900 border border-slate-700 rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-slate-800">
          <div className="flex items-center space-x-2">
            <span className="text-xl">⚠️</span>
            <h3 className="text-lg font-bold text-white">Human-in-the-Loop Safety Checkpoint</h3>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-white text-lg">
            ✕
          </button>
        </div>

        <div className="flex items-center justify-between bg-slate-950 p-3 rounded-lg border border-slate-800">
          <div>
            <div className="text-xs text-slate-400">Action ID: {action.action_id}</div>
            <div className="text-sm font-semibold text-sky-400">{action.action_type}</div>
          </div>
          <span
            className={`text-xs font-bold px-2.5 py-1 rounded-full uppercase tracking-wider ${
              isCritical
                ? 'bg-red-500/20 text-red-300 border border-red-500/40 animate-pulse'
                : 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
            }`}
          >
            {action.risk_level} Risk
          </span>
        </div>

        <div className="text-sm text-slate-300 bg-slate-950/60 p-3.5 rounded-lg border border-slate-800/80">
          <p className="font-medium text-slate-200">{action.description}</p>
          {action.parameters && Object.keys(action.parameters).length > 0 && (
            <div className="mt-3 pt-2 border-t border-slate-800 text-xs font-mono space-y-1 text-slate-400">
              {Object.entries(action.parameters).map(([k, v]) => (
                <div key={k} className="flex justify-between">
                  <span className="text-slate-500">{k}:</span>
                  <span className="text-slate-200 font-semibold">{String(v)}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {error && (
          <div className="p-3 rounded-lg bg-red-950/80 border border-red-800 text-xs text-red-300">
            {error}
          </div>
        )}

        <div className="space-y-3 pt-2">
          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1">
              Operator Identifier
            </label>
            <input
              type="text"
              value={operatorId}
              onChange={(e) => setOperatorId(e.target.value)}
              className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-white focus:outline-none focus:border-sky-500 font-mono"
            />
          </div>

          {!isRejecting ? (
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1">
                Authorization Notes (Optional)
              </label>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="e.g. Passenger verbally confirmed new itinerary."
                rows={2}
                className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-white focus:outline-none focus:border-sky-500"
              />
            </div>
          ) : (
            <div>
              <label className="block text-xs font-medium text-red-400 mb-1">
                Rejection Rationale (Required)
              </label>
              <textarea
                value={rejectionReason}
                onChange={(e) => setRejectionReason(e.target.value)}
                placeholder="State reason for rejecting proposed itinerary mutation."
                rows={2}
                className="w-full px-3 py-2 bg-slate-950 border border-red-900 rounded-lg text-xs text-white focus:outline-none focus:border-red-500"
              />
            </div>
          )}
        </div>

        <div className="flex items-center justify-between pt-3 border-t border-slate-800">
          <button
            onClick={() => setIsRejecting(!isRejecting)}
            className="text-xs text-slate-400 hover:text-slate-200 underline"
          >
            {isRejecting ? '← Back to Authorization' : 'Switch to Reject Proposal'}
          </button>

          <div className="flex space-x-2">
            <button
              onClick={onClose}
              className="px-3.5 py-2 rounded-lg text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors"
            >
              Cancel
            </button>

            {!isRejecting ? (
              <button
                onClick={handleConfirm}
                disabled={submitting}
                className="px-4 py-2 rounded-lg text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white transition-colors disabled:opacity-50 flex items-center space-x-1"
              >
                {submitting ? 'Executing...' : '✓ Approve & Execute'}
              </button>
            ) : (
              <button
                onClick={handleReject}
                disabled={submitting}
                className="px-4 py-2 rounded-lg text-xs font-semibold bg-red-600 hover:bg-red-500 text-white transition-colors disabled:opacity-50"
              >
                {submitting ? 'Rejecting...' : '✗ Confirm Rejection'}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
