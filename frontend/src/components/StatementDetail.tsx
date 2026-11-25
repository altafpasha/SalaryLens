import React, { useState, useEffect } from 'react';
import {
  ArrowLeft,
  FileSpreadsheet,
  RefreshCw,
  UserCheck,
  CheckCircle2,
  AlertTriangle,
  HelpCircle,
  XCircle,
  FileText,
  Calendar,
  TrendingUp,
  Cpu,
  Filter,
  Layers,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  ChevronUp,
  ShieldAlert,
  ShieldCheck,
  Download,
  Building,
  Activity,
  Zap,
  Info,
  Check,
  Clock,
  Sparkles,
  Trash2,
  Loader2,
  Terminal,
} from 'lucide-react';
import { api } from '../api';
import {
  StatementItem,
  StatementResults,
  PaginatedTransactions,
  StatementTransaction,
  CandidateGroup,
  PipelineLogEntry,
} from '../types';

interface StatementDetailProps {
  statement: StatementItem;
  onBack: () => void;
  onDownloadWorkbook: (statement: StatementItem) => void;
  onOpenReview: () => void;
  onDeleteStatement?: (statement: StatementItem) => Promise<void>;
  onStatementUpdated?: (statementId: string) => void;
}

// Indian Rupee Currency Formatter
const formatINR = (val?: number | string | null, includeDecimals = false): string => {
  if (val === undefined || val === null || val === '') return '—';
  const num = typeof val === 'number' ? val : parseFloat(val);
  if (isNaN(num)) return '—';
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: includeDecimals ? 2 : 0,
    minimumFractionDigits: includeDecimals ? 2 : 0,
  }).format(num);
};

// Convert AI cost to INR (using 1 USD = 86.0 INR)
const formatAICostINR = (val?: number | string | null): string => {
  if (val === undefined || val === null || val === '') return '₹ 0.00';
  const num = typeof val === 'number' ? val : parseFloat(val);
  if (isNaN(num)) return '₹ 0.00';
  const inrVal = num * 86.0;
  return `₹ ${inrVal.toFixed(2)}`;
};

