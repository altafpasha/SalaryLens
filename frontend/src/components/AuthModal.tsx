import React, { useState } from 'react';
import { X, Lock, Mail, User, Building, Sparkles, Loader2, AlertCircle } from 'lucide-react';
import { api } from '../api';
import { User as UserType } from '../types';

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  onAuthSuccess: (user: UserType) => void;
}

export const AuthModal: React.FC<AuthModalProps> = ({ isOpen, onClose, onAuthSuccess }) => {
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState('demo@salarylens.ai');
  const [password, setPassword] = useState('Password123!');
  const [fullName, setFullName] = useState('Altaf Pasha');
  const [orgName, setOrgName] = useState('CodeSec Global Capital');
  const [role, setRole] = useState('admin');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleDemoLogin = async () => {
    setLoading(true);
    setError(null);
    try {
      try {
        await api.login({ email: 'demo@salarylens.ai', password: 'Password123!' });
      } catch {
        await api.register({
          email: 'demo@salarylens.ai',
          password: 'Password123!',
          full_name: 'Demo Reviewer',
          organization_name: 'CodeSec Financial Services',
          role: 'admin',
        });
      }
      const user = await api.getMe();
      onAuthSuccess(user);
      onClose();
    } catch (err: any) {
      setError(err.message || 'Demo sign-in failed');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      if (isRegister) {
        await api.register({
          email,
          password,
          full_name: fullName,
          organization_name: orgName,
          role,
        });
      } else {
        await api.login({ email, password });
      }
      const user = await api.getMe();
      onAuthSuccess(user);
      onClose();
    } catch (err: any) {
      setError(err.message || 'Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-in fade-in duration-200">
      <div className="bg-[#141414]/95 border border-white/[0.1] rounded-3xl w-full max-w-md shadow-[0_20px_50px_rgba(0,0,0,0.6)] overflow-hidden">
        {/* Header */}
        <div className="px-6 py-5 border-b border-white/[0.06] flex items-center justify-between">
          <div>
            <h3 className="text-base font-bold text-white tracking-tight">
              {isRegister ? 'Register Tenant Account' : 'Sign in to SalaryLens'}
            </h3>
            <p className="text-xs text-text-muted">Enterprise bank statement salary intelligence</p>
          </div>
          <button
            onClick={onClose}
            disabled={loading}
            className="h-8 w-8 rounded-full bg-white/[0.04] hover:bg-white/[0.08] text-text-muted hover:text-white flex items-center justify-center border border-white/[0.08] transition"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-4">
          {error && (
            <div className="p-3 rounded-2xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-center gap-2">
              <AlertCircle className="h-4 w-4 shrink-0 text-rose-400" />
              <span>{error}</span>
            </div>
          )}

          {/* Quick Demo Button */}
          <button
            type="button"
            onClick={handleDemoLogin}
            disabled={loading}
            className="w-full py-3 px-4 rounded-full bg-gradient-to-r from-[#F15A43] via-[#e04832] to-[#8B7CFF] hover:opacity-95 text-white text-xs font-bold flex items-center justify-center gap-2 shadow-glow-accent transition active:scale-98"
          >
            <Sparkles className="h-4 w-4" />
            <span>1-Click Instant Demo Login (Admin)</span>
          </button>

          <div className="flex items-center gap-3">
            <div className="h-[1px] flex-1 bg-white/[0.06]" />
            <span className="text-[10px] text-text-muted uppercase tracking-wider font-semibold">
              or continue with credentials
            </span>
            <div className="h-[1px] flex-1 bg-white/[0.06]" />
          </div>

          <form onSubmit={handleSubmit} className="space-y-3">
            {isRegister && (
              <>
                <div>
                  <label className="block text-xs font-medium text-text-secondary mb-1">Full Name</label>
                  <div className="relative">
                    <User className="h-4 w-4 text-text-muted absolute left-3.5 top-3" />
                    <input
                      type="text"
                      value={fullName}
                      onChange={(e) => setFullName(e.target.value)}
                      placeholder="Jane Doe"
                      className="w-full pl-10 pr-4 py-2.5 bg-[#161616] border border-white/[0.08] rounded-xl text-xs text-text-primary focus:outline-none focus:border-[#F15A43]/50 transition"
                      required
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-medium text-text-secondary mb-1">Organization Name</label>
                  <div className="relative">
                    <Building className="h-4 w-4 text-text-muted absolute left-3.5 top-3" />
                    <input
                      type="text"
                      value={orgName}
                      onChange={(e) => setOrgName(e.target.value)}
                      placeholder="Acme Financial Corp"
                      className="w-full pl-10 pr-4 py-2.5 bg-[#161616] border border-white/[0.08] rounded-xl text-xs text-text-primary focus:outline-none focus:border-[#F15A43]/50 transition"
                      required
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-medium text-text-secondary mb-1">Role</label>
                  <select
                    value={role}
                    onChange={(e) => setRole(e.target.value)}
                    className="w-full px-4 py-2.5 bg-[#161616] border border-white/[0.08] rounded-xl text-xs text-text-primary focus:outline-none focus:border-[#F15A43]/50 transition"
                  >
                    <option value="admin">Admin (Full Access & Reviewer)</option>
                    <option value="reviewer">Reviewer</option>
                    <option value="agent">Agent</option>
                  </select>
                </div>
              </>
            )}

            <div>
              <label className="block text-xs font-medium text-text-secondary mb-1">Email</label>
              <div className="relative">
                <Mail className="h-4 w-4 text-text-muted absolute left-3.5 top-3" />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="analyst@bank.com"
                  className="w-full pl-10 pr-4 py-2.5 bg-[#161616] border border-white/[0.08] rounded-xl text-xs text-text-primary focus:outline-none focus:border-[#F15A43]/50 transition"
                  required
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-text-secondary mb-1">Password</label>
              <div className="relative">
                <Lock className="h-4 w-4 text-text-muted absolute left-3.5 top-3" />
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full pl-10 pr-4 py-2.5 bg-[#161616] border border-white/[0.08] rounded-xl text-xs text-text-primary focus:outline-none focus:border-[#F15A43]/50 transition"
                  required
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full mt-2 py-2.5 px-4 rounded-full bg-[#F15A43] hover:bg-[#e04832] text-white text-xs font-semibold flex items-center justify-center gap-2 shadow-glow-accent transition active:scale-98"
            >
              {loading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>Signing in...</span>
                </>
              ) : (
                <span>{isRegister ? 'Create Account' : 'Sign In'}</span>
              )}
            </button>
          </form>

          {/* Toggle Register / Login */}
          <div className="pt-2 text-center text-xs text-text-muted">
            {isRegister ? (
              <span>
                Already have an account?{' '}
                <button
                  type="button"
                  onClick={() => setIsRegister(false)}
                  className="text-[#F15A43] hover:underline font-semibold"
                >
                  Sign in
                </button>
              </span>
            ) : (
              <span>
                Need an organization account?{' '}
                <button
                  type="button"
                  onClick={() => setIsRegister(true)}
                  className="text-[#F15A43] hover:underline font-semibold"
                >
                  Register tenant
                </button>
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
