import React, { useState } from 'react';
import {
  FileSpreadsheet,
  Clock,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Download,
  ChevronRight,
  RefreshCw,
  Search,
  Filter,
  Trash2,
} from 'lucide-react';
import { StatementItem } from '../types';

interface StatementsTableProps {
  statements: StatementItem[];
  loading: boolean;
  onSelectStatement: (statement: StatementItem) => void;
  onDownloadWorkbook: (statement: StatementItem, e: React.MouseEvent) => void;
  onRefresh: () => void;
  onDeleteStatement?: (statement: StatementItem) => void;
}

export const StatementsTable: React.FC<StatementsTableProps> = ({
  statements,
  loading,
  onSelectStatement,
  onDownloadWorkbook,
  onRefresh,
  onDeleteStatement,
}) => {
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [search, setSearch] = useState<string>('');

  const filteredStatements = statements.filter((stmt) => {
    const matchesStatus =
      filterStatus === 'all' || stmt.status === filterStatus;
    const matchesSearch =
      search === '' || stmt.filename.toLowerCase().includes(search.toLowerCase());
    return matchesStatus && matchesSearch;
  });

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'completed':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/20 shadow-[0_0_10px_rgba(34,197,94,0.1)]">
            <CheckCircle2 className="h-3 w-3" />
            Verified
          </span>
        );
      case 'requires_human_review':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-amber-500/15 text-amber-400 border border-amber-500/20 shadow-[0_0_10px_rgba(245,158,11,0.1)]">
            <AlertTriangle className="h-3 w-3" />
            Needs Review
          </span>
        );
      case 'processing':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-[#8B7CFF]/15 text-[#8B7CFF] border border-[#8B7CFF]/20 animate-pulse">
            <RefreshCw className="h-3 w-3 animate-spin" />
            Processing
          </span>
        );
      case 'failed':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-rose-500/15 text-rose-400 border border-rose-500/20">
            <XCircle className="h-3 w-3" />
            Failed
          </span>
        );
      case 'pending':
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-white/[0.05] text-text-muted border border-white/10">
            <Clock className="h-3 w-3" />
            Queued
          </span>
        );
    }
  };

  return (
    <div className="rounded-2xl glass-panel overflow-hidden border border-white/[0.08] shadow-glass space-y-0">
      {/* Table Header Controls */}
      <div className="p-5 border-b border-white/[0.06] flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="h-8 w-8 rounded-xl bg-[#F15A43]/15 text-[#F15A43] flex items-center justify-center">
            <FileSpreadsheet className="h-4 w-4" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-white">Bank Statement Ingestion Queue</h2>
            <p className="text-xs text-text-muted">Manage uploaded statements, verify salary streams and review AI decisions</p>
          </div>
        </div>

        {/* Filters and search */}
        <div className="flex items-center gap-3 flex-wrap">
          {/* Status filter tabs */}
          <div className="inline-flex rounded-full bg-[#141414] p-1 border border-white/[0.08] text-xs">
            {['all', 'completed', 'requires_human_review', 'processing'].map((st) => (
              <button
                key={st}
                onClick={() => setFilterStatus(st)}
                className={`px-3 py-1 rounded-full text-[11px] font-medium transition-all ${
                  filterStatus === st
                    ? 'bg-[#F15A43] text-white shadow-sm'
                    : 'text-text-muted hover:text-white'
                }`}
              >
                {st === 'all'
                  ? 'All'
                  : st === 'completed'
                  ? 'Verified'
                  : st === 'requires_human_review'
                  ? 'Review'
                  : 'Processing'}
              </button>
            ))}
          </div>

          <button
            onClick={onRefresh}
            className="p-2 rounded-full bg-[#141414] border border-white/[0.08] text-text-muted hover:text-white hover:border-white/20 transition"
            title="Refresh"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin text-[#F15A43]' : ''}`} />
          </button>
        </div>
      </div>

      {/* Table Body */}
      {filteredStatements.length === 0 ? (
        <div className="py-20 text-center space-y-3">
          <FileSpreadsheet className="h-10 w-10 text-text-muted mx-auto opacity-40" />
          <h3 className="text-sm font-medium text-text-secondary">No bank statements match your criteria</h3>
          <p className="text-xs text-text-muted max-w-sm mx-auto">
            Upload new statements or clear your filter to view results.
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-white/[0.06] text-text-muted uppercase text-[10px] tracking-wider bg-white/[0.01]">
                <th className="py-3 px-5 font-medium">Statement File</th>
                <th className="py-3 px-4 font-medium text-center">Pages</th>
                <th className="py-3 px-4 font-medium text-center">Transactions</th>
                <th className="py-3 px-4 font-medium">Status</th>
                <th className="py-3 px-4 font-medium">Workbook</th>
                <th className="py-3 px-4 font-medium">Uploaded</th>
                <th className="py-3 px-5 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.04]">
              {filteredStatements.map((stmt) => (
                <tr
                  key={stmt.statement_id}
                  onClick={() => onSelectStatement(stmt)}
                  className="hover:bg-white/[0.03] cursor-pointer transition group"
                >
                  <td className="py-3.5 px-5">
                    <div className="flex items-center gap-3">
                      <div className="h-9 w-9 rounded-xl bg-[#F15A43]/10 border border-[#F15A43]/20 text-[#F15A43] flex items-center justify-center shrink-0 group-hover:scale-105 transition">
                        <FileSpreadsheet className="h-4 w-4" />
                      </div>
                      <div>
                        <div className="font-semibold text-text-primary group-hover:text-[#F15A43] transition">
                          {stmt.filename}
                        </div>
                        <div className="text-[11px] text-text-muted">
                          {(stmt.file_size_bytes / (1024 * 1024)).toFixed(2)} MB
                          {stmt.is_scanned && (
                            <span className="ml-2 text-amber-400 font-medium">• Scanned Document</span>
                          )}
                        </div>
                      </div>
                    </div>
                  </td>
                  <td className="py-3.5 px-4 text-center text-text-secondary">
                    {stmt.page_count} pg
                  </td>
                  <td className="py-3.5 px-4 text-center text-text-secondary">
                    {stmt.total_transactions_count ? (
                      <div>
                        <span className="font-semibold text-white">{stmt.total_transactions_count}</span>
                        <div className="text-[10px] text-text-muted">
                          {stmt.included_in_salary_count || 0} salary / {stmt.excluded_from_salary_count || 0} excl
                        </div>
                      </div>
                    ) : (
                      <span className="text-text-muted">—</span>
                    )}
                  </td>
                  <td className="py-3.5 px-4">
                    {getStatusBadge(stmt.status)}
                  </td>
                  <td className="py-3.5 px-4">
                    {stmt.status !== 'processing' ? (
                      <button
                        onClick={(e) => onDownloadWorkbook(stmt, e)}
                        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-300 text-[11px] font-semibold border border-emerald-500/20 transition"
                        title="Download 5-Sheet Excel Workbook"
                      >
                        <Download className="h-3 w-3" />
                        <span>.XLSX</span>
                      </button>
                    ) : (
                      <span className="text-text-muted text-[11px]">—</span>
                    )}
                  </td>
                  <td className="py-3.5 px-4 text-text-muted text-[11px]">
                    {new Date(stmt.created_at).toLocaleString([], {
                      month: 'short',
                      day: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </td>
                  <td className="py-3.5 px-5 text-right">
                    <div className="flex items-center justify-end gap-1.5" onClick={(e) => e.stopPropagation()}>
                      {onDeleteStatement && (
                        <button
                          onClick={() => onDeleteStatement(stmt)}
                          className="h-7 w-7 rounded-full bg-white/[0.04] hover:bg-rose-500/20 text-text-muted hover:text-rose-400 border border-white/[0.08] hover:border-rose-500/30 flex items-center justify-center transition"
                          title="Delete statement"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      )}
                      <button
                        onClick={() => onSelectStatement(stmt)}
                        className="inline-flex items-center gap-1 px-3 py-1.5 rounded-full bg-white/[0.04] hover:bg-[#F15A43] hover:text-white text-text-secondary text-xs font-medium border border-white/[0.08] transition"
                      >
                        <span>Inspect</span>
                        <ChevronRight className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
