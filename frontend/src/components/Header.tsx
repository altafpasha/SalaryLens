import React from 'react';
import {
  Search,
  Calendar,
  Bell,
  UploadCloud,
  LogOut,
  User as UserIcon,
  Activity,
  CheckCircle2,
  Menu,
} from 'lucide-react';
import { User, HealthStatus } from '../types';

interface HeaderProps {
  user: User | null;
  health: HealthStatus | null;
  searchQuery: string;
  onSearchChange: (q: string) => void;
  onOpenUpload: () => void;
  onOpenAuth: () => void;
  onLogout: () => void;
  onToggleMobileMenu?: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  user,
  health,
  searchQuery,
  onSearchChange,
  onOpenUpload,
  onOpenAuth,
  onLogout,
  onToggleMobileMenu,
}) => {
  const currentDate = new Date().toLocaleDateString('en-US', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });

  return (
    <header className="flex items-center justify-between gap-3 py-2">
      {/* Mobile Hamburger Menu Toggle */}
      <button
        onClick={onToggleMobileMenu}
        className="lg:hidden p-2 rounded-2xl bg-[#161616]/90 border border-white/[0.08] text-text-secondary hover:text-white shrink-0"
        aria-label="Toggle navigation"
      >
        <Menu className="h-4 w-4" />
      </button>

      {/* Search Bar - Pill shaped matching screenshot */}
      <div className="relative flex-1 max-w-md">
        <div className="flex items-center gap-2.5 px-4 py-2 rounded-full bg-[#161616]/90 border border-white/[0.08] shadow-inner text-xs text-text-secondary focus-within:border-[#F15A43]/50 focus-within:shadow-[0_0_15px_rgba(241,90,67,0.15)] transition-all">
          <Search className="h-4 w-4 text-text-muted shrink-0" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search statements, candidates, employers..."
            className="w-full bg-transparent border-none text-xs text-text-primary placeholder:text-text-muted focus:outline-none"
          />
        </div>
      </div>

      {/* Right Controls */}
      <div className="flex items-center gap-3">
        {/* Date Selector Pill */}
        <div className="hidden lg:flex items-center gap-2 px-3.5 py-2 rounded-full bg-[#161616]/80 border border-white/[0.08] text-xs text-text-secondary font-medium">
          <span>{currentDate}</span>
          <Calendar className="h-3.5 w-3.5 text-text-muted" />
        </div>

        {/* Live Health Status */}
        <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full bg-[#161616]/80 border border-white/[0.08] text-[11px] text-text-secondary">
          <span
            className={`h-2 w-2 rounded-full ${
              health?.status === 'healthy' || health?.status === 'ok'
                ? 'bg-emerald-400 animate-pulse'
                : 'bg-amber-400'
            }`}
          />
          <span className="font-medium">
            {health?.status === 'healthy' || health?.status === 'ok' ? 'Live API' : 'Connecting'}
          </span>
        </div>

        {/* Upload Statement Primary CTA */}
        {user && (
          <button
            onClick={onOpenUpload}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-gradient-to-r from-[#F15A43] to-[#e04832] hover:opacity-95 text-white text-xs font-semibold shadow-glow-accent transition-all duration-200 active:scale-95"
          >
            <UploadCloud className="h-3.5 w-3.5" />
            <span>Upload PDF</span>
          </button>
        )}

        {/* Notification Bell */}
        <div className="relative">
          <button
            title="Notifications"
            className="h-9 w-9 rounded-full bg-[#161616]/80 border border-white/[0.08] flex items-center justify-center text-text-muted hover:text-text-primary hover:border-white/20 transition"
          >
            <Bell className="h-4 w-4" />
            <span className="absolute top-1.5 right-1.5 h-2 w-2 rounded-full bg-[#F15A43]" />
          </button>
        </div>

        {/* User Avatar & Info */}
        {user ? (
          <div className="flex items-center gap-2 pl-1">
            <div className="h-9 w-9 rounded-full bg-gradient-to-tr from-[#F15A43] to-[#8B7CFF] p-[1px] shadow-sm">
              <div className="h-full w-full rounded-full bg-[#161616] flex items-center justify-center text-xs font-bold text-white uppercase">
                {user.full_name ? user.full_name.slice(0, 2) : 'SA'}
              </div>
            </div>
            <button
              onClick={onLogout}
              title="Sign Out"
              className="h-9 w-9 rounded-full bg-[#161616]/80 border border-white/[0.08] flex items-center justify-center text-text-muted hover:text-rose-400 hover:border-rose-500/30 transition"
            >
              <LogOut className="h-3.5 w-3.5" />
            </button>
          </div>
        ) : (
          <button
            onClick={onOpenAuth}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-[#161616] border border-white/[0.12] hover:border-[#F15A43]/50 text-text-primary text-xs font-medium transition"
          >
            <UserIcon className="h-3.5 w-3.5 text-[#F15A43]" />
            <span>Sign In / Demo</span>
          </button>
        )}
      </div>
    </header>
  );
};

