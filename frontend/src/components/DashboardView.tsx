import React, { useMemo } from 'react';
import {
  FileSpreadsheet,
  CheckCircle2,
  AlertTriangle,
  Building2,
  ChevronRight,
  Download,
  Calendar,
  Activity,
  Sparkles,
  Trash2,
} from 'lucide-react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { DashboardSummary, StatementItem } from '../types';

interface DashboardViewProps {
  summary: DashboardSummary | null;
  statements: StatementItem[];
  loading: boolean;
  onSelectStatement: (statement: StatementItem) => void;
  onDownloadWorkbook: (statement: StatementItem, e: React.MouseEvent) => void;
  onViewAllStatements?: () => void;
  onDeleteStatement?: (statement: StatementItem) => void;
}

export const DashboardView: React.FC<DashboardViewProps> = ({
  summary,
  statements,
  loading,
  onSelectStatement,
  onDownloadWorkbook,
  onViewAllStatements,
  onDeleteStatement,
}) => {
  // 1. Metric cards data strictly bound to actual API / database state
  const totalStatementsCount = summary?.total_statements ?? summary?.total_statements_processed ?? statements.length;
  const verifiedSalaryCount = summary?.likely_salary_count ?? statements.filter(s => s.status === 'completed' || s.salary_status === 'likely_salary').length;
  const requiresReviewCount = summary?.requires_human_review_count ?? summary?.pending_reviews_count ?? statements.filter(s => s.status === 'requires_human_review').length;
  const avgSalary = Number(summary?.average_salary_usd ?? summary?.average_monthly_salary_usd ?? 0);
  const totalAiSpend = Number(summary?.total_spend_usd ?? summary?.total_ai_spend_usd ?? 0);

  const metricCards = [
    {
      title: 'Total Statements',
      value: totalStatementsCount.toLocaleString(),
      pillText: `${totalStatementsCount} Ingested`,
      timeframe: `${statements.filter(s => s.status === 'completed').length} completed analysis`,
      accentColor: 'text-[#8B7CFF]',
      pillBg: 'bg-[#8B7CFF]/15 text-[#8B7CFF] border border-[#8B7CFF]/25',
      prefix: '',
    },
    {
      title: 'Verified Salary (Likely)',
      value: verifiedSalaryCount.toLocaleString(),
      pillText: 'Verified',
      timeframe: `${summary?.possible_salary_count ?? 0} possible candidate(s)`,
      accentColor: 'text-emerald-400',
      pillBg: 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/25',
      prefix: '',
    },
    {
      title: 'Requires Review',
      value: requiresReviewCount.toLocaleString(),
      pillText: 'Review Queue',
      timeframe: `${summary?.pending_reviews_count ?? requiresReviewCount} pending verification`,
      accentColor: 'text-[#F15A43]',
      pillBg: 'bg-[#F15A43]/15 text-[#F15A43] border border-[#F15A43]/25',
      prefix: '',
    },
    {
      title: 'Avg Monthly Salary',
      value: avgSalary > 0
        ? new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 }).format(avgSalary)
        : '0',
      pillText: 'Active',
      timeframe: `AI Spend: ₹ ${(totalAiSpend * 86.0).toFixed(2)}`,
      accentColor: 'text-[#8B7CFF]',
      pillBg: 'bg-[#8B7CFF]/15 text-[#8B7CFF] border border-[#8B7CFF]/25',
      prefix: '₹ ',
    },
  ];

  // 2. Real Chart data aggregated dynamically from actual ingested statements
  const chartData = useMemo(() => {
    if (!statements || statements.length === 0) return [];

    const monthMap = new Map<string, { month: string; verified: number; target: number }>();
    const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

    // Collect timestamps and map to months
    statements.forEach((stmt) => {
      try {
        const d = new Date(stmt.created_at || Date.now());
        const monthKey = monthNames[d.getMonth()];
        const entry = monthMap.get(monthKey) || { month: monthKey, verified: 0, target: 0 };
        entry.target += (stmt.total_transactions_count && stmt.total_transactions_count > 0 ? stmt.total_transactions_count : 10);
        if (stmt.status === 'completed' || stmt.salary_status === 'likely_salary' || stmt.status === 'requires_human_review') {
          entry.verified += (stmt.included_in_salary_count && stmt.included_in_salary_count > 0 ? stmt.included_in_salary_count : 1);
        }
        monthMap.set(monthKey, entry);
      } catch {
        // ignore date parse issues
      }
    });

    return Array.from(monthMap.values());
  }, [statements]);

  // 3. Real Ingestion Activity (Day of Week x Hour Buckets)
  const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  const times = ['9 am', '10 am', '11 am', '12 pm', '1 pm', '2 pm', '3 pm'];

  const heatMatrix = useMemo(() => {
    const matrix: number[][] = Array(times.length).fill(0).map(() => Array(days.length).fill(0));
    statements.forEach((stmt) => {
      try {
        const d = new Date(stmt.created_at || Date.now());
        const dayIdx = (d.getDay() + 6) % 7; // Convert Sun=0 to Mon=0
        const hour = d.getHours();
        const timeIdx = Math.max(0, Math.min(times.length - 1, Math.floor((hour - 9) / 2)));
        if (matrix[timeIdx] && matrix[timeIdx][dayIdx] !== undefined) {
          matrix[timeIdx][dayIdx] += 1;
        }
      } catch {
        // ignore
      }
    });
    return matrix;
  }, [statements]);

  const getHeatLevel = (tIdx: number, dIdx: number) => {
    const count = heatMatrix[tIdx]?.[dIdx] || 0;
    if (count >= 5) return 4;
    if (count >= 3) return 3;
    if (count >= 2) return 2;
    if (count >= 1) return 1;
    return 0;
  };

  // 4. Real Detected Employer streams aggregated from actual statement analysis results
  const detectedEmployerStreams = useMemo(() => {
    const list: Array<{
      name: string;
      amount: string;
      recurrence: string;
      code: string;
      count: string;
    }> = [];

    const seen = new Set<string>();
    statements.forEach((stmt) => {
      if (stmt.detected_employer && !seen.has(stmt.detected_employer.toUpperCase())) {
        seen.add(stmt.detected_employer.toUpperCase());
        const symbol = stmt.currency === 'INR' ? '₹' : '$';
        const formattedAmt = stmt.average_salary && Number(stmt.average_salary) > 0
          ? `${symbol}${Number(stmt.average_salary).toLocaleString(undefined, { maximumFractionDigits: 0 })}`
          : 'Analyzed';

        list.push({
          name: stmt.detected_employer,
          amount: formattedAmt,
          recurrence: stmt.salary_status === 'likely_salary' ? '100%' : 'Candidate',
          code: stmt.detected_employer.slice(0, 2).toUpperCase(),
          count: `${stmt.total_transactions_count ?? 1} transactions`,
        });
      }
    });

    return list.slice(0, 6);
  }, [statements]);

  const recentStatements = statements.slice(0, 5);

  return (
    <div className="space-y-5 animate-in fade-in duration-300">
      {/* ROW 1: Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {metricCards.map((card, i) => (
          <div
            key={i}
            className="p-5 rounded-2xl glass-card relative overflow-hidden group hover:border-white/20 transition-all duration-300"
          >
            {/* Top row: Label & Trend / Status Pill */}
            <div className="flex items-center justify-between gap-2">
              <span className="text-[13px] font-medium text-text-secondary">{card.title}</span>
              <span
                className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold ${card.pillBg}`}
              >
                <span>{card.pillText}</span>
              </span>
            </div>

            {/* Middle: Prominent Value */}
            <div className="mt-3 flex items-baseline gap-1">
              {card.prefix && (
                <span className="text-xl font-bold text-[#F15A43]">{card.prefix}</span>
              )}
              <span className="text-3xl font-extrabold text-white tracking-tight">
                {card.value}
              </span>
            </div>

            {/* Bottom: Supporting Context */}
            <div className="mt-2 text-[11px] text-text-muted">{card.timeframe}</div>
          </div>
        ))}
      </div>

      {/* ROW 2: Heatmap & Line Performance Chart */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Left: Processing Activity Heatmap (5 cols) */}
        <div className="lg:col-span-5 p-5 rounded-2xl glass-card flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-semibold text-white">Ingestion Activity</h3>
                <span className="text-[10px] text-text-muted px-2 py-0.5 rounded bg-white/[0.04]">Live Ledger</span>
              </div>

              {/* Legend */}
              <div className="flex items-center gap-2 text-[10px] text-text-muted">
                <span className="flex items-center gap-1">
                  <span className="h-1.5 w-1.5 rounded-full bg-[#332220]" />
                  1+
                </span>
                <span className="flex items-center gap-1">
                  <span className="h-1.5 w-1.5 rounded-full bg-[#8c3224]" />
                  2+
                </span>
                <span className="flex items-center gap-1">
                  <span className="h-1.5 w-1.5 rounded-full bg-[#d6412b]" />
                  3+
                </span>
                <span className="flex items-center gap-1">
                  <span className="h-1.5 w-1.5 rounded-full bg-[#F15A43]" />
                  5+
                </span>
              </div>
            </div>

            {/* Heatmap Matrix Grid */}
            <div className="space-y-1.5 pt-1">
              {times.map((time, tIdx) => (
                <div key={time} className="flex items-center gap-2">
                  <span className="w-10 text-[10px] text-text-muted text-right shrink-0">{time}</span>
                  <div className="grid grid-cols-7 gap-1.5 flex-1">
                    {days.map((day, dIdx) => {
                      const level = getHeatLevel(tIdx, dIdx);
                      let cellClass = 'bg-white/[0.03] border border-white/[0.03]';
                      if (level === 1) cellClass = 'bg-[#3b1c17] border border-[#52231c]';
                      if (level === 2) cellClass = 'bg-[#7a2c20] border border-[#a13b2c]';
                      if (level === 3) cellClass = 'bg-[#c93f2c] border border-[#f15a43]/40 shadow-[0_0_8px_rgba(241,90,67,0.3)]';
                      if (level === 4) cellClass = 'bg-[#F15A43] border border-white/40 shadow-[0_0_12px_rgba(241,90,67,0.6)]';

                      return (
                        <div
                          key={day}
                          title={`${day} ${time}: ${heatMatrix[tIdx]?.[dIdx] || 0} statement(s)`}
                          className={`h-6 rounded-md transition-all duration-150 hover:scale-105 cursor-pointer ${cellClass}`}
                        />
                      );
                    })}
                  </div>
                </div>
              ))}

              {/* Day Labels */}
              <div className="flex items-center gap-2 pt-1">
                <span className="w-10" />
                <div className="grid grid-cols-7 gap-1.5 flex-1 text-center">
                  {days.map((d) => (
                    <span key={d} className="text-[10px] text-text-muted">{d}</span>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Right: Monthly Detection Performance Chart (7 cols) */}
        <div className="lg:col-span-7 p-5 rounded-2xl glass-card flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <div>
                <h3 className="text-sm font-semibold text-white">Monthly Verification Performance</h3>
                <p className="text-[11px] text-text-muted">Salary verification vs total credit volume</p>
              </div>

              {/* Chart Legend */}
              <div className="flex items-center gap-3 text-xs">
                <span className="flex items-center gap-1.5 text-text-secondary">
                  <span className="h-2 w-2 rounded-full bg-[#F15A43]" />
                  Verified
                </span>
                <span className="flex items-center gap-1.5 text-text-secondary">
                  <span className="h-2 w-2 rounded-full bg-[#8B7CFF]" />
                  Total Ingestion
                </span>
              </div>
            </div>

            {/* Recharts Area Chart or Clean Empty State */}
            <div className="h-56 w-full pt-2">
              {chartData.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-center p-4 rounded-xl border border-dashed border-white/10">
                  <Activity className="h-8 w-8 text-text-muted mb-2 animate-pulse" />
                  <p className="text-xs font-semibold text-white">No Monthly Activity Yet</p>
                  <p className="text-[11px] text-text-muted mt-1 max-w-sm">
                    Upload customer bank statements to view monthly salary verification timelines.
                  </p>
                </div>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <defs>
                      <linearGradient id="colorVerified" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#F15A43" stopOpacity={0.35} />
                        <stop offset="95%" stopColor="#F15A43" stopOpacity={0.0} />
                      </linearGradient>
                      <linearGradient id="colorTarget" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#8B7CFF" stopOpacity={0.25} />
                        <stop offset="95%" stopColor="#8B7CFF" stopOpacity={0.0} />
                      </linearGradient>
                    </defs>
                    <XAxis
                      dataKey="month"
                      stroke="#52525b"
                      tick={{ fill: '#71717A', fontSize: 11 }}
                      tickLine={false}
                      axisLine={{ stroke: 'rgba(255,255,255,0.06)' }}
                    />
                    <YAxis
                      stroke="#52525b"
                      tick={{ fill: '#71717A', fontSize: 11 }}
                      tickLine={false}
                      axisLine={false}
                    />
                    <Tooltip
                      content={({ active, payload, label }) => {
                        if (active && payload && payload.length) {
                          return (
                            <div className="p-3 rounded-xl bg-[#141414]/95 border border-white/10 shadow-glass text-xs space-y-1 backdrop-blur-md">
                              <div className="font-semibold text-white">{label}</div>
                              <div className="flex items-center justify-between gap-4 text-[#F15A43]">
                                <span>• Verified Salary:</span>
                                <span className="font-bold text-white">{payload[0]?.value?.toLocaleString()}</span>
                              </div>
                              <div className="flex items-center justify-between gap-4 text-[#8B7CFF]">
                                <span>• Total Transactions:</span>
                                <span className="font-bold text-white">{payload[1]?.value?.toLocaleString()}</span>
                              </div>
                            </div>
                          );
                        }
                        return null;
                      }}
                    />
                    <Area
                      type="monotone"
                      dataKey="verified"
                      stroke="#F15A43"
                      strokeWidth={2.5}
                      fillOpacity={1}
                      fill="url(#colorVerified)"
                    />
                    <Area
                      type="monotone"
                      dataKey="target"
                      stroke="#8B7CFF"
                      strokeWidth={2}
                      fillOpacity={1}
                      fill="url(#colorTarget)"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* ROW 3: Secondary Panels (Employers & Statements Queue Table) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Left: Primary Employers Detected (4 cols) */}
        <div className="lg:col-span-4 p-5 rounded-2xl glass-card flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-white">Employer Streams</h3>
              <button
                onClick={onViewAllStatements}
                className="text-xs text-text-muted hover:text-white transition"
              >
                View All
              </button>
            </div>

            {detectedEmployerStreams.length === 0 ? (
              <div className="py-8 text-center p-4 rounded-xl border border-dashed border-white/10 space-y-2">
                <Building2 className="h-6 w-6 text-text-muted mx-auto" />
                <p className="text-xs font-semibold text-white">No Employers Detected Yet</p>
                <p className="text-[11px] text-text-muted">
                  Ingest statements to automatically extract verified employer payroll streams.
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                {detectedEmployerStreams.map((emp, i) => (
                  <div
                    key={i}
                    className="p-3 rounded-xl bg-white/[0.025] hover:bg-white/[0.05] border border-white/[0.06] hover:border-white/[0.12] transition flex flex-col justify-between"
                  >
                    <div className="flex items-center gap-2">
                      <div className="h-6 w-6 rounded-lg bg-[#F15A43]/15 text-[#F15A43] flex items-center justify-center text-[10px] font-bold">
                        {emp.code}
                      </div>
                      <span className="text-xs font-semibold text-white truncate" title={emp.name}>{emp.name}</span>
                    </div>
                    <div className="mt-2.5 flex items-baseline justify-between">
                      <span className="text-sm font-bold text-white">{emp.amount}</span>
                      <span className="text-[10px] text-emerald-400 font-semibold">{emp.recurrence}</span>
                    </div>
                    <div className="text-[10px] text-text-muted mt-0.5">{emp.count}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right: Recent Statements Queue Table (8 cols) */}
        <div className="lg:col-span-8 p-5 rounded-2xl glass-card flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-semibold text-white">Recent Statement Ingestion</h3>
                <span className="text-xs text-text-muted">({statements.length} total)</span>
              </div>
              <button
                onClick={onViewAllStatements}
                className="text-xs text-text-muted hover:text-white transition"
              >
                View All
              </button>
            </div>

            {/* Table */}
            {recentStatements.length === 0 ? (
              <div className="py-12 text-center text-xs text-text-muted">
                No bank statements uploaded yet. Click "Upload PDF" to analyze statements.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="border-b border-white/[0.06] text-text-muted uppercase text-[10px] tracking-wider">
                      <th className="py-2.5 px-3 font-medium">Statement File</th>
                      <th className="py-2.5 px-3 font-medium text-center">Pages</th>
                      <th className="py-2.5 px-3 font-medium text-center">Transactions</th>
                      <th className="py-2.5 px-3 font-medium">Detected Employer</th>
                      <th className="py-2.5 px-3 font-medium">Status</th>
                      <th className="py-2.5 px-3 font-medium text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/[0.04]">
                    {recentStatements.map((stmt) => (
                      <tr
                        key={stmt.statement_id}
                        onClick={() => onSelectStatement(stmt)}
                        className="hover:bg-white/[0.03] cursor-pointer transition group"
                      >
                        <td className="py-3 px-3">
                          <div className="flex items-center gap-2.5">
                            <div className="h-7 w-7 rounded-lg bg-[#F15A43]/15 text-[#F15A43] flex items-center justify-center shrink-0">
                              <FileSpreadsheet className="h-3.5 w-3.5" />
                            </div>
                            <div className="truncate max-w-[180px]">
                              <div className="font-semibold text-text-primary group-hover:text-[#F15A43] transition truncate">
                                {stmt.filename}
                              </div>
                              <div className="text-[10px] text-text-muted">
                                {(stmt.file_size_bytes / (1024 * 1024)).toFixed(2)} MB
                                {stmt.is_scanned && <span className="ml-1 text-amber-400">• Scanned</span>}
                              </div>
                            </div>
                          </div>
                        </td>
                        <td className="py-3 px-3 text-center text-text-secondary">
                          {stmt.page_count} pg
                        </td>
                        <td className="py-3 px-3 text-center text-text-secondary">
                          {stmt.total_transactions_count ? (
                            <span className="font-medium text-white">{stmt.total_transactions_count}</span>
                          ) : (
                            <span className="text-text-muted">—</span>
                          )}
                        </td>
                        <td className="py-3 px-3">
                          {stmt.detected_employer ? (
                            <span className="font-semibold text-white truncate max-w-[140px] block" title={stmt.detected_employer}>
                              {stmt.detected_employer}
                            </span>
                          ) : (
                            <span className="text-text-muted">—</span>
                          )}
                        </td>
                        <td className="py-3 px-3">
                          {stmt.status === 'completed' && (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/20">
                              <CheckCircle2 className="h-3 w-3" />
                              Verified
                            </span>
                          )}
                          {stmt.status === 'requires_human_review' && (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-500/15 text-amber-400 border border-amber-500/20">
                              <AlertTriangle className="h-3 w-3" />
                              Review
                            </span>
                          )}
                          {stmt.status === 'processing' && (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-indigo-500/15 text-[#8B7CFF] border border-[#8B7CFF]/20 animate-pulse">
                              Processing
                            </span>
                          )}
                          {stmt.status === 'failed' && (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-rose-500/15 text-rose-400 border border-rose-500/20">
                              Failed
                            </span>
                          )}
                          {stmt.status === 'pending' && (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-white/[0.05] text-text-muted border border-white/10">
                              Queued
                            </span>
                          )}
                        </td>
                        <td className="py-3 px-3 text-right">
                          <div className="inline-flex items-center gap-1.5" onClick={(e) => e.stopPropagation()}>
                            {onDeleteStatement && (
                              <button
                                onClick={() => onDeleteStatement(stmt)}
                                title="Delete statement"
                                className="p-1.5 rounded-lg bg-white/[0.04] hover:bg-rose-500/20 text-text-muted hover:text-rose-400 border border-white/10 transition"
                              >
                                <Trash2 className="h-3 w-3" />
                              </button>
                            )}
                            {stmt.status !== 'processing' ? (
                              <button
                                onClick={(e) => onDownloadWorkbook(stmt, e)}
                                title="Download 5-Sheet Excel Workbook"
                                className="p-1.5 rounded-lg bg-white/[0.04] hover:bg-emerald-500/20 text-emerald-400 hover:text-emerald-300 border border-white/10 transition"
                              >
                                <Download className="h-3 w-3" />
                              </button>
                            ) : null}
                            <button
                              onClick={() => onSelectStatement(stmt)}
                              className="px-2.5 py-1 rounded-lg bg-white/[0.04] hover:bg-[#F15A43] hover:text-white text-text-secondary text-[11px] font-medium border border-white/10 transition flex items-center gap-1"
                            >
                              <span>View</span>
                              <ChevronRight className="h-3 w-3" />
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
        </div>
      </div>
    </div>
  );
};
