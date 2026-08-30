import React from 'react';
import type { Verdict } from '../../types';
import { ShieldCheck, ShieldAlert, ShieldX, ArrowDown, Check, AlertTriangle } from 'lucide-react';

interface PolicyStep {
  id: number;
  title: string;
  condition: string;
  verdict: Verdict;
  confidenceStr: string;
  matched: boolean;
  activeReason?: string;
  note?: string;
}

interface PolicyWaterfallProps {
  amountInr?: number;
  riskWeight?: number;
  hasBehaviorFlag?: boolean;
  activeVerdict?: Verdict;
  primaryFactor?: string;
}

export const PolicyWaterfall: React.FC<PolicyWaterfallProps> = ({
  amountInr = 299.0,
  riskWeight = 0.05,
  hasBehaviorFlag = false,
  activeVerdict,
}) => {
  const safeAmount = typeof amountInr === 'number' && !isNaN(amountInr) ? amountInr : 0;
  const safeRisk = typeof riskWeight === 'number' && !isNaN(riskWeight) ? riskWeight : 0.05;

  const isCeilingBreach = safeAmount > 50000.0;
  const isHighRisk = !isCeilingBreach && safeRisk >= 0.80;
  const isFlagged = !isCeilingBreach && !isHighRisk && (safeRisk >= 0.40 || hasBehaviorFlag);
  const isAllowed = !isCeilingBreach && !isHighRisk && !isFlagged;

  const steps: PolicyStep[] = [
    {
      id: 1,
      title: 'Deterministic Ceiling Gate',
      condition: 'amount_inr > ₹50,000.00',
      verdict: 'BLOCK',
      confidenceStr: '1.00 (deterministic)',
      matched: isCeilingBreach,
      activeReason: isCeilingBreach
        ? `Order amount ₹${safeAmount.toLocaleString('en-IN', { minimumFractionDigits: 2 })} exceeds ₹50,000.00 ceiling`
        : `₹${safeAmount.toLocaleString('en-IN', { minimumFractionDigits: 2 })} ≤ ₹50,000.00 ceiling (passed)`,
    },
    {
      id: 2,
      title: 'Apiris High Telemetry Risk',
      condition: 'risk_weight ≥ 0.80',
      verdict: 'BLOCK',
      confidenceStr: 'inherited from Apiris (≥0.90)',
      matched: isHighRisk,
      activeReason: isHighRisk
        ? `Risk weight ${safeRisk.toFixed(2)} ≥ 0.80 block threshold`
        : `Risk weight ${safeRisk.toFixed(2)} < 0.80 (passed)`,
    },
    {
      id: 3,
      title: 'Moderate Risk or Behavior Anomaly',
      condition: 'risk_weight ≥ 0.40 OR behavior_flag',
      verdict: 'FLAG',
      confidenceStr: 'boundary scaled (0.70 – 0.95)',
      matched: isFlagged,
      note: 'Behavior flags can only ever push toward FLAG, never BLOCK on their own.',
      activeReason: isFlagged
        ? hasBehaviorFlag
          ? `Behavior anomaly detected in rolling window (FLAG)`
          : `Moderate risk weight ${safeRisk.toFixed(2)} ≥ 0.40 (FLAG)`
        : `Clean behavior & risk weight ${safeRisk.toFixed(2)} < 0.40 (passed)`,
    },
    {
      id: 4,
      title: 'Policy Cleared — Mint ALLOW Token',
      condition: 'All prior checks cleared',
      verdict: 'ALLOW',
      confidenceStr: '1.00 × (1.0 − risk_weight)',
      matched: isAllowed,
      activeReason: isAllowed
        ? `All deterministic and probabilistic safety boundaries cleared. HMAC token minted (30s TTL).`
        : undefined,
    },
  ];

  return (
    <div className="w-full bg-[#111113] border border-white/10 rounded-xl p-5 shadow-2xl relative overflow-hidden">
      {/* Background Accent Grid */}
      <div className="absolute inset-0 bg-[radial-gradient(#d4a15c_1px,transparent_1px)] [background-size:16px_16px] opacity-[0.03] pointer-events-none" />

      {/* Header */}
      <div className="flex items-center justify-between pb-4 mb-4 border-b border-white/10 relative z-10">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono uppercase tracking-widest text-[#D4A15C]">
              Deterministic Policy Engine
            </span>
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-white/5 border border-white/10 text-[#8E8A83]">
              First-Match-Wins Hierarchy
            </span>
          </div>
          <h3 className="text-sm font-semibold text-[#F5F1EA] mt-1">
            4-Stage Evaluation Waterfall
          </h3>
        </div>

        {activeVerdict && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-[#8E8A83]">Resolved:</span>
            <span
              className={`font-mono text-xs font-bold px-2 py-0.5 rounded border uppercase ${
                activeVerdict === 'ALLOW'
                  ? 'text-emerald-400 bg-emerald-950/60 border-emerald-500/40'
                  : activeVerdict === 'FLAG'
                  ? 'text-amber-400 bg-amber-950/60 border-amber-500/40'
                  : 'text-rose-400 bg-rose-950/60 border-rose-500/40'
              }`}
            >
              {activeVerdict}
            </span>
          </div>
        )}
      </div>

      {/* Asymmetry Trust Callout */}
      <div className="mb-4 p-3 rounded-lg bg-[#D4A15C]/10 border border-[#D4A15C]/30 flex items-start gap-2.5">
        <AlertTriangle size={16} className="text-[#E8B96C] shrink-0 mt-0.5" />
        <div className="text-xs text-[#E8B96C] leading-relaxed">
          <strong className="font-semibold text-[#F5F1EA]">Asymmetric Trust Guarantee:</strong> Behavioral rolling-window anomalies (<code className="font-mono text-[11px] bg-black/40 px-1 py-0.5 rounded">high_frequency</code>, <code className="font-mono text-[11px] bg-black/40 px-1 py-0.5 rounded">amount_deviation</code>) can <strong className="underline">only push to FLAG</strong>, never unilaterally trigger BLOCK.
        </div>
      </div>

      {/* Waterfall Steps */}
      <div className="space-y-3 relative z-10">
        {steps.map((step, idx) => {
          const isFired = step.matched;
          const isPastFired = steps.slice(0, idx).some((s) => s.matched);
          const isEvaluatedAndPassed = !step.matched && !isPastFired;

          return (
            <div key={step.id} className="relative">
              <div
                className={`p-3.5 rounded-lg border transition-all duration-300 ${
                  isFired
                    ? step.verdict === 'ALLOW'
                      ? 'bg-emerald-950/40 border-emerald-500/60 shadow-[0_0_15px_rgba(74,222,128,0.15)] ring-1 ring-emerald-500/40'
                      : step.verdict === 'FLAG'
                      ? 'bg-amber-950/40 border-amber-500/60 shadow-[0_0_15px_rgba(245,166,35,0.15)] ring-1 ring-amber-500/40'
                      : 'bg-rose-950/40 border-rose-500/60 shadow-[0_0_15px_rgba(239,68,68,0.15)] ring-1 ring-rose-500/40'
                    : isPastFired
                    ? 'bg-[#161619]/40 border-white/5 opacity-40'
                    : 'bg-[#161619] border-white/10 hover:border-white/20'
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  {/* Step number & condition */}
                  <div className="flex items-start gap-3">
                    <div
                      className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-mono font-bold shrink-0 mt-0.5 ${
                        isFired
                          ? step.verdict === 'ALLOW'
                            ? 'bg-emerald-500 text-black'
                            : step.verdict === 'FLAG'
                            ? 'bg-amber-500 text-black'
                            : 'bg-rose-500 text-black'
                          : isEvaluatedAndPassed
                          ? 'bg-white/10 text-[#C5C0B7]'
                          : 'bg-white/5 text-[#8E8A83]'
                      }`}
                    >
                      {isFired ? (
                        step.verdict === 'ALLOW' ? <ShieldCheck size={14} /> : step.verdict === 'FLAG' ? <ShieldAlert size={14} /> : <ShieldX size={14} />
                      ) : isEvaluatedAndPassed ? (
                        <Check size={12} className="text-emerald-400" />
                      ) : (
                        step.id
                      )}
                    </div>

                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-medium text-[#F5F1EA]">
                          Rule #{step.id}: {step.title}
                        </span>
                      </div>
                      <div className="font-mono text-xs text-[#D4A15C] mt-0.5">
                        <code>{step.condition}</code>
                      </div>

                      {step.activeReason && (
                        <div
                          className={`text-xs mt-1.5 font-mono ${
                            isFired
                              ? step.verdict === 'ALLOW'
                                ? 'text-emerald-300'
                                : step.verdict === 'FLAG'
                                ? 'text-amber-300'
                                : 'text-rose-300 font-semibold'
                              : 'text-[#8E8A83]'
                          }`}
                        >
                          → {step.activeReason}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Verdict & Confidence pill */}
                  <div className="text-right shrink-0">
                    <div
                      className={`font-mono text-xs font-bold px-2 py-0.5 rounded border inline-block ${
                        step.verdict === 'ALLOW'
                          ? 'text-emerald-400 bg-emerald-950/40 border-emerald-500/30'
                          : step.verdict === 'FLAG'
                          ? 'text-amber-400 bg-amber-950/40 border-amber-500/30'
                          : 'text-rose-400 bg-rose-950/40 border-rose-500/30'
                      }`}
                    >
                      {step.verdict}
                    </div>
                    <div className="text-[10px] font-mono text-[#8E8A83] mt-1">
                      conf: {step.confidenceStr}
                    </div>
                  </div>
                </div>
              </div>

              {idx < steps.length - 1 && (
                <div className="flex justify-center py-1">
                  <ArrowDown size={14} className={isPastFired || isFired ? 'text-white/10' : 'text-[#D4A15C]/40'} />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
