import React from 'react';
import type { DecisionRecord } from '../../types';
import { VerdictBadge } from '../common/VerdictBadge';
import { PolicyWaterfall } from '../common/PolicyWaterfall';
import { ApirisScoreTriad } from '../common/ApirisScoreTriad';
import { AgentTimeline } from './AgentTimeline';

import {
  X,
  Copy,
  Check,
  Clock,
  Shield,
  AlertOctagon,
  CreditCard,
} from 'lucide-react';

interface DecisionDetailDrawerProps {
  decision: DecisionRecord | null;
  onClose: () => void;
}

export const DecisionDetailDrawer: React.FC<DecisionDetailDrawerProps> = ({
  decision,
  onClose,
}) => {
  const [copiedOrderId, setCopiedOrderId] = React.useState(false);
  const [copiedExplanation, setCopiedExplanation] = React.useState(false);

  if (!decision) return null;

  const isAllow = decision.verdict === 'ALLOW';
  const isBlock = decision.verdict === 'BLOCK';
  const isFlag = decision.verdict === 'FLAG';

  const apirisTelemetry = decision.evidence?.apiris;
  const behaviorTelemetry = decision.evidence?.behavior;

  const copyToClipboard = (text: string, type: 'order' | 'explanation') => {
    navigator.clipboard.writeText(text);
    if (type === 'order') {
      setCopiedOrderId(true);
      setTimeout(() => setCopiedOrderId(false), 2000);
    } else {
      setCopiedExplanation(true);
      setTimeout(() => setCopiedExplanation(false), 2000);
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-hidden flex justify-end">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/70 backdrop-blur-sm transition-opacity"
        onClick={onClose}
      />

      {/* Drawer Container */}
      <div className="relative w-full max-w-2xl bg-[#0E0E10] border-l border-white/10 h-full overflow-y-auto shadow-2xl flex flex-col z-10 text-[#F5F1EA]">
        {/* Header */}
        <div className="sticky top-0 bg-[#0E0E10]/95 backdrop-blur border-b border-white/10 px-6 py-4 flex items-center justify-between z-20">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono text-[#D4A15C] font-semibold">
                AUDIT RECORD #{decision.id}
              </span>
              <span className="text-xs text-[#8E8A83]">·</span>
              <span className="text-xs font-mono text-[#8E8A83] flex items-center gap-1">
                <Clock size={12} />
                {new Date(decision.timestamp).toLocaleTimeString()}
              </span>
            </div>
            <h2 className="text-base font-bold text-[#F5F1EA] mt-0.5">
              Decision Audit & Policy Execution Trace
            </h2>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-[#8E8A83] hover:text-[#F5F1EA] transition-all"
          >
            <X size={18} />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-6 space-y-6 flex-1">
          {/* Top Summary Banner */}
          <div
            className={`p-4 rounded-xl border ${
              isAllow
                ? 'bg-emerald-950/30 border-emerald-500/40'
                : isFlag
                ? 'bg-amber-950/30 border-amber-500/40'
                : 'bg-rose-950/30 border-rose-500/40'
            }`}
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="text-xs font-mono text-[#8E8A83] uppercase tracking-wider mb-1">
                  Evaluated Outcome
                </div>
                <div className="flex items-center gap-2 mb-2">
                  <VerdictBadge
                    verdict={decision.verdict}
                    confidence={decision.confidence}
                    riskTier={apirisTelemetry?.risk_classification}
                    size="lg"
                  />
                </div>
                <div className="text-xs font-mono text-[#F5F1EA] leading-relaxed">
                  Factor: <code className="text-[#D4A15C]">{decision.primary_factor}</code>
                </div>
              </div>

              <div className="text-right font-mono">
                <div className="text-xs text-[#8E8A83]">Amount</div>
                <div className="text-xl font-bold text-[#F5F1EA] tabular-nums">
                  ₹{decision.amount_inr.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                </div>
                <div className="text-[10px] text-[#8E8A83]">
                  ({decision.amount_paise} paise)
                </div>
              </div>
            </div>
          </div>

          {/* BLOCK PROOF POINT: Human-Readable Explainer (Verbatim) */}
          {isBlock && (
            <div className="p-4 rounded-xl bg-rose-950/40 border border-rose-500/40">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-1.5 text-xs font-semibold text-rose-400 font-mono">
                  <AlertOctagon size={14} />
                  <span>Audit Explanation (audit/explainer.py)</span>
                </div>
                <button
                  onClick={() => copyToClipboard(decision.summary, 'explanation')}
                  className="text-[10px] font-mono text-[#8E8A83] hover:text-[#F5F1EA] flex items-center gap-1 bg-white/5 px-2 py-0.5 rounded border border-white/10"
                >
                  {copiedExplanation ? <Check size={11} className="text-emerald-400" /> : <Copy size={11} />}
                  <span>{copiedExplanation ? 'Copied' : 'Copy'}</span>
                </button>
              </div>

              <p className="text-xs font-mono text-rose-200 leading-relaxed bg-black/40 p-3 rounded-lg border border-rose-500/20">
                "{decision.summary}"
              </p>

              <div className="mt-2.5 flex items-center gap-2 text-[11px] text-[#8E8A83]">
                <Shield size={12} className="text-emerald-400 shrink-0" />
                <span><strong>Failure Handled Gracefully:</strong> Downstream Razorpay Orders API was never invoked. Zero partial side-effects.</span>
              </div>
            </div>
          )}

          {/* ALLOW PROOF POINT: Real Razorpay Order ID */}
          {isAllow && decision.razorpay_order_id && (
            <div className="p-4 rounded-xl bg-emerald-950/30 border border-emerald-500/30">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-1.5 text-xs font-semibold text-emerald-400 font-mono">
                  <CreditCard size={14} />
                  <span>Downstream Razorpay Test-Mode Order</span>
                </div>
                <button
                  onClick={() => copyToClipboard(decision.razorpay_order_id || '', 'order')}
                  className="text-[10px] font-mono text-[#8E8A83] hover:text-[#F5F1EA] flex items-center gap-1 bg-white/5 px-2 py-0.5 rounded border border-white/10"
                >
                  {copiedOrderId ? <Check size={11} className="text-emerald-400" /> : <Copy size={11} />}
                  <span>{copiedOrderId ? 'Copied' : 'Copy Order ID'}</span>
                </button>
              </div>

              <div className="flex items-center justify-between bg-black/40 p-3 rounded-lg border border-emerald-500/20 font-mono text-xs">
                <span className="text-[#F5F1EA] font-semibold">{decision.razorpay_order_id}</span>
                <span className="text-emerald-400 text-[11px] flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  Verified on Razorpay Test API
                </span>
              </div>

              {decision.allow_token && (
                <div className="mt-2 text-[10px] font-mono text-[#8E8A83] truncate">
                  HMAC ALLOW Token: <code>{decision.allow_token.slice(0, 32)}...</code>
                </div>
              )}
            </div>
          )}

          {/* 1. Policy Hierarchy Waterfall Trace */}
          <div>
            <h4 className="text-xs font-mono uppercase tracking-wider text-[#D4A15C] mb-2.5">
              1. Policy Hierarchy Execution Trace
            </h4>
            <PolicyWaterfall
              amountInr={decision.amount_inr}
              riskWeight={apirisTelemetry?.risk_weight ?? 0.05}
              hasBehaviorFlag={behaviorTelemetry?.flag ?? false}
              activeVerdict={decision.verdict}
              primaryFactor={decision.primary_factor}
            />
          </div>

          {/* 2. Apiris CAD Triad Health & Inverted Risk */}
          <div>
            <h4 className="text-xs font-mono uppercase tracking-wider text-[#D4A15C] mb-2.5">
              2. Apiris Security Telemetry
            </h4>
            <ApirisScoreTriad telemetry={apirisTelemetry} />
          </div>

          {/* 3. Behavioral Telemetry Signals */}
          <div>
            <h4 className="text-xs font-mono uppercase tracking-wider text-[#D4A15C] mb-2.5">
              3. Session & Behavioral Signals
            </h4>
            <div className="p-4 rounded-xl bg-[#111113] border border-white/10 space-y-3 font-mono text-xs">
              <div className="flex items-center justify-between">
                <span className="text-[#8E8A83]">Agent ID:</span>
                <span className="text-[#F5F1EA] font-semibold">{decision.agent_id}</span>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-[#8E8A83]">Behavior Flag Status:</span>
                <span
                  className={
                    behaviorTelemetry?.flag
                      ? 'text-amber-400 font-bold'
                      : 'text-emerald-400'
                  }
                >
                  {behaviorTelemetry?.flag ? 'FLAG TRIGGERED' : 'CLEAN / NORMAL'}
                </span>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-[#8E8A83]">Rolling Window Calls (300s):</span>
                <span className="text-[#F5F1EA]">
                  {behaviorTelemetry?.session_call_count ?? 1} / 5 max threshold
                </span>
              </div>

              {behaviorTelemetry?.reasons && behaviorTelemetry.reasons.length > 0 && (
                <div className="pt-2 border-t border-white/5">
                  <div className="text-[11px] text-[#8E8A83] mb-1">Triggered Reasons:</div>
                  <ul className="space-y-1 text-amber-300 text-[11px]">
                    {behaviorTelemetry.reasons.map((r, i) => (
                      <li key={i} className="flex items-start gap-1.5">
                        <span>•</span>
                        <span>{r}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>

          {/* 4. A2A Protocol Handshake Transcript */}
          <div>
            <h4 className="text-xs font-mono uppercase tracking-wider text-[#D4A15C] mb-2.5">
              4. A2A Protocol Handshake Transcript
            </h4>
            <AgentTimeline
              receipt={{
                mandate_id: `mandate_${decision.id}`,
                buyer_agent_id: decision.agent_id,
                merchant_id: 'merchant_razorgate_cloud',
                sku: String((decision.evidence as any)?.request?.notes?.sku || 'compute-gpu-h100-1hr'),
                amount_paise: decision.amount_paise,
                amount_inr: decision.amount_inr,
                currency: 'INR',
                verdict: decision.verdict,
                primary_factor: decision.primary_factor,
                summary: decision.summary,
                confidence: decision.confidence,
                audit_id: decision.id,
                order: decision.razorpay_order_id ? { id: decision.razorpay_order_id } : null,
              }}
              explanation={decision.summary}
            />
          </div>
        </div>
      </div>
    </div>
  );
};

