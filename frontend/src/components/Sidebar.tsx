import React from 'react';
import {
  LayoutDashboard,
  FileSpreadsheet,
  Users,
  BarChart3,
  ShieldCheck,
  Settings,
  HelpCircle,
  X,
} from 'lucide-react';

interface SidebarProps {
  currentTab: string;
  onSelectTab: (tab: string) => void;
  onOpenSettings?: () => void;
  onOpenHelp?: () => void;
  mobileOpen?: boolean;
  onCloseMobile?: () => void;
  ocrEngine?: string;
  activeModel?: string;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentTab,
  onSelectTab,
  onOpenSettings,
  onOpenHelp,
  mobileOpen = false,
  onCloseMobile,
  ocrEngine = 'hybrid_indra',
  activeModel = 'qwen2.5:1.5b',
}) => {
  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'statements', label: 'Statements', icon: FileSpreadsheet },
    { id: 'candidates', label: 'Candidates', icon: Users },
    { id: 'analytics', label: 'Analysis', icon: BarChart3 },
    { id: 'audit', label: 'Audit Logs', icon: ShieldCheck },
  ];

  const handleNavClick = (tabId: string) => {
    onSelectTab(tabId);
    if (onCloseMobile) onCloseMobile();
  };

  return (
    <>
      {/* Mobile Backdrop Overlay */}
      {mobileOpen && (
        <div
          onClick={onCloseMobile}
          className="fixed inset-0 bg-black/80 backdrop-blur-sm z-40 lg:hidden animate-in fade-in"
        />
      )}

      <aside
        className={`w-64 shrink-0 flex flex-col justify-between p-4 rounded-3xl glass-sidebar border border-white/[0.08] shadow-glass select-none transition-all duration-300 z-50 ${
          mobileOpen
            ? 'fixed top-4 bottom-4 left-4 flex'
            : 'hidden lg:flex sticky top-4 h-[calc(100vh-2rem)]'
        }`}
      >
        {/* Brand Header */}
        <div>
          <div className="flex items-center justify-between px-3 py-2 mb-6">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-2xl bg-gradient-to-br from-[#F15A43] to-[#d6412b] flex items-center justify-center shadow-glow-accent">
                <svg
                  className="w-5 h-5 text-white"
                  viewBox="0 0 24 24"
                  fill="currentColor"
                >
                  <circle cx="8" cy="8" r="3" />
                  <circle cx="16" cy="8" r="3" />
                  <circle cx="12" cy="16" r="3" />
                </svg>
              </div>
              <div>
                <div className="text-base font-bold text-white tracking-tight flex items-center gap-1.5">
                  <span>SalaryLens</span>
                </div>
                <span className="text-[10px] text-text-muted font-medium tracking-wide uppercase">
                  Financial AI Engine
                </span>
              </div>
            </div>

            {/* Mobile close button */}
            {mobileOpen && (
              <button
                onClick={onCloseMobile}
                className="lg:hidden p-1.5 rounded-lg text-text-muted hover:text-white"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>

          {/* Navigation list */}
          <nav className="space-y-1.5">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = currentTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => handleNavClick(item.id)}
                  className={`w-full flex items-center gap-3.5 px-4 py-3 rounded-2xl text-[13px] font-medium transition-all duration-200 text-left ${
                    isActive
                      ? 'bg-[#F15A43]/15 text-[#F15A43] font-semibold border border-[#F15A43]/20 shadow-[0_0_20px_rgba(241,90,67,0.15)]'
                      : 'text-text-secondary hover:text-text-primary hover:bg-white/[0.04]'
                  }`}
                >
                  <Icon
                    className={`h-4 w-4 transition-colors ${
                      isActive ? 'text-[#F15A43]' : 'text-text-muted group-hover:text-text-secondary'
                    }`}
                  />
                  <span>{item.label}</span>
                </button>
              );
            })}
          </nav>
        </div>

        {/* Footer Navigation */}
        <div className="pt-4 border-t border-white/[0.06] space-y-1">
          <button
            onClick={() => handleNavClick('settings')}
            className={`w-full flex items-center gap-3.5 px-4 py-2.5 rounded-2xl text-[13px] font-medium transition-all duration-200 text-left ${
              currentTab === 'settings'
                ? 'bg-[#F15A43]/15 text-[#F15A43] font-semibold border border-[#F15A43]/20'
                : 'text-text-secondary hover:text-text-primary hover:bg-white/[0.04]'
            }`}
          >
            <Settings className="h-4 w-4 text-text-muted" />
            <span>Settings</span>
          </button>
          <button
            onClick={() => handleNavClick('help')}
            className={`w-full flex items-center gap-3.5 px-4 py-2.5 rounded-2xl text-[13px] font-medium transition-all duration-200 text-left ${
              currentTab === 'help'
                ? 'bg-[#F15A43]/15 text-[#F15A43] font-semibold border border-[#F15A43]/20'
                : 'text-text-secondary hover:text-text-primary hover:bg-white/[0.04]'
            }`}
          >
            <HelpCircle className="h-4 w-4 text-text-muted" />
            <span>Help Center</span>
          </button>

          {/* Engine indicator pill */}
          <div
            onClick={() => handleNavClick('settings')}
            className="mt-4 p-3 rounded-2xl bg-white/[0.025] hover:bg-white/[0.05] border border-white/[0.05] hover:border-white/[0.12] text-[11px] text-text-muted flex items-center gap-2 cursor-pointer transition group"
            title="Configure OCR Engine and AI Models in Settings"
          >
            <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
            <div className="truncate">
              <span className="text-white font-medium block group-hover:text-[#F15A43] transition">
                {ocrEngine === 'hybrid_indra'
                  ? 'Indra OCR (Hybrid)'
                  : ocrEngine === 'indra'
                  ? 'Indra OCR (Full)'
                  : 'Native PyMuPDF'}
              </span>
              <span className="text-[10px] text-text-secondary truncate block">
                {activeModel || 'qwen2.5:1.5b'} • Metal GPU
              </span>
            </div>
          </div>
        </div>
      </aside>
    </>
  );
};
