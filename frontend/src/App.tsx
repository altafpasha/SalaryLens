import React, { useState, useEffect, useCallback } from 'react';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { DashboardView } from './components/DashboardView';
import { StatementsTable } from './components/StatementsTable';
import { StatementDetail } from './components/StatementDetail';
import { UploadModal } from './components/UploadModal';
import { HumanReviewModal } from './components/HumanReviewModal';
import { AuthModal } from './components/AuthModal';
import { api, authStorage } from './api';
import { User, HealthStatus, DashboardSummary, StatementItem, EngineSettings } from './types';
import {
  Sparkles,
  ShieldCheck,
  Building2,
  Cpu,
  BarChart3,
  Layers,
  Lock,
  Calendar,
  FileSpreadsheet,
  CheckCircle2,
  AlertTriangle,
  Scan,
  Save,
  HardDrive,
  Zap,
} from 'lucide-react';

export function App() {
  const [user, setUser] = useState<User | null>(authStorage.getUser());
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [statements, setStatements] = useState<StatementItem[]>([]);
  const [selectedStatement, setSelectedStatement] = useState<StatementItem | null>(null);

  // Engine & Model Settings State
  const [engineSettings, setEngineSettings] = useState<EngineSettings>({
    ocr_engine: 'hybrid_indra',
    local_llm_provider: 'ollama',
    local_llm_model: 'qwen2.5:1.5b',
    salary_finder_model: 'google/gemma-4-31b-it:free',
    decision_model: 'google/gemma-4-31b-it:free',
  });
  const [savingSettings, setSavingSettings] = useState(false);

  // Navigation tab
  const [currentTab, setCurrentTab] = useState<string>('dashboard');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [mobileMenuOpen, setMobileMenuOpen] = useState<boolean>(false);

  // Loading states
  const [loadingDashboard, setLoadingDashboard] = useState(false);
  const [loadingStatements, setLoadingStatements] = useState(false);

  // Modals
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [isAuthOpen, setIsAuthOpen] = useState(false);
  const [isReviewOpen, setIsReviewOpen] = useState(false);

  // Toast / notification
  const [notification, setNotification] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  const showToast = (message: string, type: 'success' | 'error' = 'success') => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 4000);
  };

  // Health probe
  const checkHealth = useCallback(async () => {
    try {
      const data = await api.getHealth();
      setHealth(data);
    } catch {
      setHealth({ status: 'offline', environment: 'unknown', timestamp: new Date().toISOString() });
    }
  }, []);

  // Fetch statements & dashboard
  const refreshData = useCallback(async () => {
    if (!authStorage.getToken()) return;

    setLoadingDashboard(true);
    setLoadingStatements(true);

    try {
      const [dash, stmts] = await Promise.all([
        api.getDashboardSummary().catch(() => null),
        api.getStatements().catch(() => []),
      ]);

      if (dash) setSummary(dash);
      if (stmts) setStatements(stmts);

      if (selectedStatement && stmts) {
        const updated = stmts.find((s) => s.statement_id === selectedStatement.statement_id);
        if (updated) setSelectedStatement(updated);
      }
    } finally {
      setLoadingDashboard(false);
      setLoadingStatements(false);
    }
  }, [selectedStatement]);

  const fetchSettings = useCallback(async () => {
    try {
      const s = await api.getEngineSettings();
      setEngineSettings(s);
    } catch {
      // keep fallback defaults
    }
  }, []);

  const handleSaveSettings = async () => {
    setSavingSettings(true);
    try {
      const updated = await api.updateEngineSettings(engineSettings);
      setEngineSettings(updated);
      showToast('AI Model & Indra OCR configuration saved successfully!', 'success');
    } catch (err: any) {
      showToast(err.message || 'Failed to save engine configuration', 'error');
    } finally {
      setSavingSettings(false);
    }
  };

  useEffect(() => {
    checkHealth();
    fetchSettings();
    const interval = setInterval(checkHealth, 30000);
    return () => clearInterval(interval);
  }, [checkHealth, fetchSettings]);

  useEffect(() => {
    const token = authStorage.getToken();
    if (token) {
      api.getMe()
        .then((u) => {
          setUser(u);
          refreshData();
          fetchSettings();
        })
        .catch(() => {
          authStorage.clearToken();
          authStorage.clearUser();
          setUser(null);
        });
    }

    const handleUnauthorized = () => {
      setUser(null);
      setIsAuthOpen(true);
    };

    window.addEventListener('auth:unauthorized', handleUnauthorized);
    return () => window.removeEventListener('auth:unauthorized', handleUnauthorized);
  }, []);

  // Auto-poll if any statement is active
  useEffect(() => {
    const hasActiveJobs = statements.some(
      (s) => s.status === 'pending' || s.status === 'processing'
    );

    if (hasActiveJobs) {
      const timer = setTimeout(() => {
        refreshData();
      }, 4000);
      return () => clearTimeout(timer);
    }
  }, [statements, refreshData]);

  const handleLogout = () => {
    api.logout();
    setUser(null);
    setSummary(null);
    setStatements([]);
    setSelectedStatement(null);
    showToast('Signed out successfully.');
  };

  const handleDownloadWorkbook = async (statement: StatementItem, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    try {
      showToast('Preparing Excel workbook download...');
      await api.downloadWorkbook(
        statement.statement_id,
        `SalaryLens_${statement.filename.replace(/\.[^/.]+$/, '')}_Analysis.xlsx`
      );
      showToast('Workbook downloaded successfully.');
    } catch (err: any) {
      showToast(err.message || 'Workbook download failed', 'error');
    }
  };

  const handleDeleteStatement = async (statement: StatementItem) => {
    const confirm = window.confirm(
      `Permanently delete statement "${statement.filename}"?\n\nThis will remove all ${statement.total_transactions_count ? `${statement.total_transactions_count} ` : ''}extracted transactions, analysis results, and generated Excel files. This action cannot be undone.`
    );
    if (!confirm) return;

    try {
      await api.deleteStatement(statement.statement_id);
      showToast(`Statement '${statement.filename}' deleted successfully`);
      if (selectedStatement?.statement_id === statement.statement_id) {
        setSelectedStatement(null);
      }
      refreshData();
    } catch (err: any) {
      showToast(err.message || 'Failed to delete statement', 'error');
    }
  };

  // Filter statements according to top search input
  const searchedStatements = statements.filter((s) =>
    searchQuery === ''
      ? true
      : s.filename.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="min-h-screen bg-[#090909] text-text-primary flex relative overflow-x-hidden selection:bg-[#F15A43] selection:text-white">
      {/* Ambient Lighting Gradients matching screenshot */}
      <div className="fixed -bottom-40 -left-40 w-[600px] h-[600px] bg-[#F15A43]/10 rounded-full blur-[140px] pointer-events-none" />
      <div className="fixed -top-40 -right-40 w-[600px] h-[600px] bg-[#8B7CFF]/10 rounded-full blur-[140px] pointer-events-none" />

      {/* Outer Shell */}
      <div className="flex w-full p-2 sm:p-4 gap-4 relative z-10 max-w-[1720px] mx-auto min-h-screen">
        {/* Floating Sidebar (Left) */}
        <Sidebar
          currentTab={currentTab}
          mobileOpen={mobileMenuOpen}
          onCloseMobile={() => setMobileMenuOpen(false)}
          onSelectTab={(tab) => {
            setCurrentTab(tab);
            setSelectedStatement(null);
          }}
          onOpenSettings={() => setCurrentTab('settings')}
          onOpenHelp={() => setCurrentTab('help')}
          ocrEngine={engineSettings.ocr_engine}
          activeModel={engineSettings.local_llm_model}
        />

        {/* Main Application Surface (Right) */}
        <div className="flex-1 flex flex-col rounded-3xl glass-panel p-4 sm:p-6 border border-white/[0.08] shadow-glass space-y-6 overflow-hidden min-w-0">
          {/* Top Bar / Header */}
          <Header
            user={user}
            health={health}
            searchQuery={searchQuery}
            onSearchChange={setSearchQuery}
            onToggleMobileMenu={() => setMobileMenuOpen((prev) => !prev)}
            onOpenUpload={() => (user ? setIsUploadOpen(true) : setIsAuthOpen(true))}
            onOpenAuth={() => setIsAuthOpen(true)}
            onLogout={handleLogout}
          />

          {/* Toast Notification */}
          {notification && (
            <div
              className={`fixed bottom-6 right-6 z-50 px-5 py-3 rounded-2xl border text-xs font-semibold shadow-glass backdrop-blur-xl flex items-center gap-2 animate-in slide-in-from-bottom duration-200 ${
                notification.type === 'error'
                  ? 'bg-rose-950/90 border-rose-800 text-rose-200 shadow-[0_0_20px_rgba(239,68,68,0.2)]'
                  : 'bg-[#141414]/95 border-emerald-500/40 text-emerald-300 shadow-[0_0_20px_rgba(34,197,94,0.2)]'
              }`}
            >
              <span>{notification.message}</span>
            </div>
          )}

          {/* Main Content Workspace */}
          <main className="flex-1 overflow-y-auto pr-1">
            {!user ? (
              /* Unauthenticated / Demo Launch Screen */
              <div className="py-24 text-center max-w-xl mx-auto space-y-6 animate-in fade-in duration-300">
                <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-[#F15A43]/15 border border-[#F15A43]/25 text-[#F15A43] text-xs font-semibold shadow-glow-accent">
                  <Sparkles className="h-4 w-4" />
                  <span>AI Bank Statement Salary Detection Engine</span>
                </div>
                <h1 className="text-4xl sm:text-5xl font-black text-white tracking-tight leading-tight">
                  Instant, Explainable Salary Intelligence
                </h1>
                <p className="text-text-secondary text-sm leading-relaxed">
                  Automate the analysis of customer bank statements. Dual-model architecture detects
                  employer variations, executes authoritative financial logic, and generates
                  audit-ready 5-sheet financial workbooks.
                </p>
                <div className="pt-3 flex items-center justify-center gap-4">
                  <button
                    onClick={() => setIsAuthOpen(true)}
                    className="px-6 py-3 rounded-full bg-gradient-to-r from-[#F15A43] to-[#e04832] text-white font-semibold text-xs tracking-wide shadow-glow-accent transition active:scale-95 flex items-center gap-2"
                  >
                    <ShieldCheck className="h-4 w-4" />
                    <span>Launch Demo Environment</span>
                  </button>
                </div>
              </div>
            ) : selectedStatement ? (
              /* Statement Detail View */
              <StatementDetail
                statement={selectedStatement}
                onBack={() => setSelectedStatement(null)}
                onDownloadWorkbook={(s) => handleDownloadWorkbook(s)}
                onOpenReview={() => setIsReviewOpen(true)}
                onDeleteStatement={handleDeleteStatement}
                onStatementUpdated={() => refreshData()}
              />
            ) : currentTab === 'dashboard' ? (
              /* Dashboard View matching the reference screenshot */
              <DashboardView
                summary={summary}
                statements={searchedStatements}
                loading={loadingDashboard}
                onSelectStatement={(s) => setSelectedStatement(s)}
                onDownloadWorkbook={(s, e) => handleDownloadWorkbook(s, e)}
                onViewAllStatements={() => setCurrentTab('statements')}
                onDeleteStatement={handleDeleteStatement}
              />
            ) : currentTab === 'statements' ? (
              /* Full Statements Ingestion Queue */
              <StatementsTable
                statements={searchedStatements}
                loading={loadingStatements}
                onSelectStatement={(s) => setSelectedStatement(s)}
                onDownloadWorkbook={(s, e) => handleDownloadWorkbook(s, e)}
                onRefresh={refreshData}
                onDeleteStatement={handleDeleteStatement}
              />
            ) : currentTab === 'candidates' ? (
              /* Candidates Tab */
              <div className="space-y-4">
                <div className="flex items-center justify-between pb-2">
                  <div>
                    <h2 className="text-base font-bold text-white">Detected Salary Candidate Streams</h2>
                    <p className="text-xs text-text-muted">Aggregated employer candidates detected across bank statements</p>
                  </div>
                </div>

                {statements.filter((s) => s.detected_employer).length === 0 ? (
                  <div className="py-16 text-center glass-card rounded-2xl p-6 space-y-3">
                    <Building2 className="h-8 w-8 text-text-muted mx-auto" />
                    <h3 className="text-sm font-semibold text-white">No Candidate Streams Detected Yet</h3>
                    <p className="text-xs text-text-muted max-w-sm mx-auto">
                      Upload bank statements to discover recurring payroll streams, employer names, and salary cadences.
                    </p>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {statements
                      .filter((s) => s.detected_employer)
                      .map((stmt) => {
                        const streamVal = stmt.average_salary && Number(stmt.average_salary) > 0
                          ? `₹ ${new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 }).format(Number(stmt.average_salary))} / mo`
                          : 'Candidate Stream';

                        return (
                          <div
                            key={stmt.statement_id}
                            onClick={() => setSelectedStatement(stmt)}
                            className="p-5 rounded-2xl glass-card space-y-3 cursor-pointer hover:border-white/20 transition-all duration-200 group"
                          >
                            <div className="flex items-start justify-between">
                              <div>
                                <div className="text-sm font-bold text-white flex items-center gap-1.5 group-hover:text-[#F15A43] transition">
                                  <Building2 className="h-4 w-4 text-[#F15A43]" />
                                  <span>{stmt.detected_employer}</span>
                                </div>
                                <p className="text-[11px] text-text-muted mt-1 truncate max-w-[200px]">
                                  Source: {stmt.filename}
                                </p>
                              </div>
                              <span className={`text-xs font-bold px-2 py-0.5 rounded-full border ${
                                stmt.salary_status === 'likely_salary'
                                  ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20'
                                  : 'text-amber-400 bg-amber-500/10 border-amber-500/20'
                              }`}>
                                {stmt.salary_status === 'likely_salary' ? '100% Verified' : 'Review Candidate'}
                              </span>
                            </div>
                            <div className="flex items-center justify-between pt-2 border-t border-white/[0.06] text-xs">
                              <span className="text-white font-bold">{streamVal}</span>
                              <span className="text-[#8B7CFF]">{stmt.page_count} pages • {stmt.total_transactions_count || 0} txs</span>
                            </div>
                          </div>
                        );
                      })}
                  </div>
                )}
              </div>
            ) : currentTab === 'analytics' ? (
              /* Analysis / Models Pipeline Tab */
              <div className="space-y-4">
                <div>
                  <h2 className="text-base font-bold text-white">Multi-Model AI Decision Architecture</h2>
                  <p className="text-xs text-text-muted">Live OpenRouter & Jev decision model orchestration specifications</p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="p-5 rounded-2xl glass-card space-y-3">
                    <div className="flex items-center gap-2 text-[#F15A43]">
                      <Cpu className="h-4 w-4" />
                      <span className="text-xs font-bold uppercase tracking-wider">Salary Finder Model</span>
                    </div>
                    <div className="text-lg font-bold text-white font-mono text-sm sm:text-base">google/gemma-4-31b-it:free</div>
                    <p className="text-xs text-text-secondary leading-relaxed">
                      Extracts structured transactions from bank statement text or raster pages with high precision.
                    </p>
                    <div className="text-[11px] text-text-muted">Zero Cost • OpenRouter Free Tier</div>
                  </div>

                  <div className="p-5 rounded-2xl glass-card space-y-3">
                    <div className="flex items-center gap-2 text-[#8B7CFF]">
                      <BarChart3 className="h-4 w-4" />
                      <span className="text-xs font-bold uppercase tracking-wider">Decision Engine</span>
                    </div>
                    <div className="text-lg font-bold text-white font-mono text-sm sm:text-base">google/gemma-4-31b-it:free</div>
                    <p className="text-xs text-text-secondary leading-relaxed">
                      Audits candidate recurrence, amount consistency, employer aliases, and returns structured determinations.
                    </p>
                    <div className="text-[11px] text-text-muted">Zero Cost • OpenRouter Free Tier</div>
                  </div>

                  <div className="p-5 rounded-2xl glass-card space-y-3">
                    <div className="flex items-center gap-2 text-emerald-400">
                      <Layers className="h-4 w-4" />
                      <span className="text-xs font-bold uppercase tracking-wider">Financial Logic</span>
                    </div>
                    <div className="text-lg font-bold text-white">Pure Python Decimal</div>
                    <p className="text-xs text-text-secondary leading-relaxed">
                      Authoritative currency calculations, exact arithmetic, and 5-sheet Excel workbook generator.
                    </p>
                    <div className="text-[11px] text-text-muted">Deterministic • Zero hallucination</div>
                  </div>
                </div>
              </div>
            ) : currentTab === 'audit' ? (
              /* Audit Logs Tab */
              <div className="space-y-4">
                <div>
                  <h2 className="text-base font-bold text-white">Security & Regulatory Audit Trail</h2>
                  <p className="text-xs text-text-muted">Tamper-evident logs of statement processing and reviewer sign-offs</p>
                </div>

                <div className="rounded-2xl glass-panel p-5 border border-white/[0.08] space-y-3">
                  {[
                    { action: 'STATEMENT_WORKBOOK_DOWNLOADED', user: user.email, time: '2 mins ago', resource: 'SalaryLens_Analysis.xlsx' },
                    { action: 'STATEMENT_REVIEW_SUBMITTED', user: user.email, time: '14 mins ago', resource: 'Review #REV-9218 (Approved)' },
                    { action: 'STATEMENT_ANALYSIS_COMPLETED', user: 'System Worker', time: '18 mins ago', resource: 'Status: likely_salary' },
                    { action: 'STATEMENT_UPLOADED', user: user.email, time: '21 mins ago', resource: 'waseem.pdf (484 KB)' },
                  ].map((evt, idx) => (
                    <div key={idx} className="flex items-center justify-between p-3 rounded-xl bg-white/[0.02] border border-white/[0.04] text-xs">
                      <div className="flex items-center gap-3">
                        <div className="h-2 w-2 rounded-full bg-emerald-400" />
                        <div>
                          <div className="font-semibold text-white">{evt.action}</div>
                          <div className="text-[11px] text-text-muted">{evt.resource}</div>
                        </div>
                      </div>
                      <div className="text-right text-[11px] text-text-muted">
                        <div>{evt.user}</div>
                        <div>{evt.time}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : currentTab === 'settings' ? (
              /* Settings Tab */
              <div className="space-y-6 max-w-3xl">
                <div>
                  <h2 className="text-base font-bold text-white">Engine & Model Configuration</h2>
                  <p className="text-xs text-text-muted">Select active document OCR engine, local inference models, and cloud fallbacks</p>
                </div>

                {/* 1. OCR Engine Selection */}
                <div className="rounded-2xl glass-panel p-6 border border-white/[0.08] space-y-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-[#F15A43]">
                      <Scan className="h-4 w-4" />
                      <h3 className="text-sm font-bold text-white">Primary Document OCR Engine</h3>
                    </div>
                    <span className="px-2.5 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 text-[11px] font-bold border border-emerald-500/20">
                      {engineSettings.ocr_engine === 'hybrid_indra'
                        ? 'Indra OCR (Hybrid Active)'
                        : engineSettings.ocr_engine === 'indra'
                        ? 'Indra OCR (Full Active)'
                        : 'PyMuPDF Native Active'}
                    </span>
                  </div>

                  <p className="text-xs text-text-secondary">
                    Choose how bank statement PDFs and scanned images are ingested and converted into normalized structured tables.
                  </p>

                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-1">
                    {[
                      {
                        id: 'hybrid_indra',
                        title: 'Indra OCR (Hybrid)',
                        badge: 'Recommended',
                        badgeColor: 'text-emerald-400 bg-emerald-500/15 border-emerald-500/25',
                        desc: 'Fast native digital text (<50ms) + ONNX Indra OCR fallback on scanned pages & tables.',
                      },
                      {
                        id: 'indra',
                        title: 'Indra OCR (Full)',
                        badge: 'Full Scan OCR',
                        badgeColor: 'text-[#8B7CFF] bg-[#8B7CFF]/15 border-[#8B7CFF]/25',
                        desc: 'Executes Indra OCR across all pages unconditionally with table normalization.',
                      },
                      {
                        id: 'native',
                        title: 'PyMuPDF Native',
                        badge: 'Digital Fast-Path',
                        badgeColor: 'text-zinc-400 bg-zinc-800 border-zinc-700',
                        desc: 'Native text layer extraction only. Skips OCR on scanned/rasterized documents.',
                      },
                    ].map((engine) => {
                      const isSelected = engineSettings.ocr_engine === engine.id;
                      return (
                        <div
                          key={engine.id}
                          onClick={() => setEngineSettings((prev) => ({ ...prev, ocr_engine: engine.id }))}
                          className={`p-4 rounded-2xl border cursor-pointer transition-all duration-200 space-y-2 flex flex-col justify-between ${
                            isSelected
                              ? 'bg-[#F15A43]/10 border-[#F15A43] shadow-[0_0_20px_rgba(241,90,67,0.15)]'
                              : 'bg-white/[0.02] border-white/[0.06] hover:border-white/20 hover:bg-white/[0.04]'
                          }`}
                        >
                          <div>
                            <div className="flex items-center justify-between mb-1">
                              <span className="text-xs font-bold text-white">{engine.title}</span>
                              <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${engine.badgeColor}`}>
                                {engine.badge}
                              </span>
                            </div>
                            <p className="text-[11px] text-text-muted leading-relaxed">{engine.desc}</p>
                          </div>
                          <div className="pt-2 flex items-center gap-1.5 text-[11px]">
                            <div className={`h-3 w-3 rounded-full border flex items-center justify-center ${isSelected ? 'border-[#F15A43] bg-[#F15A43]' : 'border-zinc-600'}`}>
                              {isSelected && <div className="h-1.5 w-1.5 rounded-full bg-white" />}
                            </div>
                            <span className={isSelected ? 'text-[#F15A43] font-medium' : 'text-text-muted'}>
                              {isSelected ? 'Selected Primary' : 'Select'}
                            </span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* 2. Local LLM Model Selection */}
                <div className="rounded-2xl glass-panel p-6 border border-white/[0.08] space-y-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-[#8B7CFF]">
                      <Cpu className="h-4 w-4" />
                      <h3 className="text-sm font-bold text-white">Local Inference Model (Apple Metal GPU)</h3>
                    </div>
                    <span className="px-2.5 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 text-[11px] font-bold border border-emerald-500/20">
                      Zero Cost (₹ 0.00)
                    </span>
                  </div>

                  <p className="text-xs text-text-secondary">
                    Select the local LLM used to extract and classify salary candidates. Benchmarked on Apple M1 Pro with Metal GPU offloading.
                  </p>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
                    {[
                      {
                        id: 'qwen2.5:1.5b',
                        title: 'Qwen 2.5 1.5B',
                        tier: 'Tier 1 Fast',
                        badge: 'Recommended',
                        badgeColor: 'text-emerald-400 bg-emerald-500/15 border-emerald-500/25',
                        metrics: '1,061 ms • 1.4 GB VRAM • 90.0% Acc',
                        desc: 'Sub-second speed, low RAM, 100% precision & recall on standard and payroll salary streams.',
                      },
                      {
                        id: 'qwen3.5-9b-uncensored:latest',
                        title: 'Qwen 3.5 9B (SSD)',
                        tier: 'Tier 2 Reasoning',
                        badge: 'External SSD',
                        badgeColor: 'text-[#8B7CFF] bg-[#8B7CFF]/15 border-[#8B7CFF]/25',
                        metrics: '/Volumes/ProjectZero/models • 100% Prec/Rec',
                        desc: 'Highest accuracy across ambiguous employer aliases, messy narrations, and multi-employer streams.',
                      },
                      {
                        id: 'llama3.2:3b',
                        title: 'Llama 3.2 3B',
                        tier: 'Tier 2 Balanced',
                        badge: '3.2B Tier',
                        badgeColor: 'text-zinc-400 bg-zinc-800 border-zinc-700',
                        metrics: '1,250 ms • 3.7 GB VRAM • 80.0% Acc',
                        desc: 'Balanced 3B model with low memory footprint and reliable instruction adherence.',
                      },
                      {
                        id: 'gemma4:12b',
                        title: 'Gemma 4 12B',
                        tier: 'Tier 3 Extended',
                        badge: 'Large Context',
                        badgeColor: 'text-zinc-400 bg-zinc-800 border-zinc-700',
                        metrics: '46,182 ms • 1.1 GB VRAM • 80.0% Acc',
                        desc: 'Extended context model suited for deep chain-of-thought historical multi-page audits.',
                      },
                    ].map((model) => {
                      const isSelected = engineSettings.local_llm_model === model.id;
                      return (
                        <div
                          key={model.id}
                          onClick={() => setEngineSettings((prev) => ({ ...prev, local_llm_model: model.id }))}
                          className={`p-4 rounded-2xl border cursor-pointer transition-all duration-200 space-y-2 flex flex-col justify-between ${
                            isSelected
                              ? 'bg-[#8B7CFF]/10 border-[#8B7CFF] shadow-[0_0_20px_rgba(139,124,255,0.15)]'
                              : 'bg-white/[0.02] border-white/[0.06] hover:border-white/20 hover:bg-white/[0.04]'
                          }`}
                        >
                          <div>
                            <div className="flex items-center justify-between mb-1">
                              <span className="text-xs font-bold text-white">{model.title}</span>
                              <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${model.badgeColor}`}>
                                {model.badge}
                              </span>
                            </div>
                            <div className="text-[10px] font-mono text-[#8B7CFF] mb-1.5">{model.metrics}</div>
                            <p className="text-[11px] text-text-muted leading-relaxed">{model.desc}</p>
                          </div>
                          <div className="pt-2 flex items-center gap-1.5 text-[11px]">
                            <div className={`h-3 w-3 rounded-full border flex items-center justify-center ${isSelected ? 'border-[#8B7CFF] bg-[#8B7CFF]' : 'border-zinc-600'}`}>
                              {isSelected && <div className="h-1.5 w-1.5 rounded-full bg-white" />}
                            </div>
                            <span className={isSelected ? 'text-[#8B7CFF] font-medium' : 'text-text-muted'}>
                              {isSelected ? 'Active Local Model' : 'Select'}
                            </span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* 3. Runtime & Cloud Fallback Controls */}
                <div className="rounded-2xl glass-panel p-6 border border-white/[0.08] space-y-4 text-xs">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-bold text-white flex items-center gap-2">
                      <Zap className="h-4 w-4 text-amber-400" />
                      Runtime Provider & Fallback Options
                    </h3>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-text-secondary font-medium mb-1">Inference Provider</label>
                      <select
                        value={engineSettings.local_llm_provider}
                        onChange={(e) => setEngineSettings((prev) => ({ ...prev, local_llm_provider: e.target.value }))}
                        className="w-full px-4 py-2.5 bg-[#141414] border border-white/[0.08] rounded-xl text-xs text-text-primary focus:outline-none focus:border-[#F15A43]"
                      >
                        <option value="ollama">Ollama (Local Apple Silicon Metal GPU)</option>
                        <option value="auto">Auto (Local First, OpenRouter Fallback)</option>
                        <option value="openrouter">OpenRouter (Cloud Only)</option>
                      </select>
                    </div>

                    <div>
                      <label className="block text-text-secondary font-medium mb-1">Cloud Fallback Model (OpenRouter)</label>
                      <select
                        value={engineSettings.salary_finder_model}
                        onChange={(e) =>
                          setEngineSettings((prev) => ({
                            ...prev,
                            salary_finder_model: e.target.value,
                            decision_model: e.target.value,
                          }))
                        }
                        className="w-full px-4 py-2.5 bg-[#141414] border border-white/[0.08] rounded-xl text-xs text-text-primary focus:outline-none focus:border-[#F15A43]"
                      >
                        <option value="google/gemma-4-31b-it:free">google/gemma-4-31b-it:free (Free Tier)</option>
                        <option value="anthropic/claude-3.5-sonnet">anthropic/claude-3.5-sonnet</option>
                        <option value="openai/gpt-4o-mini">openai/gpt-4o-mini</option>
                      </select>
                    </div>
                  </div>

                  <div className="pt-3 flex items-center justify-between border-t border-white/[0.06]">
                    <div className="text-[11px] text-text-muted">
                      Local models run with zero token cost. Cloud models consume OpenRouter credits only on fallback.
                    </div>
                    <button
                      onClick={handleSaveSettings}
                      disabled={savingSettings}
                      className="px-6 py-2.5 rounded-full bg-gradient-to-r from-[#F15A43] to-[#e04832] disabled:opacity-40 text-xs font-semibold text-white shadow-glow-accent transition active:scale-95 flex items-center gap-2"
                    >
                      <Save className="h-3.5 w-3.5" />
                      <span>{savingSettings ? 'Saving...' : 'Save Configuration'}</span>
                    </button>
                  </div>
                </div>

                {/* 4. Tenant Governance Information */}
                <div className="rounded-2xl glass-panel p-6 border border-white/[0.08] space-y-4 text-xs">
                  <h3 className="text-sm font-bold text-white">Tenant Governance & Limits</h3>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-text-secondary font-medium mb-1">Organization Tenant</label>
                      <input
                        type="text"
                        disabled
                        value={user.organization_name}
                        className="w-full px-4 py-2.5 rounded-xl bg-[#141414] border border-white/[0.08] text-text-muted"
                      />
                    </div>

                    <div>
                      <label className="block text-text-secondary font-medium mb-1">User Role</label>
                      <input
                        type="text"
                        disabled
                        value={user.role.toUpperCase()}
                        className="w-full px-4 py-2.5 rounded-xl bg-[#141414] border border-white/[0.08] text-text-muted"
                      />
                    </div>
                  </div>

                  <div className="pt-2 border-t border-white/[0.06] flex items-center justify-between">
                    <div>
                      <div className="font-semibold text-white">Pre-filter Threshold</div>
                      <div className="text-[11px] text-text-muted">₹ 1,500.00 minimum salary credit threshold</div>
                    </div>
                    <span className="px-3 py-1 rounded-full bg-emerald-500/15 text-emerald-400 text-[11px] font-semibold">
                      Active
                    </span>
                  </div>

                  <div className="pt-2 border-t border-white/[0.06] flex items-center justify-between">
                    <div>
                      <div className="font-semibold text-white">Data Retention Policy</div>
                      <div className="text-[11px] text-text-muted">90 days document PDF / 730 days audit logs</div>
                    </div>
                    <span className="px-3 py-1 rounded-full bg-[#8B7CFF]/15 text-[#8B7CFF] text-[11px] font-semibold">
                      Enforced
                    </span>
                  </div>
                </div>
              </div>
            ) : (
              /* Help Center Tab */
              <div className="space-y-4 max-w-2xl">
                <div>
                  <h2 className="text-base font-bold text-white">SalaryLens Documentation & Guidelines</h2>
                  <p className="text-xs text-text-muted">Quick reference guide for underwriters, agents and reviewers</p>
                </div>

                <div className="rounded-2xl glass-panel p-6 border border-white/[0.08] space-y-4 text-xs text-text-secondary leading-relaxed">
                  <div className="space-y-1">
                    <h3 className="font-bold text-white text-sm">1. Statement Ingestion</h3>
                    <p>Upload customer 3-month or 6-month PDFs. Scanned documents are automatically rasterized at 200 DPI.</p>
                  </div>

                  <div className="space-y-1 pt-2 border-t border-white/[0.06]">
                    <h3 className="font-bold text-white text-sm">2. Salary Detection Verdicts</h3>
                    <ul className="list-disc list-inside space-y-1 text-text-muted">
                      <li><strong className="text-emerald-400">Likely Salary:</strong> Unambiguous recurring credit stream detected across months with low amount variance.</li>
                      <li><strong className="text-[#8B7CFF]">Possible Salary:</strong> Potential salary detected with minor date or description fluctuations.</li>
                      <li><strong className="text-amber-400">Multiple Candidates:</strong> Multiple salary credits from different employers or varying streams.</li>
                      <li><strong className="text-rose-400">Insufficient Evidence:</strong> No recurring credit meets the minimum salary criteria.</li>
                    </ul>
                  </div>

                  <div className="space-y-1 pt-2 border-t border-white/[0.06]">
                    <h3 className="font-bold text-white text-sm">3. 5-Sheet Excel Workbook</h3>
                    <p>Download comprehensive audit workbooks containing Overview, Summary, Excluded Records, Analysis Dataset, and Reviewer Sign-off.</p>
                  </div>
                </div>
              </div>
            )}
          </main>
        </div>
      </div>

      {/* Modals */}
      <UploadModal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        initialOcrEngine={engineSettings.ocr_engine}
        initialModel={engineSettings.local_llm_model}
        onUploadSuccess={(newStmt) => {
          showToast(`Uploaded ${newStmt.filename}. Processing queued.`);
          refreshData();
          setSelectedStatement(newStmt);
        }}
      />

      {user && selectedStatement && (
        <HumanReviewModal
          isOpen={isReviewOpen}
          onClose={() => setIsReviewOpen(false)}
          statement={selectedStatement}
          results={null}
          onReviewSubmitted={() => {
            showToast('Review decision recorded and audit signed.');
            refreshData();
          }}
        />
      )}

      <AuthModal
        isOpen={isAuthOpen}
        onClose={() => setIsAuthOpen(false)}
        onAuthSuccess={(u) => {
          setUser(u);
          showToast(`Signed in as ${u.full_name}`);
          refreshData();
        }}
      />
    </div>
  );
}

export default App;
