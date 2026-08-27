import React from 'react';
import { Shield, Play, Terminal, Radio } from 'lucide-react';

export type SurfaceTab = 'landing' | 'dashboard' | 'walkthrough';

interface HeaderProps {
  currentTab: SurfaceTab;
  onSelectTab: (tab: SurfaceTab) => void;
  sseStatus: 'connected' | 'disconnected' | 'reconnecting';
  onQuickRunDemo?: () => void;
  isDemoRunning?: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  currentTab,
  onSelectTab,
  sseStatus,
  onQuickRunDemo,
  isDemoRunning = false,
}) => {
  return (
    <header className="sticky top-0 z-50 w-full bg-[#0A0A0B]/90 backdrop-blur-md border-b border-white/10">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo & Product Identity */}
          <div className="flex items-center gap-3 cursor-pointer" onClick={() => onSelectTab('landing')}>
            <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-[#D4A15C] to-[#B5823D] flex items-center justify-center shadow-[0_0_15px_rgba(212,161,92,0.3)]">
              <Shield className="w-5 h-5 text-black font-bold" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-base tracking-tight text-[#F5F1EA]">
                  RazorGate
                </span>
                <span className="text-[10px] font-mono font-medium px-1.5 py-0.5 rounded bg-[#D4A15C]/15 border border-[#D4A15C]/30 text-[#E8B96C]">
                  Track 01
                </span>
              </div>
              <p className="text-[11px] text-[#8E8A83] font-mono -mt-0.5">
                AI Agent Payments Trust Layer
              </p>
            </div>
          </div>

          {/* Surface Switcher Navigation */}
          <nav className="hidden md:flex items-center p-1 rounded-lg bg-[#161619] border border-white/10">
            <button
              onClick={() => onSelectTab('landing')}
              className={`px-3.5 py-1.5 rounded-md text-xs font-medium transition-all ${
                currentTab === 'landing'
                  ? 'bg-[#D4A15C] text-black shadow font-semibold'
                  : 'text-[#C5C0B7] hover:text-[#F5F1EA] hover:bg-white/5'
              }`}
            >
              1. Overview & Trust
            </button>

            <button
              onClick={() => onSelectTab('dashboard')}
              className={`px-3.5 py-1.5 rounded-md text-xs font-medium transition-all flex items-center gap-1.5 ${
                currentTab === 'dashboard'
                  ? 'bg-[#D4A15C] text-black shadow font-semibold'
                  : 'text-[#C5C0B7] hover:text-[#F5F1EA] hover:bg-white/5'
              }`}
            >
              <Radio size={13} className={currentTab === 'dashboard' ? 'text-black' : 'text-emerald-400 animate-pulse'} />
              2. Live Control Room
            </button>

            <button
              onClick={() => onSelectTab('walkthrough')}
              className={`px-3.5 py-1.5 rounded-md text-xs font-medium transition-all flex items-center gap-1.5 ${
                currentTab === 'walkthrough'
                  ? 'bg-[#D4A15C] text-black shadow font-semibold'
                  : 'text-[#C5C0B7] hover:text-[#F5F1EA] hover:bg-white/5'
              }`}
            >
              <Terminal size={13} />
              3. Gated Payment Flow
            </button>
          </nav>

          {/* Live Status & Quick Action */}
          <div className="flex items-center gap-3">
            {/* Real-time SSE Pulse */}
            <div
              className={`hidden sm:inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-mono border ${
                sseStatus === 'connected'
                  ? 'bg-emerald-950/50 border-emerald-500/30 text-emerald-400'
                  : sseStatus === 'reconnecting'
                  ? 'bg-amber-950/50 border-amber-500/30 text-amber-400'
                  : 'bg-rose-950/50 border-rose-500/30 text-rose-400'
              }`}
              title="Server-Sent Events connection on /decisions/stream"
            >
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  sseStatus === 'connected'
                    ? 'bg-emerald-400 animate-pulse'
                    : sseStatus === 'reconnecting'
                    ? 'bg-amber-400 animate-ping'
                    : 'bg-rose-400'
                }`}
              />
              <span>{sseStatus === 'connected' ? 'SSE Stream Live' : sseStatus === 'reconnecting' ? 'Reconnecting...' : 'SSE Offline'}</span>
            </div>

            {/* Quick Run Scenario Button */}
            {onQuickRunDemo && (
              <button
                onClick={onQuickRunDemo}
                disabled={isDemoRunning}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#D4A15C] hover:bg-[#E8B96C] text-black text-xs font-semibold shadow-md transition-all disabled:opacity-50"
              >
                <Play size={13} className={isDemoRunning ? 'animate-spin' : ''} />
                <span>{isDemoRunning ? 'Running...' : 'Run Scenario'}</span>
              </button>
            )}
          </div>
        </div>
      </div>
    </header>
  );
};
