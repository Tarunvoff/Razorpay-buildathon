import React, { useState } from 'react';
import type { DecisionRecord, MetricsSummary, ScenarioRunResult } from '../../types';
import { VerdictBadge } from '../common/VerdictBadge';
import { ArchitecturePanel } from '../common/ArchitecturePanel';
import { AgentTimeline } from './AgentTimeline';
import { DecisionDetailDrawer } from './DecisionDetailDrawer';
import {
  Activity,
  Search,
  ShieldCheck,
  ShieldAlert,
  ShieldX,
  Zap,
  Play,
  ArrowUpRight,
} from 'lucide-react';

interface LiveDashboardProps {
  decisions: DecisionRecord[];
  metrics: MetricsSummary;
  selectedDecision: DecisionRecord | null;
  onSelectDecision: (decision: DecisionRecord | null) => void;
  sseStatus: 'connected' | 'disconnected' | 'reconnecting';
  latestScenario?: ScenarioRunResult | null;
  onRunScenario?: (scenario: 'clean_allow' | 'behavior_flag' | 'forced_failure_block') => void;
  isScenarioRunning?: boolean;
}

export const LiveDashboard: React.FC<LiveDashboardProps> = ({
  decisions,
  metrics,
  selectedDecision,
  onSelectDecision,
  latestScenario,
  onRunScenario,
  isScenarioRunning = false,
}) => {
  const [filterVerdict, setFilterVerdict] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');

  const filteredDecisions = decisions.filter((d) => {
    if (filterVerdict !== 'ALL' && d.verdict !== filterVerdict) return false;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      return (
        d.agent_id.toLowerCase().includes(q) ||
        d.primary_factor.toLowerCase().includes(q) ||
        d.summary.toLowerCase().includes(q) ||
        (d.razorpay_order_id && d.razorpay_order_id.toLowerCase().includes(q))
      );
    }
    return true;
  });

  const allows = decisions.filter((d) => d.verdict === 'ALLOW').length;
  const flags = decisions.filter((d) => d.verdict === 'FLAG').length;
  const blocks = decisions.filter((d) => d.verdict === 'BLOCK').length;
  const total = decisions.length || metrics.ledger.total_decisions;

  return (
    <div className="space-y-8 pb-16">
      {/* ZONE 1: TOP STRIP — SYSTEM PULSE */}
      <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
        {/* Total Decisions */}
        <div className="p-4 rounded-xl bg-[#111113] border border-white/10 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-mono text-[#8E8A83]">Total Decisions</span>
            <Activity size={13} className="text-[#D4A15C]" />
          </div>
          <div className="text-2xl font-bold font-mono text-[#F5F1EA] mt-2 tabular-nums">
            {total}
          </div>
          <div className="text-[10px] font-mono text-[#8E8A83] mt-1 flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            Live SSE Ledger
          </div>
        </div>

        {/* ALLOW Tally */}
        <div className="p-4 rounded-xl bg-[#111113] border border-emerald-500/20 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-mono text-emerald-400">ALLOW (Cleared)</span>
            <ShieldCheck size={13} className="text-emerald-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-emerald-400 mt-2 tabular-nums">
            {allows}
          </div>
          <div className="text-[10px] font-mono text-[#8E8A83] mt-1">
            HMAC 30s Tokens
          </div>
        </div>

        {/* FLAG Tally */}
        <div className="p-4 rounded-xl bg-[#111113] border border-amber-500/20 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-mono text-amber-400">FLAG (Review)</span>
            <ShieldAlert size={13} className="text-amber-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-amber-400 mt-2 tabular-nums">
            {flags}
          </div>
          <div className="text-[10px] font-mono text-[#8E8A83] mt-1">
            Behavior Anomaly
          </div>
        </div>

        {/* BLOCK Tally */}
        <div className="p-4 rounded-xl bg-[#111113] border border-rose-500/20 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-mono text-rose-400">BLOCK (Gated)</span>
            <ShieldX size={13} className="text-rose-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-rose-400 mt-2 tabular-nums">
            {blocks}
          </div>
          <div className="text-[10px] font-mono text-[#8E8A83] mt-1">
            0 Orders Created
          </div>
        </div>

        {/* p50 / p95 Latency */}
        <div className="p-4 rounded-xl bg-[#111113] border border-white/10 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-mono text-[#8E8A83]">p50 Latency</span>
            <Zap size={13} className="text-[#D4A15C]" />
          </div>
          <div className="text-2xl font-bold font-mono text-[#F5F1EA] mt-2 tabular-nums">
            {metrics.apiris_specs.p50_latency_ms} <span className="text-xs font-normal text-[#8E8A83]">ms</span>
          </div>
          <div className="text-[10px] font-mono text-[#8E8A83] mt-1">
            p95: {metrics.apiris_specs.p95_latency_ms} ms
          </div>
        </div>

        {/* Telemetry Badge */}
        <div className="p-4 rounded-xl bg-[#111113] border border-white/10 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-mono text-[#8E8A83]">Telemetry</span>
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          </div>
          <div className="text-base font-bold font-mono text-emerald-400 mt-2">
            0 Bytes Egress
          </div>
          <div className="text-[10px] font-mono text-[#8E8A83] mt-1">
            Air-Gapped & Offline
          </div>
        </div>
      </div>

      {/* QUICK SCENARIO FIRER STRIP */}
      {onRunScenario && (
        <div className="p-4 rounded-xl bg-[#161619] border border-white/10 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-[#D4A15C]/10 border border-[#D4A15C]/30 flex items-center justify-center text-[#E8B96C] shrink-0">
              <Play size={14} />
            </div>
            <div>
              <div className="text-xs font-semibold text-[#F5F1EA]">
                Judge Demo Trigger: Fire Scripted A2A Scenario
              </div>
              <div className="text-[11px] text-[#8E8A83] font-mono">
                Executes live A2A transaction, pushes decision over SSE, and updates ledger.
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={() => onRunScenario('clean_allow')}
              disabled={isScenarioRunning}
              className="px-3 py-1.5 rounded-md bg-emerald-950/60 hover:bg-emerald-900/60 border border-emerald-500/40 text-emerald-300 font-mono text-xs font-semibold transition-all disabled:opacity-50"
            >
              1. Clean ALLOW (₹299)
            </button>

            <button
              onClick={() => onRunScenario('behavior_flag')}
              disabled={isScenarioRunning}
              className="px-3 py-1.5 rounded-md bg-amber-950/60 hover:bg-amber-900/60 border border-amber-500/40 text-amber-300 font-mono text-xs font-semibold transition-all disabled:opacity-50"
            >
              2. Behavioral FLAG (Burst)
            </button>

            <button
              onClick={() => onRunScenario('forced_failure_block')}
              disabled={isScenarioRunning}
              className="px-3 py-1.5 rounded-md bg-rose-950/60 hover:bg-rose-900/60 border border-rose-500/40 text-rose-300 font-mono text-xs font-semibold transition-all disabled:opacity-50"
            >
              3. Phase 8 BLOCK (&gt;₹50k)
            </button>
          </div>
        </div>
      )}

      {/* MAIN TWO-COLUMN SPLIT: ZONE 2 (FEED) + ZONE 3 (ARCHITECTURE) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* CENTER FEED (7 Cols) */}
        <div className="lg:col-span-7 space-y-4">
          {/* Table Controls */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 p-3 rounded-xl bg-[#111113] border border-white/10">
            {/* Search */}
            <div className="relative flex-1">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#8E8A83]" />
              <input
                type="text"
                placeholder="Filter by agent_id, primary factor, or order ID..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-[#161619] border border-white/10 rounded-lg pl-9 pr-3 py-1.5 text-xs text-[#F5F1EA] placeholder-[#8E8A83] focus:outline-none focus:border-[#D4A15C]/50 font-mono"
              />
            </div>

            {/* Verdict Filter Buttons */}
            <div className="flex items-center gap-1 bg-[#161619] p-1 rounded-lg border border-white/5 font-mono text-xs">
              {['ALL', 'ALLOW', 'FLAG', 'BLOCK'].map((v) => (
                <button
                  key={v}
                  onClick={() => setFilterVerdict(v)}
                  className={`px-2.5 py-1 rounded text-[11px] font-semibold transition-all ${
                    filterVerdict === v
                      ? v === 'ALLOW'
                        ? 'bg-emerald-950 text-emerald-300 border border-emerald-500/40'
                        : v === 'FLAG'
                        ? 'bg-amber-950 text-amber-300 border border-amber-500/40'
                        : v === 'BLOCK'
                        ? 'bg-rose-950 text-rose-300 border border-rose-500/40'
                        : 'bg-[#D4A15C] text-black'
                      : 'text-[#8E8A83] hover:text-[#F5F1EA]'
                  }`}
                >
                  {v}
                </button>
              ))}
            </div>
          </div>

          {/* Live Decision Feed Table */}
          <div className="bg-[#111113] border border-white/10 rounded-xl overflow-hidden shadow-2xl">
            <div className="p-3.5 border-b border-white/10 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                <h3 className="text-xs font-semibold text-[#F5F1EA]">
                  Live Decision Feed (`/decisions/stream`)
                </h3>
              </div>
              <span className="text-[11px] font-mono text-[#8E8A83]">
                {filteredDecisions.length} recorded decisions
              </span>
            </div>

            <div className="overflow-x-auto max-h-[460px] overflow-y-auto">
              <table className="w-full text-left font-mono text-xs">
                <thead className="sticky top-0 bg-[#161619] border-b border-white/10 text-[10px] text-[#8E8A83] uppercase tracking-wider">
                  <tr>
                    <th className="py-2.5 px-3">Verdict</th>
                    <th className="py-2.5 px-3">Agent ID</th>
                    <th className="py-2.5 px-3 text-right">Amount</th>
                    <th className="py-2.5 px-3">Primary Factor</th>
                    <th className="py-2.5 px-3">Time</th>
                    <th className="py-2.5 px-3 text-center">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {filteredDecisions.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="py-8 text-center text-[#8E8A83]">
                        No decisions matching current filter criteria.
                      </td>
                    </tr>
                  ) : (
                    filteredDecisions.map((decision) => (
                      <tr
                        key={decision.id}
                        onClick={() => onSelectDecision(decision)}
                        className={`hover:bg-white/[0.03] cursor-pointer transition-all ${
                          selectedDecision?.id === decision.id ? 'bg-white/[0.06] ring-1 ring-inset ring-[#D4A15C]/40' : ''
                        }`}
                      >
                        {/* Verdict Badge */}
                        <td className="py-3 px-3">
                          <VerdictBadge verdict={decision.verdict} confidence={decision.confidence} size="sm" />
                        </td>

                        {/* Agent ID */}
                        <td className="py-3 px-3">
                          <div className="text-[#F5F1EA] font-semibold truncate max-w-[130px]" title={decision.agent_id}>
                            {decision.agent_id}
                          </div>
                          {decision.razorpay_order_id && (
                            <div className="text-[10px] text-emerald-400/80 truncate max-w-[130px]">
                              {decision.razorpay_order_id}
                            </div>
                          )}
                        </td>

                        {/* Amount */}
                        <td className="py-3 px-3 text-right tabular-nums font-semibold text-[#F5F1EA]">
                          ₹{decision.amount_inr.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                        </td>

                        {/* Factor */}
                        <td className="py-3 px-3">
                          <span className="text-[11px] text-[#C5C0B7] bg-white/5 px-2 py-0.5 rounded border border-white/5">
                            {decision.primary_factor}
                          </span>
                        </td>

                        {/* Time */}
                        <td className="py-3 px-3 text-[11px] text-[#8E8A83]">
                          {new Date(decision.timestamp).toLocaleTimeString()}
                        </td>

                        {/* Inspect link */}
                        <td className="py-3 px-3 text-center">
                          <button className="text-[#D4A15C] hover:text-[#E8B96C] p-1 rounded hover:bg-white/5">
                            <ArrowUpRight size={14} />
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* SIDE ARCHITECTURE PANEL (5 Cols) */}
        <div className="lg:col-span-5">
          <ArchitecturePanel
            activeVerdict={selectedDecision?.verdict || latestScenario?.verdict || 'ALLOW'}
            isProcessing={isScenarioRunning}
          />
        </div>
      </div>

      {/* ZONE 4: AGENT RUN TIMELINE (A2A Multi-Agent Transcript) */}
      <div>
        <AgentTimeline
          transcript={latestScenario?.transcript}
          receipt={latestScenario?.receipt}
          explanation={latestScenario?.explanation}
        />
      </div>

      {/* DECISION DETAIL DRAWER */}
      <DecisionDetailDrawer
        decision={selectedDecision}
        onClose={() => onSelectDecision(null)}
      />
    </div>
  );
};