export const StatementDetail: React.FC<StatementDetailProps> = ({
  statement,
  onBack,
  onDownloadWorkbook,
  onOpenReview,
  onDeleteStatement,
  onStatementUpdated,
}) => {
  const [results, setResults] = useState<StatementResults | null>(null);
  const [loadingResults, setLoadingResults] = useState(true);
  const [resultsError, setResultsError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);

  // Pipeline execution logs (How It Works)
  const [pipelineLogs, setPipelineLogs] = useState<PipelineLogEntry[]>([]);
  const [showLogs, setShowLogs] = useState(false);
  const [loadingLogs, setLoadingLogs] = useState(false);

  // Deletion state
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  // Expanded states for candidate cards and technical diagnostics
  const [expandedCandidates, setExpandedCandidates] = useState<Set<number>>(new Set());
  const [showDiagnostics, setShowDiagnostics] = useState(false);

  // Transactions state
  const [txData, setTxData] = useState<PaginatedTransactions | null>(null);
  const [txPage, setTxPage] = useState(1);
  const [filterIncluded, setFilterIncluded] = useState<boolean | undefined>(undefined);
  const [loadingTx, setLoadingTx] = useState(false);

  // Toggle single candidate card details
  const toggleCandidateExpand = (idx: number) => {
    setExpandedCandidates((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) {
        next.delete(idx);
      } else {
        next.add(idx);
      }
      return next;
    });
  };

  // Fetch results
  const fetchResults = async () => {
    try {
      setLoadingResults(true);
      const res = await api.getStatementResults(statement.statement_id);
      setResults(res);
      setResultsError(null);
    } catch (err: any) {
      setResultsError(err.message || 'Analysis results pending or in progress.');
    } finally {
      setLoadingResults(false);
    }
  };

  const fetchTransactions = async (page: number, includedOnly?: boolean) => {
    try {
      setLoadingTx(true);
      const data = await api.getStatementTransactions(statement.statement_id, page, 50, includedOnly);
      setTxData(data);
    } catch {
      // ignore
    } finally {
      setLoadingTx(false);
    }
  };

  const fetchLogs = async () => {
    try {
      setLoadingLogs(true);
      const data = await api.getStatementLogs(statement.statement_id);
      if (data && data.logs) {
        setPipelineLogs(data.logs);
      }
    } catch {
      // ignore
    } finally {
      setLoadingLogs(false);
    }
  };

  const handleDownload = async () => {
    try {
      setDownloading(true);
      await onDownloadWorkbook(statement);
    } finally {
      setDownloading(false);
    }
  };

  const handleDelete = async () => {
    if (!onDeleteStatement) return;
    try {
      setDeleting(true);
      await onDeleteStatement(statement);
    } finally {
      setDeleting(false);
      setConfirmDelete(false);
    }
  };

  // Initial load
  useEffect(() => {
    fetchResults();
    fetchLogs();
  }, [statement.statement_id, statement.status]);

  useEffect(() => {
    fetchTransactions(txPage, filterIncluded);
  }, [statement.statement_id, txPage, filterIncluded]);

  // Real-time active polling while processing or until results are available
  useEffect(() => {
    const isProcessing = statement.status === 'processing' || !results || results.status === 'processing';
    if (!isProcessing) return;

    const interval = setInterval(async () => {
      try {
        const res = await api.getStatementResults(statement.statement_id);
        if (res) {
          setResults(res);
          setResultsError(null);
          fetchTransactions(txPage, filterIncluded);
          fetchLogs();
          if (onStatementUpdated) {
            onStatementUpdated(statement.statement_id);
          }
        }
      } catch {
        // Still processing, poll logs to show progress
        fetchLogs();
      }
    }, 2500);

    return () => clearInterval(interval);
  }, [statement.statement_id, statement.status, !results, txPage, filterIncluded]);

  // Primary Candidate Group
  const primaryGroup = results?.candidate_groups?.find((g) => g.is_primary) || results?.candidate_groups?.[0];

  // Competing Candidate Groups
  const competingGroups = results?.candidate_groups?.filter((g) => g !== primaryGroup) || [];

  // Estimated Monthly Salary
  const monthlySalary = results?.estimated_monthly_salary ?? primaryGroup?.average_amount ?? 0;

  // Confidence Score
  const confidenceScore = results?.confidence_score ?? (primaryGroup ? Math.round(primaryGroup.recurrence_score * 100) : 50);

  // Decision outcome themes
  const getOutcomeTheme = (status?: string) => {
    switch (status) {
      case 'likely_salary':
        return {
          title: 'Salary Identified',
          badgeText: 'Verified Outcome',
          borderColor: 'border-emerald-500/30',
          textColor: 'text-emerald-400',
          bgColor: 'bg-emerald-500/10',
          glowClass: 'shadow-[0_0_30px_rgba(34,197,94,0.15)]',
          icon: CheckCircle2,
          confidenceColor: 'bg-emerald-500',
        };
      case 'possible_salary':
        return {
          title: 'Likely Salary',
          badgeText: 'Probable Payroll',
          borderColor: 'border-[#8B7CFF]/30',
          textColor: 'text-[#8B7CFF]',
          bgColor: 'bg-[#8B7CFF]/10',
          glowClass: 'shadow-[0_0_30px_rgba(139,124,255,0.15)]',
          icon: HelpCircle,
          confidenceColor: 'bg-[#8B7CFF]',
        };
      case 'multiple_salary_candidates':
        return {
          title: 'Multiple Employers / Ambiguous Streams',
          badgeText: 'Manual Review Required',
          borderColor: 'border-amber-500/30',
          textColor: 'text-amber-400',
          bgColor: 'bg-amber-500/10',
          glowClass: 'shadow-[0_0_30px_rgba(245,158,11,0.15)]',
          icon: AlertTriangle,
          confidenceColor: 'bg-amber-500',
        };
      case 'conflicting_evidence':
        return {
          title: 'Conflicting Evidence',
          badgeText: 'Manual Review Required',
          borderColor: 'border-amber-500/30',
          textColor: 'text-amber-400',
          bgColor: 'bg-amber-500/10',
          glowClass: 'shadow-[0_0_30px_rgba(245,158,11,0.15)]',
          icon: AlertTriangle,
          confidenceColor: 'bg-amber-500',
        };
      case 'insufficient_evidence':
      case 'analysis_failed':
      default:
        return {
          title: 'Insufficient Salary Evidence',
          badgeText: 'No Salary Detected',
          borderColor: 'border-[#F15A43]/30',
          textColor: 'text-[#F15A43]',
          bgColor: 'bg-[#F15A43]/10',
          glowClass: 'shadow-[0_0_30px_rgba(241,90,67,0.15)]',
          icon: XCircle,
          confidenceColor: 'bg-[#F15A43]',
        };
    }
  };

  const theme = getOutcomeTheme(results?.status);
  const OutcomeIcon = theme.icon;

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Top Action Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-white/[0.06]">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="h-9 w-9 rounded-full bg-[#161616] border border-white/[0.08] hover:border-white/20 text-text-secondary hover:text-white flex items-center justify-center transition"
            title="Back to statements list"
          >
            <ArrowLeft className="h-4 w-4" />
          </button>
          <div>
            <h1 className="text-base font-bold text-white flex items-center gap-2">
              <span className="truncate max-w-md">{statement.filename}</span>
              {statement.is_scanned && (
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-300 border border-amber-500/25 font-semibold">
                  Scanned Document
                </span>
              )}
            </h1>
            <p className="text-xs text-text-muted">
              {statement.page_count} pages • Ingested {new Date(statement.created_at).toLocaleString()}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2.5 flex-wrap">
          <button
            onClick={() => {
              fetchResults();
              fetchTransactions(txPage, filterIncluded);
              fetchLogs();
            }}
            className="h-9 w-9 rounded-full bg-[#161616] border border-white/[0.08] hover:border-white/20 text-text-secondary hover:text-white flex items-center justify-center transition"
            title="Refresh analysis results & ledger"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loadingResults || loadingTx ? 'animate-spin text-[#F15A43]' : ''}`} />
          </button>

          <button
            onClick={() => {
              setShowLogs(!showLogs);
              if (!showLogs) fetchLogs();
            }}
            className={`inline-flex items-center gap-1.5 px-3.5 py-2 rounded-full text-xs font-semibold border transition ${
              showLogs
                ? 'bg-[#8B7CFF]/20 text-[#8B7CFF] border-[#8B7CFF]/40 shadow-[0_0_15px_rgba(139,124,255,0.2)]'
                : 'bg-white/[0.04] hover:bg-white/[0.08] text-text-secondary hover:text-white border-white/[0.08]'
            }`}
            title="View technical pipeline logs & explanation of how it works"
          >
            <Terminal className="h-3.5 w-3.5 text-[#8B7CFF]" />
            <span>How It Works</span>
            {pipelineLogs.length > 0 && (
              <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-white/10 text-white font-mono">
                {pipelineLogs.length}
              </span>
            )}
          </button>

          <button
            onClick={handleDownload}
            disabled={downloading || statement.status === 'processing'}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-full bg-emerald-500/15 hover:bg-emerald-500/25 text-emerald-300 disabled:opacity-40 disabled:cursor-not-allowed text-xs font-semibold border border-emerald-500/25 transition shadow-sm active:scale-95"
            title="Download authoritative 5-sheet financial workbook"
          >
            {downloading ? (
              <RefreshCw className="h-4 w-4 animate-spin text-emerald-300" />
            ) : (
              <FileSpreadsheet className="h-4 w-4" />
            )}
            <span>{downloading ? 'Generating Excel...' : 'Download 5-Sheet Excel'}</span>
          </button>

          <button
            onClick={onOpenReview}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-full bg-gradient-to-r from-[#F15A43] to-[#e04832] text-white text-xs font-semibold transition shadow-glow-accent active:scale-95"
          >
            <UserCheck className="h-4 w-4" />
            <span>Human Review Audit</span>
          </button>

          {onDeleteStatement && (
            <button
              onClick={() => setConfirmDelete(true)}
              disabled={deleting}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-full bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 hover:text-rose-300 text-xs font-semibold border border-rose-500/20 transition active:scale-95"
              title="Permanently delete statement"
            >
              {deleting ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Trash2 className="h-3.5 w-3.5" />
              )}
              <span>Delete</span>
            </button>
          )}
        </div>
      </div>

      {/* Inline Delete Confirmation */}
      {confirmDelete && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs animate-in fade-in">
          <div className="flex items-center gap-2 text-rose-300">
            <AlertTriangle className="h-4 w-4 text-rose-400 flex-shrink-0" />
            <span>
              Are you sure you want to permanently delete <strong>{statement.filename}</strong>? All {txData?.total_count ?? statement.total_transactions_count ?? ''} extracted transactions and Excel workbooks will be permanently removed.
            </span>
          </div>
          <div className="flex items-center gap-2 self-end sm:self-auto flex-shrink-0">
            <button
              onClick={() => setConfirmDelete(false)}
              disabled={deleting}
              className="px-3 py-1.5 rounded-lg bg-white/[0.06] hover:bg-white/[0.1] text-white font-medium transition"
            >
              Cancel
            </button>
            <button
              onClick={handleDelete}
              disabled={deleting}
              className="px-3 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-700 text-white font-semibold transition flex items-center gap-1.5 shadow-lg shadow-rose-900/30"
            >
              {deleting && <Loader2 className="h-3 w-3 animate-spin" />}
              <span>Yes, Delete Statement</span>
            </button>
          </div>
        </div>
      )}

      {/* PHASE 2.A — EXECUTIVE SUMMARY */}
      {results && (
        <div className="rounded-2xl glass-panel border border-white/[0.08] p-5 space-y-4 shadow-glass">
          <div className="flex items-center justify-between pb-3 border-b border-white/[0.06]">
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-[#F15A43]" />
              <h2 className="text-xs font-bold uppercase tracking-wider text-text-muted">
                Executive Salary Analysis Report
              </h2>
            </div>
            <div className="flex items-center gap-2 text-xs">
              <span className="text-text-muted">Currency:</span>
              <span className="px-2 py-0.5 rounded-full bg-white/[0.06] font-mono text-white text-[11px] font-bold">
                INR (₹)
              </span>
            </div>
          </div>

          {/* 4 Primary Executive Stat Blocks */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {/* 1. Identification Status */}
            <div className="p-3.5 rounded-xl bg-white/[0.02] border border-white/[0.05] space-y-1">
              <span className="text-[10px] text-text-muted uppercase font-semibold block">Salary Status</span>
              <div className="flex items-center gap-1.5">
                <span className={`text-sm font-bold ${theme.textColor}`}>
                  {theme.title}
                </span>
              </div>
              <p className="text-[11px] text-text-secondary truncate" title={results.detected_employer || 'None detected'}>
                {results.detected_employer || 'No canonical employer'}
              </p>
            </div>

            {/* 2. Monthly Salary */}
            <div className="p-3.5 rounded-xl bg-white/[0.02] border border-white/[0.05] space-y-1">
              <span className="text-[10px] text-text-muted uppercase font-semibold block">Identified Monthly Salary</span>
              <div className="text-sm font-bold text-white font-mono">
                {monthlySalary > 0 ? formatINR(monthlySalary) : '—'}
              </div>
              <p className="text-[11px] text-text-muted">
                Avg: {primaryGroup ? formatINR(primaryGroup.average_amount) : '—'}
              </p>
            </div>

            {/* 3. Credits & Months */}
            <div className="p-3.5 rounded-xl bg-white/[0.02] border border-white/[0.05] space-y-1">
              <span className="text-[10px] text-text-muted uppercase font-semibold block">Payroll Evidence</span>
              <div className="text-sm font-bold text-[#8B7CFF]">
                {primaryGroup?.transaction_count || results.supporting_transaction_ids.length} Credits
              </div>
              <p className="text-[11px] text-text-muted">
                Across {primaryGroup?.months_count || results.supporting_months.length} statement months
              </p>
            </div>

            {/* 4. Confidence Score */}
            <div className="p-3.5 rounded-xl bg-white/[0.02] border border-white/[0.05] space-y-1.5">
              <div className="flex items-center justify-between text-[10px] text-text-muted uppercase font-semibold">
                <span>Confidence</span>
                <span className={`font-bold ${theme.textColor}`}>{confidenceScore}%</span>
              </div>
              <div className="w-full bg-white/[0.08] rounded-full h-2 overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${theme.confidenceColor}`}
                  style={{ width: `${Math.min(100, Math.max(10, confidenceScore))}%` }}
                />
              </div>
              <p className="text-[10px] text-text-muted text-right">
                {confidenceScore >= 80 ? 'High Grounding' : confidenceScore >= 50 ? 'Moderate' : 'Low Evidence'}
              </p>
            </div>
          </div>

          {/* Sub-bar: Tokens, Cost, Review Status */}
          <div className="pt-2 flex flex-wrap items-center justify-between gap-3 text-xs text-text-secondary border-t border-white/[0.04]">
            <div className="flex items-center gap-4 flex-wrap text-[11px]">
              <div>
                <span className="text-text-muted mr-1.5">AI Spend:</span>
                <span className="font-semibold text-emerald-400">{formatAICostINR(results.total_ai_cost_usd)}</span>
              </div>
              <div className="h-3 w-[1px] bg-white/[0.08]" />
              <div>
                <span className="text-text-muted mr-1.5">Token Consumption:</span>
                <span className="font-semibold text-white">{results.total_tokens.toLocaleString()}</span>
              </div>
              <div className="h-3 w-[1px] bg-white/[0.08]" />
              <div>
                <span className="text-text-muted mr-1.5">Engine Mode:</span>
                <span className="font-semibold text-[#8B7CFF]">{results.is_demo ? 'Deterministic Grounding' : 'Live OpenRouter'}</span>
              </div>
            </div>

            <div>
              {results.requires_human_review ? (
                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-amber-500/15 text-amber-300 border border-amber-500/25">
                  <AlertTriangle className="h-3 w-3" />
                  Human Review Required
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/25">
                  <CheckCircle2 className="h-3 w-3" />
                  Automated Sign-Off Eligible
                </span>
              )}
            </div>
          </div>
        </div>
      )}

      {/* PHASE 2.B — FINAL AI DECISION CARD */}
      {loadingResults ? (
        <div className="p-8 rounded-2xl glass-panel text-center animate-pulse">
          <RefreshCw className="h-8 w-8 text-[#F15A43] animate-spin mx-auto mb-2" />
          <p className="text-xs text-text-secondary">Evaluating transaction graph with Jev Decision Engine...</p>
        </div>
      ) : results ? (
        <div className={`p-6 rounded-2xl glass-panel border ${theme.borderColor} ${theme.glowClass} space-y-5`}>
          <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
            <div className="flex items-start gap-4">
              <div className={`h-12 w-12 rounded-2xl bg-white/[0.04] border border-white/[0.08] flex items-center justify-center shrink-0 ${theme.textColor}`}>
                <OutcomeIcon className="h-6 w-6" />
              </div>
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-bold tracking-widest uppercase text-text-muted">
                    Final AI Decision
                  </span>
                  <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${theme.bgColor} ${theme.textColor} border ${theme.borderColor}`}>
                    {theme.badgeText}
                  </span>
                </div>
                <h2 className={`text-2xl font-black ${theme.textColor} tracking-tight`}>
                  {theme.title}
                </h2>
                {results.detected_employer && (
                  <div className="text-sm font-medium text-text-secondary flex items-center gap-2 pt-0.5">
                    <span>Recommended Employer:</span>
                    <span className="text-white font-bold px-2.5 py-0.5 rounded-lg bg-white/[0.06] border border-white/[0.1] text-xs">
                      {results.detected_employer}
                    </span>
                  </div>
                )}
              </div>
            </div>

            {/* Prominent Monthly Salary Amount Display */}
            {monthlySalary > 0 && (
              <div className="bg-[#141414] px-5 py-3.5 rounded-2xl border border-white/[0.08] text-right shrink-0">
                <span className="text-[10px] text-text-muted uppercase font-semibold block">
                  Estimated Monthly Salary
                </span>
                <div className="text-2xl font-black text-white font-mono tracking-tight mt-0.5">
                  {formatINR(monthlySalary)}
                </div>
                <span className="text-[10px] text-emerald-400 font-medium">
                  {primaryGroup?.transaction_count || results.supporting_transaction_ids.length} recurring deposits
                </span>
              </div>
            )}
          </div>

          {/* Decision Explanation */}
          <div className="p-4 rounded-xl bg-[#141414]/90 border border-white/[0.06] text-xs text-text-secondary leading-relaxed space-y-1.5">
            <div className="font-semibold text-white flex items-center gap-1.5">
              <Info className="h-3.5 w-3.5 text-[#F15A43]" />
              <span>Decision Explanation:</span>
            </div>
            <p className="text-text-primary leading-normal">{results.explanation}</p>
          </div>

          {/* Risk Factors / Uncertainties & Reason Codes */}
          <div className="space-y-2 pt-1">
            {results.uncertainties.length > 0 && (
              <div className="space-y-1.5">
                <span className="text-[10px] font-bold uppercase tracking-wider text-amber-400/80 block">
                  Risk Factors & Uncertainties:
                </span>
                <div className="flex flex-wrap gap-2">
                  {results.uncertainties.map((unc, i) => (
                    <span
                      key={i}
                      className="text-[11px] font-medium px-3 py-1 rounded-full bg-amber-500/10 text-amber-300 border border-amber-500/25 flex items-center gap-1.5"
                    >
                      <ShieldAlert className="h-3.5 w-3.5 shrink-0 text-amber-400" />
                      <span>{unc}</span>
                    </span>
                  ))}
                </div>
              </div>
            )}

            {results.reason_codes.length > 0 && (
              <div className="flex flex-wrap gap-1.5 pt-1">
                {results.reason_codes.map((code, i) => (
                  <span
                    key={i}
                    className="text-[10px] font-mono font-medium px-2.5 py-0.5 rounded-md bg-white/[0.03] text-text-secondary border border-white/[0.06]"
                  >
                    #{code}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="p-6 rounded-2xl glass-panel border border-[#F15A43]/20 relative overflow-hidden space-y-5">
          <div className="absolute top-0 right-0 -mr-16 -mt-16 w-48 h-48 rounded-full bg-[#F15A43]/10 blur-3xl pointer-events-none animate-pulse" />

          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-xl bg-[#F15A43]/15 border border-[#F15A43]/30 flex items-center justify-center text-[#F15A43] shrink-0">
                <Loader2 className="h-5 w-5 animate-spin" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-sm font-bold text-white">Statement Analysis in Progress</h3>
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-[#F15A43]/15 text-[#F15A43] border border-[#F15A43]/25 animate-pulse">
                    <span className="h-1.5 w-1.5 rounded-full bg-[#F15A43]" />
                    Auto-Polling Active
                  </span>
                </div>
                <p className="text-xs text-text-muted mt-0.5">
                  {resultsError ? resultsError : 'SalaryLens AI is extracting transactions, filtering debits & evaluating recurring salary candidates.'}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2 self-start sm:self-auto shrink-0">
              <button
                onClick={() => {
                  fetchResults();
                  fetchTransactions(txPage, filterIncluded);
                  fetchLogs();
                }}
                className="px-3 py-1.5 rounded-full bg-white/[0.05] hover:bg-white/[0.1] text-xs font-semibold text-white border border-white/[0.08] transition flex items-center gap-1.5"
              >
                <RefreshCw className="h-3.5 w-3.5 text-[#F15A43]" />
                <span>Refresh Status</span>
              </button>
              <button
                onClick={() => {
                  setShowLogs(true);
                  fetchLogs();
                }}
                className="px-3 py-1.5 rounded-full bg-[#8B7CFF]/15 hover:bg-[#8B7CFF]/25 text-xs font-semibold text-[#8B7CFF] border border-[#8B7CFF]/30 transition flex items-center gap-1.5"
              >
                <Terminal className="h-3.5 w-3.5" />
                <span>View Live Logs</span>
              </button>
            </div>
          </div>

          {/* 4-Step Pipeline Visualizer */}
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 pt-1">
            <div className="p-3 rounded-xl bg-white/[0.02] border border-white/[0.06]">
              <div className="flex items-center gap-2 mb-1">
                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                <span className="text-[11px] font-semibold text-emerald-400">1. Document Ingestion</span>
              </div>
              <p className="text-[10px] text-text-muted">
                {statement.page_count} pages • SHA-256 verified
              </p>
            </div>

            <div className="p-3 rounded-xl bg-white/[0.03] border border-[#F15A43]/30">
              <div className="flex items-center gap-2 mb-1">
                <RefreshCw className="h-3.5 w-3.5 text-[#F15A43] animate-spin" />
                <span className="text-[11px] font-semibold text-[#F15A43]">2. Layout Extraction</span>
              </div>
              <p className="text-[10px] text-text-muted">
                {txData?.total_count ? `${txData.total_count} transactions extracted` : 'Parsing coordinate tables...'}
              </p>
            </div>

            <div className="p-3 rounded-xl bg-white/[0.02] border border-white/[0.06]">
              <div className="flex items-center gap-2 mb-1">
                <Clock className="h-3.5 w-3.5 text-text-muted" />
                <span className="text-[11px] font-semibold text-text-secondary">3. Financial Filters</span>
              </div>
              <p className="text-[10px] text-text-muted">
                Debit exclusion & UPI categorization
              </p>
            </div>

            <div className="p-3 rounded-xl bg-white/[0.02] border border-white/[0.06]">
              <div className="flex items-center gap-2 mb-1">
                <Cpu className="h-3.5 w-3.5 text-text-muted" />
                <span className="text-[11px] font-semibold text-text-secondary">4. Jev Decision</span>
              </div>
              <p className="text-[10px] text-text-muted">
                Multi-model underwriting verdict
              </p>
            </div>
          </div>
        </div>
      )}

      {/* PHASE 2.C — JEV DECISION ENGINE OUTPUT */}
      {results && (
        <div className="rounded-2xl glass-panel border border-white/[0.08] p-5 space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-white/[0.06]">
            <div className="flex items-center gap-2.5">
              <div className="h-7 w-7 rounded-lg bg-indigo-500/15 border border-indigo-500/30 flex items-center justify-center text-[#8B7CFF]">
                <Cpu className="h-4 w-4" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <span>Jev Decision Engine Output</span>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-[#8B7CFF]/15 text-[#8B7CFF] border border-[#8B7CFF]/25 font-semibold">
                    v2.0 Production Grounded
                  </span>
                </h3>
                <p className="text-[11px] text-text-muted">
                  Formal decision reasoning, supporting evidence, and model diagnostics
                </p>
              </div>
            </div>

            <button
              onClick={() => setShowDiagnostics((prev) => !prev)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] text-text-secondary hover:text-white text-xs font-medium border border-white/[0.08] transition"
            >
              <Activity className="h-3.5 w-3.5 text-[#8B7CFF]" />
              <span>{showDiagnostics ? 'Hide Diagnostics' : 'Technical Diagnostics'}</span>
              {showDiagnostics ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
            </button>
          </div>

          {/* Jev Structured Evidence Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
            {/* Supporting Evidence Breakdown */}
            <div className="p-4 rounded-xl bg-[#141414] border border-white/[0.06] space-y-2.5">
              <div className="font-semibold text-white flex items-center gap-1.5 text-xs">
                <Check className="h-3.5 w-3.5 text-emerald-400" />
                <span>Supporting Evidence Verification</span>
              </div>
              <ul className="space-y-1.5 text-text-secondary text-[11px]">
                <li className="flex items-start gap-2">
                  <span className="text-emerald-400 font-bold">•</span>
                  <span>
                    <strong className="text-white">{results.supporting_transaction_ids.length || primaryGroup?.transaction_count || 0}</strong> verified transactions cited in payroll credit continuity.
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-emerald-400 font-bold">•</span>
                  <span>
                    Supported Months: <strong className="text-white">
                      {results.supporting_months.length > 0 ? results.supporting_months.join(', ') : 'Continuous statement window'}
                    </strong>
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-emerald-400 font-bold">•</span>
                  <span>
                    Employer Normalization: Canonical entity matched with strict token containment.
                  </span>
                </li>
              </ul>
            </div>

            {/* Underwriter Guidance & Competing Candidates */}
            <div className="p-4 rounded-xl bg-[#141414] border border-white/[0.06] space-y-2.5">
              <div className="font-semibold text-white flex items-center gap-1.5 text-xs">
                <UserCheck className="h-3.5 w-3.5 text-[#8B7CFF]" />
                <span>Human Review Guidance</span>
              </div>
              <p className="text-[11px] text-text-secondary leading-relaxed">
                {results.requires_human_review ? (
                  <span className="text-amber-300/90 font-medium">
                    Manual inspection recommended to confirm employer identity, verify irregular credits, or sign off on low amount variance.
                  </span>
                ) : (
                  <span className="text-emerald-400 font-medium">
                    Fully automated confidence thresholds satisfied. Statement meets standard underwriting payroll continuity standards.
                  </span>
                )}
              </p>
              {competingGroups.length > 0 && (
                <div className="pt-1.5 border-t border-white/[0.04] text-[10px] text-text-muted">
                  <span>Detected {competingGroups.length} competing stream(s) evaluated and subordinate to primary candidate.</span>
                </div>
              )}
            </div>
          </div>

          {/* Collapsible Technical Diagnostics Drawer */}
          {showDiagnostics && (
            <div className="p-4 rounded-xl bg-black/40 border border-white/[0.08] space-y-3 animate-in fade-in duration-150">
              <div className="flex items-center justify-between text-xs font-semibold text-white">
                <span className="flex items-center gap-1.5 text-[#8B7CFF]">
                  <Cpu className="h-3.5 w-3.5" />
                  Model Pipeline Diagnostics & Telemetry
                </span>
                <span className="text-[11px] text-text-muted">Prompt Version: v2.0-financial-rag</span>
              </div>

              {results.model_diagnostics && results.model_diagnostics.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-[11px] border-collapse">
                    <thead>
                      <tr className="border-b border-white/[0.06] text-text-muted text-[10px] uppercase">
                        <th className="py-2 px-3">Stage</th>
                        <th className="py-2 px-3">Model</th>
                        <th className="py-2 px-3 text-right">In Tokens</th>
                        <th className="py-2 px-3 text-right">Out Tokens</th>
                        <th className="py-2 px-3 text-right">Total Tokens</th>
                        <th className="py-2 px-3 text-right">Latency</th>
                        <th className="py-2 px-3 text-right">Cost (INR)</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/[0.04]">
                      {results.model_diagnostics.map((diag, i) => (
                        <tr key={i} className="hover:bg-white/[0.02]">
                          <td className="py-2 px-3 font-semibold text-white capitalize">{diag.stage}</td>
                          <td className="py-2 px-3 text-text-secondary font-mono text-[10px]">{diag.model_name}</td>
                          <td className="py-2 px-3 text-right font-mono text-text-muted">{diag.input_tokens.toLocaleString()}</td>
                          <td className="py-2 px-3 text-right font-mono text-text-muted">{diag.output_tokens.toLocaleString()}</td>
                          <td className="py-2 px-3 text-right font-mono font-semibold text-white">{diag.total_tokens.toLocaleString()}</td>
                          <td className="py-2 px-3 text-right font-mono text-[#8B7CFF]">{diag.latency_ms} ms</td>
                          <td className="py-2 px-3 text-right font-mono text-emerald-400">{formatAICostINR(diag.provider_cost_usd)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                  <div className="p-2.5 rounded-lg bg-white/[0.02] border border-white/[0.04]">
                    <span className="text-[10px] text-text-muted block">Decision Model</span>
                    <span className="font-mono text-white text-[11px] truncate block">{results.model_diagnostics?.[0]?.model_name || 'google/gemma-4-31b-it:free'}</span>
                  </div>
                  <div className="p-2.5 rounded-lg bg-white/[0.02] border border-white/[0.04]">
                    <span className="text-[10px] text-text-muted block">Total Tokens</span>
                    <span className="font-mono text-white text-[11px]">{results.total_tokens.toLocaleString()}</span>
                  </div>
                  <div className="p-2.5 rounded-lg bg-white/[0.02] border border-white/[0.04]">
                    <span className="text-[10px] text-text-muted block">Incurred AI Cost</span>
                    <span className="font-mono text-emerald-400 text-[11px]">{formatAICostINR(results.total_ai_cost_usd)}</span>
                  </div>
                  <div className="p-2.5 rounded-lg bg-white/[0.02] border border-white/[0.04]">
                    <span className="text-[10px] text-text-muted block">Validation Stage</span>
                    <span className="font-mono text-[#8B7CFF] text-[11px]">Grounded Deterministic</span>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* PHASE 3 — CLEANED UP CANDIDATE STREAM CARDS */}
      {results && results.candidate_groups.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm font-semibold text-white">
              <Layers className="h-4 w-4 text-[#F15A43]" />
              <span>Identified Salary Candidate Streams</span>
              <span className="text-xs text-text-muted">({results.candidate_groups.length} detected)</span>
            </div>
            <span className="text-xs text-text-muted">Click &quot;Show Details&quot; to inspect raw narrations</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {results.candidate_groups.map((group, idx) => {
              const isExpanded = expandedCandidates.has(idx);

              return (
                <div
                  key={idx}
                  className={`p-4 rounded-2xl glass-card transition-all duration-200 space-y-3 ${
                    group.is_primary
                      ? 'border-[#F15A43]/40 shadow-[0_0_20px_rgba(241,90,67,0.15)] ring-1 ring-[#F15A43]/30'
                      : 'border-white/[0.08]'
                  }`}
                >
                  {/* Top: Employer Name & Primary Badge */}
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <div className="text-sm font-bold text-white flex items-center gap-1.5">
                        <span className="truncate" title={group.employer_name}>
                          {group.employer_name}
                        </span>
                        {group.is_primary && (
                          <span className="text-[10px] px-2 py-0.5 rounded-full bg-[#F15A43] text-white font-semibold shrink-0">
                            Primary
                          </span>
                        )}
                      </div>
                      <span className="text-[11px] text-text-muted block mt-0.5">
                        {group.transaction_count} deposits across {group.months_count} mos
                      </span>
                    </div>

                    <div className="text-right shrink-0">
                      <span className="text-[10px] text-text-muted uppercase block font-semibold">Recurrence</span>
                      <span className="text-xs font-bold text-emerald-400">
                        {Math.round(group.recurrence_score * 100)}%
                      </span>
                    </div>
                  </div>

                  {/* Prominent Monthly Amount in INR */}
                  <div className="py-2.5 px-3 rounded-xl bg-white/[0.02] border border-white/[0.04] flex items-center justify-between">
                    <div>
                      <span className="text-[10px] text-text-muted uppercase font-semibold block">Average Credit</span>
                      <span className="text-lg font-black text-white font-mono">
                        {formatINR(group.average_amount)}
                      </span>
                    </div>
                    <div className="text-right">
                      <span className="text-[10px] text-text-muted uppercase font-semibold block">Variation</span>
                      <span className="text-xs font-semibold text-text-secondary">
                        {Number(group.amount_variation_pct).toFixed(1)}%
                      </span>
                    </div>
                  </div>

                  {/* Micro Metrics Row */}
                  <div className="grid grid-cols-2 gap-2 text-center text-xs border-t border-white/[0.04] pt-2">
                    <div>
                      <span className="text-[10px] text-text-muted block">Min Amount</span>
                      <span className="text-xs font-semibold text-white font-mono">
                        {formatINR(group.min_amount)}
                      </span>
                    </div>
                    <div>
                      <span className="text-[10px] text-text-muted block">Max Amount</span>
                      <span className="text-xs font-semibold text-white font-mono">
                        {formatINR(group.max_amount)}
                      </span>
                    </div>
                  </div>

                  {/* Missing Months Warning */}
                  {group.missing_months.length > 0 && (
                    <div className="text-[11px] text-amber-300 bg-amber-500/10 px-2.5 py-1 rounded-lg border border-amber-500/20 flex items-center gap-1.5">
                      <AlertTriangle className="h-3 w-3 shrink-0" />
                      <span className="truncate">Missing: {group.missing_months.join(', ')}</span>
                    </div>
                  )}

                  {/* Expandable Details Button */}
                  <button
                    onClick={() => toggleCandidateExpand(idx)}
                    className="w-full py-1.5 px-3 rounded-xl bg-white/[0.03] hover:bg-white/[0.06] text-text-secondary hover:text-white text-[11px] font-medium border border-white/[0.06] flex items-center justify-center gap-1.5 transition"
                  >
                    <span>{isExpanded ? 'Hide Raw Details' : 'Show Details & Narrations'}</span>
                    {isExpanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                  </button>

                  {/* Expanded Narrations and Aliases View (Scrollable, never stretching parent) */}
                  {isExpanded && (
                    <div className="pt-2 border-t border-white/[0.06] space-y-2 max-h-48 overflow-y-auto pr-1 text-[11px] animate-in fade-in duration-150">
                      <div>
                        <span className="text-[10px] text-text-muted uppercase font-semibold block mb-1">
                          Raw Narrations & Aliases:
                        </span>
                        {group.aliases.length > 0 ? (
                          <div className="space-y-1">
                            {group.aliases.map((alias, aIdx) => (
                              <div
                                key={aIdx}
                                className="p-1.5 rounded-lg bg-black/40 border border-white/[0.04] text-text-secondary font-mono text-[10px] break-all"
                              >
                                {alias}
                              </div>
                            ))}
                          </div>
                        ) : (
                          <span className="text-text-muted text-[10px]">No distinct aliases recorded.</span>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* HOW IT WORKS — PIPELINE EXECUTION LOGS PANEL */}
      <div className="rounded-2xl glass-panel border border-white/[0.08] p-5 space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-white/[0.06]">
          <div className="flex items-center gap-2.5">
            <div className="h-7 w-7 rounded-lg bg-[#8B7CFF]/15 border border-[#8B7CFF]/30 flex items-center justify-center text-[#8B7CFF]">
              <Terminal className="h-4 w-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <span>Pipeline Execution Logs</span>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-[#8B7CFF]/15 text-[#8B7CFF] border border-[#8B7CFF]/25 font-semibold">
                  How It Works
                </span>
              </h3>
              <p className="text-[11px] text-text-muted">
                Chronological technical milestones detailing PDF extraction, financial filtering, and AI underwriting decisions
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={fetchLogs}
              disabled={loadingLogs}
              className="p-1.5 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] text-text-secondary hover:text-white transition"
              title="Refresh logs"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${loadingLogs ? 'animate-spin text-[#F15A43]' : ''}`} />
            </button>
            <button
              onClick={() => setShowLogs((prev) => !prev)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] text-text-secondary hover:text-white text-xs font-medium border border-white/[0.08] transition"
            >
              <span>{showLogs ? 'Hide Logs' : 'View Logs'}</span>
              {showLogs ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
            </button>
          </div>
        </div>

        {showLogs && (
          <div className="space-y-2.5 animate-in fade-in pt-1">
            {pipelineLogs.length === 0 ? (
              <div className="p-4 rounded-xl bg-black/20 text-center text-xs text-text-muted">
                {loadingLogs ? 'Loading execution logs...' : 'No pipeline execution events recorded yet.'}
              </div>
            ) : (
              pipelineLogs.map((log, idx) => {
                const getLevelBadge = (lvl: string) => {
                  switch (lvl.toUpperCase()) {
                    case 'SUCCESS':
                      return 'bg-emerald-500/15 text-emerald-400 border-emerald-500/25';
                    case 'WARNING':
                      return 'bg-amber-500/15 text-amber-400 border-amber-500/25';
                    case 'ERROR':
                      return 'bg-rose-500/15 text-rose-400 border-rose-500/25';
                    case 'INFO':
                    default:
                      return 'bg-[#8B7CFF]/15 text-[#8B7CFF] border-[#8B7CFF]/25';
                  }
                };

                return (
                  <div
                    key={idx}
                    className="p-3.5 rounded-xl bg-black/30 border border-white/[0.05] hover:border-white/10 transition space-y-1.5"
                  >
                    <div className="flex items-center justify-between gap-2 flex-wrap text-xs">
                      <div className="flex items-center gap-2">
                        <span className={`text-[10px] font-mono px-2 py-0.5 rounded-md border font-semibold ${getLevelBadge(log.level)}`}>
                          {log.stage}
                        </span>
                        <span className="font-semibold text-white text-xs">{log.title}</span>
                      </div>
                      <span className="text-[10px] text-text-muted font-mono">
                        {log.timestamp ? new Date(log.timestamp).toLocaleTimeString() : ''}
                      </span>
                    </div>

                    <p className="text-xs text-text-secondary leading-relaxed pl-1">
                      {log.message}
                    </p>

                    {log.metadata && Object.keys(log.metadata).length > 0 && (
                      <div className="pt-1 flex flex-wrap gap-2 text-[10px] font-mono text-text-muted pl-1">
                        {Object.entries(log.metadata).map(([k, v]) => (
                          <span key={k} className="px-2 py-0.5 rounded bg-white/[0.03] border border-white/[0.05]">
                            <span className="text-text-secondary">{k}:</span> {typeof v === 'object' ? JSON.stringify(v) : String(v)}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        )}
      </div>

      {/* EXTRACTED TRANSACTIONS SECTION */}
      <div className="rounded-2xl glass-panel overflow-hidden border border-white/[0.08] shadow-glass space-y-0">
        <div className="p-5 border-b border-white/[0.06] flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Filter className="h-4 w-4 text-[#F15A43]" />
            <h3 className="text-sm font-semibold text-white">Bank Transaction Ledger</h3>
            {txData && (
              <span className="text-xs text-text-muted">({txData.total_count} extracted)</span>
            )}
          </div>

          {/* Filter Pills */}
          <div className="inline-flex rounded-full bg-[#141414] p-1 border border-white/[0.08] text-xs">
            <button
              onClick={() => {
                setFilterIncluded(undefined);
                setTxPage(1);
              }}
              className={`px-3 py-1 rounded-full text-[11px] font-medium transition-all ${
                filterIncluded === undefined
                  ? 'bg-[#F15A43] text-white'
                  : 'text-text-muted hover:text-white'
              }`}
            >
              All Records
            </button>
            <button
              onClick={() => {
                setFilterIncluded(true);
                setTxPage(1);
              }}
              className={`px-3 py-1 rounded-full text-[11px] font-medium transition-all ${
                filterIncluded === true
                  ? 'bg-[#F15A43] text-white'
                  : 'text-text-muted hover:text-white'
              }`}
            >
              Salary Analysis Set
            </button>
            <button
              onClick={() => {
                setFilterIncluded(false);
                setTxPage(1);
              }}
              className={`px-3 py-1 rounded-full text-[11px] font-medium transition-all ${
                filterIncluded === false
                  ? 'bg-[#F15A43] text-white'
                  : 'text-text-muted hover:text-white'
              }`}
            >
              Excluded
            </button>
          </div>
        </div>

        {/* Transactions Table with INR Currency Formatting */}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-white/[0.06] text-text-muted uppercase text-[10px] tracking-wider bg-white/[0.01]">
                <th className="py-2.5 px-5 font-medium">Date</th>
                <th className="py-2.5 px-4 font-medium">Description</th>
                <th className="py-2.5 px-4 font-medium text-right">Credit (+)</th>
                <th className="py-2.5 px-4 font-medium text-right">Debit (-)</th>
                <th className="py-2.5 px-4 font-medium text-right">Balance</th>
                <th className="py-2.5 px-4 font-medium">Inclusion / Reason</th>
                <th className="py-2.5 px-5 font-medium text-center">Dataset</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.04] text-[11px]">
              {loadingTx ? (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-text-muted">
                    <RefreshCw className="h-5 w-5 animate-spin mx-auto mb-1 text-[#F15A43]" />
                    Loading transaction records...
                  </td>
                </tr>
              ) : txData?.transactions.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-text-muted">
                    No transactions match the selected filter.
                  </td>
                </tr>
              ) : (
                txData?.transactions.map((tx) => (
                  <tr
                    key={tx.id}
                    className={`hover:bg-white/[0.03] transition ${
                      tx.is_salary_candidate ? 'bg-[#F15A43]/5' : ''
                    }`}
                  >
                    <td className="py-2.5 px-5 text-text-secondary whitespace-nowrap font-mono">
                      {tx.transaction_date}
                    </td>
                    <td className="py-2.5 px-4 text-text-primary max-w-xs truncate" title={tx.raw_description}>
                      {tx.raw_description}
                    </td>
                    <td className="py-2.5 px-4 text-right font-semibold text-emerald-400 whitespace-nowrap font-mono">
                      {tx.credit_amount ? `+${formatINR(tx.credit_amount, true)}` : '—'}
                    </td>
                    <td className="py-2.5 px-4 text-right text-rose-400 whitespace-nowrap font-mono">
                      {tx.debit_amount ? `-${formatINR(tx.debit_amount, true)}` : '—'}
                    </td>
                    <td className="py-2.5 px-4 text-right text-text-muted whitespace-nowrap font-mono">
                      {tx.balance ? formatINR(tx.balance, true) : '—'}
                    </td>
                    <td className="py-2.5 px-4 text-text-secondary">
                      {tx.inclusion_reason ? (
                        <span className="text-[#8B7CFF] text-[10px] font-medium">{tx.inclusion_reason}</span>
                      ) : tx.exclusion_reason ? (
                        <span className="text-text-muted text-[10px]">{tx.exclusion_reason}</span>
                      ) : (
                        <span className="text-text-muted text-[10px]">—</span>
                      )}
                    </td>
                    <td className="py-2.5 px-5 text-center">
                      {tx.included_in_salary_analysis ? (
                        <span className="inline-block px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 text-[10px] font-semibold border border-emerald-500/25">
                          Included
                        </span>
                      ) : (
                        <span className="inline-block px-2 py-0.5 rounded-full bg-white/[0.04] text-text-muted text-[10px]">
                          Excluded
                        </span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Controls */}
        {txData && txData.total_count > txData.page_size && (
          <div className="p-4 border-t border-white/[0.06] flex items-center justify-between text-xs text-text-muted">
            <div>
              Showing {(txPage - 1) * txData.page_size + 1} to{' '}
              {Math.min(txPage * txData.page_size, txData.total_count)} of {txData.total_count} records
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setTxPage((p) => Math.max(1, p - 1))}
                disabled={txPage <= 1}
                className="h-8 w-8 rounded-full bg-[#161616] hover:bg-white/[0.08] disabled:opacity-30 text-white flex items-center justify-center border border-white/[0.08] transition"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <span className="text-text-secondary font-medium">Page {txPage}</span>
              <button
                onClick={() => setTxPage((p) => p + 1)}
                disabled={txPage * txData.page_size >= txData.total_count}
                className="h-8 w-8 rounded-full bg-[#161616] hover:bg-white/[0.08] disabled:opacity-30 text-white flex items-center justify-center border border-white/[0.08] transition"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
