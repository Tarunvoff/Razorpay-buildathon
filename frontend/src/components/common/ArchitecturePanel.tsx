import React from 'react';
import type { Verdict } from '../../types';
import { Bot, Store, Cpu, CreditCard, Database, Activity } from 'lucide-react';

interface ArchitecturePanelProps {
  activeVerdict?: Verdict;
  activePath?: 'buyer' | 'merchant' | 'control' | 'gate' | 'payments' | 'audit' | 'all';
  isProcessing?: boolean;
}

export const ArchitecturePanel: React.FC<ArchitecturePanelProps> = ({
  activeVerdict = 'ALLOW',
  isProcessing = false,
}) => {
  const isBlock = activeVerdict === 'BLOCK';

  return (
    <div className="w-full bg-[#111113] border border-white/10 rounded-xl p-5 shadow-2xl relative overflow-hidden">
      {/* Background Grid */}
      <div className="absolute inset-0 bg-[radial-gradient(#d4a15c_1px,transparent_1px)] [background-size:16px_16px] opacity-[0.03] pointer-events-none" />

      {/* Header */}
      <div className="flex items-center justify-between pb-3 mb-4 border-b border-white/10 relative z-10">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono uppercase tracking-widest text-[#D4A15C]">
              Control Room Telemetry
            </span>
            <span className="inline-flex items-center gap-1 text-[10px] font-mono px-1.5 py-0.5 rounded bg-emerald-950/40 border border-emerald-500/30 text-emerald-400">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              Live HLD Topology
            </span>
          </div>
          <h3 className="text-sm font-semibold text-[#F5F1EA] mt-0.5">
            RazorGate A2A Commerce & Execution Pipeline
          </h3>
        </div>

        {isProcessing && (
          <div className="flex items-center gap-1.5 text-xs font-mono text-[#D4A15C] animate-pulse">
            <Activity size={14} />
            <span>Evaluating Gate Check...</span>
          </div>
        )}
      </div>

      {/* Interactive Topology Graph */}
      <div className="space-y-4 relative z-10">
        {/* Tier 1: Multi-Agent Protocol Layer */}
        <div className="p-3 rounded-lg bg-[#161619] border border-white/10">
          <div className="text-[10px] font-mono text-[#8E8A83] uppercase tracking-wider mb-2 flex items-center justify-between">
            <span>1. Agent-to-Agent Protocol Handshake</span>
            <span className="text-[#D4A15C]">6-Step Signed Protocol</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {/* Buyer Agent */}
            <div className="p-3 rounded-md bg-black/40 border border-white/10 hover:border-[#D4A15C]/40 transition-all flex items-start gap-2.5">
              <div className="w-8 h-8 rounded bg-[#D4A15C]/10 border border-[#D4A15C]/30 flex items-center justify-center text-[#E8B96C] shrink-0">
                <Bot size={16} />
              </div>
              <div className="min-w-0">
                <div className="text-xs font-semibold text-[#F5F1EA] flex items-center gap-1.5">
                  Buyer Agent
                  <span className="text-[9px] font-mono px-1 rounded bg-white/5 text-[#8E8A83]">LLM-Driven</span>
                </div>
                <div className="text-[11px] text-[#8E8A83] mt-0.5 truncate font-mono">
                  Intent · Comparison Reasoning · Signs Mandate
                </div>
              </div>
            </div>

            {/* Merchant Agent */}
            <div className="p-3 rounded-md bg-black/40 border border-white/10 hover:border-[#D4A15C]/40 transition-all flex items-start gap-2.5">
              <div className="w-8 h-8 rounded bg-sky-950/40 border border-sky-500/30 flex items-center justify-center text-sky-400 shrink-0">
                <Store size={16} />
              </div>
              <div className="min-w-0">
                <div className="text-xs font-semibold text-[#F5F1EA] flex items-center gap-1.5">
                  Merchant Agent
                  <span className="text-[9px] font-mono px-1 rounded bg-white/5 text-[#8E8A83]">Backend Front</span>
                </div>
                <div className="text-[11px] text-[#8E8A83] mt-0.5 truncate font-mono">
                  AgentCard · Catalog Search · Mandate Verifier
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Central Connector Arrow */}
        <div className="flex justify-center text-center -my-2 relative z-20">
          <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-[#1F1F24] border border-white/10 text-[#C5C0B7] flex items-center gap-1">
            <span>FastAPI Control Plane</span>
            <code className="text-[#D4A15C]">POST /gate/check</code>
          </span>
        </div>

        {/* Tier 2: Deterministic Gate Engine */}
        <div className="p-3.5 rounded-lg bg-[#161619] border border-white/10 ring-1 ring-white/5">
          <div className="text-[10px] font-mono text-[#D4A15C] uppercase tracking-wider mb-2 flex items-center justify-between">
            <span className="flex items-center gap-1.5">
              <Cpu size={12} />
              2. Gate Engine (Pure State Function)
            </span>
            <span className="text-[#8E8A83]">Deterministic Policy Hierarchy</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
            <div className="p-2.5 rounded bg-black/50 border border-white/5">
              <div className="text-[11px] font-semibold text-[#F5F1EA]">adapter.py</div>
              <div className="text-[10px] text-[#8E8A83] font-mono mt-0.5">Real Apiris v1.1.1</div>
              <div className="text-[10px] text-emerald-400 font-mono mt-1">C/A/D Health Inversion</div>
            </div>

            <div className="p-2.5 rounded bg-black/50 border border-white/5">
              <div className="text-[11px] font-semibold text-[#F5F1EA]">behavior.py</div>
              <div className="text-[10px] text-[#8E8A83] font-mono mt-0.5">Session Drift Window</div>
              <div className="text-[10px] text-amber-400 font-mono mt-1">Cannot Solo-Block</div>
            </div>

            <div className="p-2.5 rounded bg-black/50 border border-white/5">
              <div className="text-[11px] font-semibold text-[#F5F1EA]">policy.py</div>
              <div className="text-[10px] text-[#8E8A83] font-mono mt-0.5">ALLOW / FLAG / BLOCK</div>
              <div className="text-[10px] text-[#D4A15C] font-mono mt-1">HMAC 30s ALLOW Token</div>
            </div>
          </div>
        </div>

        {/* Tier 3: Downstream Payments & Audit Layer */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {/* Payments Layer */}
          <div
            className={`p-3 rounded-lg border transition-all ${
              isBlock
                ? 'bg-rose-950/20 border-rose-500/20 opacity-60'
                : 'bg-[#161619] border-emerald-500/30'
            }`}
          >
            <div className="flex items-center gap-2 mb-1.5">
              <CreditCard size={15} className={isBlock ? 'text-rose-400' : 'text-emerald-400'} />
              <div className="text-xs font-semibold text-[#F5F1EA]">
                Payments Layer (Razorpay SDK)
              </div>
            </div>
            <div className="text-[11px] text-[#8E8A83] font-mono">
              {isBlock ? (
                <span className="text-rose-400">Strictly Gated — Zero Orders Created</span>
              ) : (
                <span className="text-emerald-400">ALLOW Token Re-validated $\rightarrow$ Real Order</span>
              )}
            </div>
          </div>

          {/* Audit Ledger */}
          <div className="p-3 rounded-lg bg-[#161619] border border-white/10">
            <div className="flex items-center gap-2 mb-1.5">
              <Database size={15} className="text-[#D4A15C]" />
              <div className="text-xs font-semibold text-[#F5F1EA]">
                Audit Ledger (SQLite)
              </div>
            </div>
            <div className="text-[11px] text-[#8E8A83] font-mono">
              Structured Evidence · Template Explanations · SSE Broadcast
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
