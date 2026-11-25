import React from 'react';
import { ShieldCheck, UploadCloud, LogOut, User as UserIcon, Activity, FileSpreadsheet } from 'lucide-react';
import { User, HealthStatus } from '../types';

interface NavbarProps {
  user: User | null;
  health: HealthStatus | null;
  onOpenUpload: () => void;
  onOpenAuth: () => void;
  onLogout: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  user,
  health,
  onOpenUpload,
  onOpenAuth,
  onLogout,
}) => {
  return (
    <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Brand */}
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-500 flex items-center justify-center shadow-lg shadow-indigo-500/20">
            <FileSpreadsheet className="h-5 w-5 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-lg font-bold tracking-tight text-white">SalaryLens AI</span>
              <span className="text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                CodeSec Enterprise
              </span>
            </div>
            <p className="text-xs text-slate-400">AI Bank Statement Salary Verification</p>
          </div>
        </div>

        {/* Center / Health status */}
        <div className="hidden md:flex items-center gap-2 px-3 py-1 rounded-full bg-slate-800/80 border border-slate-700/60 text-xs text-slate-300">
          <Activity className={`h-3.5 w-3.5 ${health?.status === 'ok' ? 'text-emerald-400 animate-pulse' : 'text-amber-400'}`} />
          <span>API: {health?.status === 'ok' ? 'Operational' : 'Connecting...'}</span>
          <span className="text-slate-500">•</span>
          <span className="text-slate-400 capitalize">{health?.environment || 'dev'}</span>
        </div>

        {/* Actions & User */}
        <div className="flex items-center gap-3">
          {user ? (
            <>
              <button
                onClick={onOpenUpload}
                className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium transition shadow-sm hover:shadow-indigo-500/25"
              >
                <UploadCloud className="h-4 w-4" />
                <span>Upload Statement</span>
              </button>

              <div className="flex items-center gap-3 pl-2 border-l border-slate-800">
                <div className="hidden sm:block text-right">
                  <div className="text-xs font-semibold text-slate-200">{user.full_name}</div>
                  <div className="text-[11px] text-slate-400">{user.organization_name} ({user.role})</div>
                </div>
                <button
                  onClick={onLogout}
                  title="Log out"
                  className="p-2 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-rose-400 transition"
                >
                  <LogOut className="h-4 w-4" />
                </button>
              </div>
            </>
          ) : (
            <button
              onClick={onOpenAuth}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium transition"
            >
              <UserIcon className="h-4 w-4" />
              <span>Sign In / Demo</span>
            </button>
          )}
        </div>
      </div>
    </header>
  );
};

