import React from 'react';
import type { DecisionRecord } from '../../types';
import { ShieldCheck, Activity, AlertTriangle, ShieldAlert, SearchX } from 'lucide-react';

interface ApirisTelemetryHeaderProps {
  latestDecision?: DecisionRecord | null;
  isConnected?: boolean;
}

export const ApirisTelemetryHeader: React.FC<ApirisTelemetryHeaderProps> = ({
  latestDecision,
  isConnected = true,
}) => {
  const apiris = latestDecision?.evidence?.apiris;

  const cScore = apiris?.health_scores?.confidentiality ?? 1.0;
  const aScore = apiris?.health_scores?.availability ?? 0.98;
  const dScore = apiris?.health_scores?.integrity ?? 1.0;

  const riskWeight = apiris?.risk_weight ?? (latestDecision?.verdict === 'BLOCK' ? 1.0 : latestDecision?.verdict === 'FLAG' ? 0.35 : 0.00);
  const riskTier = apiris?.risk_classification ?? (
    riskWeight >= 0.8 ? 'CRITICAL' : 
    riskWeight >= 0.6 ? 'HIGH' : 
    riskWeight >= 0.4 ? 'ELEVATED' :
    riskWeight > 0.1 ? 'MODERATE' : 'LOW'
  );
  const verdict = latestDecision?.verdict || 'ALLOW';


  const isAllow = verdict === 'ALLOW';
  const isFlag = verdict === 'FLAG';
  const isBlock = verdict === 'BLOCK';

  return (
    <div className="w-full bg-[#0A0A0C] border-b border-white/10 px-4 py-1 flex flex-wrap items-center justify-between gap-2.5 text-[11px] font-mono text-[#C5C0B7] z-40 sticky top-0 shadow-md backdrop-blur-md bg-opacity-95">
      {/* Left: Engine & Telemetry Title */}
      <div className="flex items-center gap-2.5">
        <div className="flex items-center gap-1.5 bg-[#161619] px-2 py-0.5 rounded border border-white/10">
          <Activity size={12} className="text-[#A39E93] animate-pulse" />
          <span className="font-bold text-[#F5F1EA] tracking-wide">APIRIS v1.1.1</span>
          <span className="text-[10px] text-[#8E8A83] border-l border-white/10 pl-1.5">REAL-TIME INTELLIGENCE</span>
        </div>

        {/* Live SSE Pulse */}
        <div className="flex items-center gap-1.5 text-[11px] text-[#8E8A83]">
          <span className={`w-2 h-2 rounded-full ${isConnected ? 'bg-emerald-400 animate-ping' : 'bg-rose-500'}`} />
          <span>{isConnected ? 'LIVE TELEMETRY' : 'CONNECTING...'}</span>
        </div>
      </div>

      {/* Center: CAD Triad Ticker Scores */}
      <div className="flex items-center gap-4 bg-[#111113] px-3 py-1 rounded-lg border border-white/5">
        <div className="flex items-center gap-1">
          <span className="text-[#8E8A83]">C:</span>
          <span className="font-bold text-emerald-400">{cScore.toFixed(2)}</span>
        </div>
        <span className="text-white/10">|</span>
        <div className="flex items-center gap-1">
          <span className="text-[#8E8A83]">A:</span>
          <span className="font-bold text-sky-400">{aScore.toFixed(2)}</span>
        </div>
        <span className="text-white/10">|</span>
        <div className="flex items-center gap-1">
          <span className="text-[#8E8A83]">D:</span>
          <span className="font-bold text-indigo-400">{dScore.toFixed(2)}</span>
        </div>
        <span className="text-white/10">|</span>
        <div className="flex items-center gap-1">
          <span className="text-[#8E8A83]">Risk Wt:</span>
          <span className={`font-bold tabular-nums ${riskWeight > 0.5 ? 'text-rose-400' : riskWeight > 0.2 ? 'text-amber-400' : 'text-emerald-400'}`}>
            {riskWeight.toFixed(3)}
          </span>
        </div>
      </div>

      {/* Right: Ambient Risk Tier & Active Gate Verdict */}
      <div className="flex items-center gap-2">
        <span className="text-[11px] text-[#8E8A83]">TIER:</span>
        <span
          className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase border ${
            riskTier === 'CRITICAL' || riskTier === 'HIGH'
              ? 'bg-rose-950/60 text-rose-300 border-rose-500/40'
              : riskTier === 'ELEVATED' || riskTier === 'MODERATE'
              ? 'bg-amber-950/60 text-amber-300 border-amber-500/40'
              : 'bg-emerald-950/60 text-emerald-300 border-emerald-500/40'
          }`}

        >
          {riskTier}
        </span>

        {/* Verdict Badge Ticker */}
        <div
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-bold tracking-wider uppercase border ${
            isAllow
              ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
              : isFlag
              ? 'bg-amber-500/10 text-amber-400 border-amber-500/30'
              : isBlock
              ? 'bg-rose-500/10 text-rose-400 border-rose-500/30'
              : 'bg-slate-800/40 text-slate-300 border-slate-500/30'
          }`}
        >
          {isAllow ? <ShieldCheck size={13} /> : isFlag ? <AlertTriangle size={13} /> : isBlock ? <ShieldAlert size={13} /> : <SearchX size={13} />}
          <span>{verdict === 'NO_MATCH' ? 'NO MATCH' : verdict}</span>
        </div>
      </div>
    </div>
  );
};
