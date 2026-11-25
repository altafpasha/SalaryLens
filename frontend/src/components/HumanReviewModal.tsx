import React, { useState } from 'react';
import { X, CheckCircle2, XCircle, Edit3, Loader2, AlertCircle } from 'lucide-react';
import { api } from '../api';
import { StatementItem, StatementResults } from '../types';

interface HumanReviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  statement: StatementItem;
  results: StatementResults | null;
  onReviewSubmitted: () => void;
}

export const HumanReviewModal: React.FC<HumanReviewModalProps> = ({
  isOpen,
  onClose,
  statement,
  results,
  onReviewSubmitted,
}) => {
  const [decision, setDecision] = useState<'approved' | 'rejected' | 'adjusted'>('approved');
  const [confirmedEmployer, setConfirmedEmployer] = useState<string>(
    results?.detected_employer || ''
  );
  const [notes, setNotes] = useState<string>('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      await api.submitReview(statement.statement_id, {
        status: decision,
        confirmed_employer: decision !== 'rejected' ? confirmedEmployer : undefined,
        confirmed_transaction_ids: results?.supporting_transaction_ids || [],
        review_notes: notes || undefined,
      });
      onReviewSubmitted();
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to submit review');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-in fade-in duration-200">
      <div className="bg-[#141414]/95 border border-white/[0.1] rounded-3xl w-full max-w-lg shadow-[0_20px_50px_rgba(0,0,0,0.6)] overflow-hidden">
        {/* Header */}
        <div className="px-6 py-5 border-b border-white/[0.06] flex items-center justify-between">
          <div>
            <h3 className="text-base font-bold text-white tracking-tight">Manual Human Review Audit</h3>
            <p className="text-xs text-text-muted">{statement.filename}</p>
          </div>
          <button
            onClick={onClose}
            disabled={submitting}
            className="h-8 w-8 rounded-full bg-white/[0.04] hover:bg-white/[0.08] text-text-muted hover:text-white flex items-center justify-center border border-white/[0.08] transition"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Content */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {error && (
            <div className="p-3 rounded-2xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-center gap-2">
              <AlertCircle className="h-4 w-4 shrink-0 text-rose-400" />
              <span>{error}</span>
            </div>
          )}

          {/* Decision Selection Pills */}
          <div className="grid grid-cols-3 gap-2.5">
            <button
              type="button"
              onClick={() => setDecision('approved')}
              className={`p-3.5 rounded-2xl border text-center transition flex flex-col items-center gap-2 ${
                decision === 'approved'
                  ? 'border-emerald-500 bg-emerald-500/15 text-emerald-300 font-semibold shadow-[0_0_15px_rgba(34,197,94,0.15)]'
                  : 'border-white/[0.08] bg-white/[0.02] text-text-muted hover:border-white/20'
              }`}
            >
              <CheckCircle2 className="h-4 w-4" />
              <span className="text-xs">Approve Salary</span>
            </button>

            <button
              type="button"
              onClick={() => setDecision('adjusted')}
              className={`p-3.5 rounded-2xl border text-center transition flex flex-col items-center gap-2 ${
                decision === 'adjusted'
                  ? 'border-[#8B7CFF] bg-[#8B7CFF]/15 text-[#8B7CFF] font-semibold shadow-[0_0_15px_rgba(139,124,255,0.15)]'
                  : 'border-white/[0.08] bg-white/[0.02] text-text-muted hover:border-white/20'
              }`}
            >
              <Edit3 className="h-4 w-4" />
              <span className="text-xs">Override / Adjust</span>
            </button>

            <button
              type="button"
              onClick={() => setDecision('rejected')}
              className={`p-3.5 rounded-2xl border text-center transition flex flex-col items-center gap-2 ${
                decision === 'rejected'
                  ? 'border-rose-500 bg-rose-500/15 text-rose-300 font-semibold shadow-[0_0_15px_rgba(239,68,68,0.15)]'
                  : 'border-white/[0.08] bg-white/[0.02] text-text-muted hover:border-white/20'
              }`}
            >
              <XCircle className="h-4 w-4" />
              <span className="text-xs">Reject Stream</span>
            </button>
          </div>

          {/* Confirmed Employer Input */}
          {decision !== 'rejected' && (
            <div>
              <label className="block text-xs font-medium text-text-secondary mb-1.5">
                Confirmed Employer Name
              </label>
              <input
                type="text"
                value={confirmedEmployer}
                onChange={(e) => setConfirmedEmployer(e.target.value)}
                placeholder="e.g. Acme Corporation"
                className="w-full px-4 py-2.5 bg-[#161616] border border-white/[0.08] rounded-xl text-xs text-text-primary focus:outline-none focus:border-[#F15A43]/50 focus:shadow-[0_0_15px_rgba(241,90,67,0.15)] transition"
                required
              />
            </div>
          )}

          {/* Notes */}
          <div>
            <label className="block text-xs font-medium text-text-secondary mb-1.5">
              Reviewer Audit Notes / Justification
            </label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Provide reason for decision (recorded in audit trail and finalized Excel workbook)..."
              rows={3}
              className="w-full px-4 py-2.5 bg-[#161616] border border-white/[0.08] rounded-xl text-xs text-text-primary focus:outline-none focus:border-[#F15A43]/50 focus:shadow-[0_0_15px_rgba(241,90,67,0.15)] transition resize-none"
            />
          </div>

          {/* Actions */}
          <div className="pt-2 flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              disabled={submitting}
              className="px-5 py-2.5 rounded-full text-xs font-medium text-text-secondary hover:text-white hover:bg-white/[0.04] transition"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="inline-flex items-center gap-2 px-6 py-2.5 rounded-full bg-gradient-to-r from-[#F15A43] to-[#e04832] text-xs font-semibold text-white shadow-glow-accent transition active:scale-95"
            >
              {submitting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>Submitting...</span>
                </>
              ) : (
                <span>Confirm & Sign Audit</span>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
