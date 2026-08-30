import React, { useEffect, useState } from 'react';
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
  const [copiedOrderId, setCopiedOrderId] = useState(false);
  const [copiedExplanation, setCopiedExplanation] = useState(false);
  const [isVisible, setIsVisible] = useState(false);
  const [activeDecision, setActiveDecision] = useState<DecisionRecord | null>(decision);

  // Handle smooth enter/exit animations and decision switching
  useEffect(() => {
    if (decision) {
      setActiveDecision(decision);
      // Lock background body scroll
      document.body.style.overflow = 'hidden';
      // Trigger slide-in animation frame
      const timer = requestAnimationFrame(() => setIsVisible(true));
      return () => {
        cancelAnimationFrame(timer);
      };
    } else {
      setIsVisible(false);
      const timer = setTimeout(() => {
        setActiveDecision(null);
        document.body.style.overflow = '';
      }, 300);
      return () => clearTimeout(timer);
    }
  }, [decision]);

  // Clean up body scroll lock on unmount
  useEffect(() => {
    return () => {
      document.body.style.overflow = '';
    };
  }, []);

  if (!activeDecision && !decision) return null;

  const current = decision || activeDecision;
  if (!current) return null;

  const isAllow = current.verdict === 'ALLOW';
  const isBlock = current.verdict === 'BLOCK';
  const isFlag = current.verdict === 'FLAG';

  const apirisTelemetry = current.evidence?.apiris;
  const behaviorTelemetry = current.evidence?.behavior;

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
      {/* Backdrop with fade transition */}
      <div
        className={`fixed inset-0 bg-black/75 backdrop-blur-sm transition-opacity duration-300 ease-in-out ${
          isVisible ? 'opacity-100' : 'opacity-0'
        }`}
        onClick={onClose}
      />

      {/* Drawer Container with slide transition */}
      <div
        className={`relative w-full max-w-2xl bg-[#0E0E10] border-l border-white/10 h-full overflow-y-auto shadow-2xl flex flex-col z-10 text-[#F5F1EA] transform transition-transform duration-300 ease-in-out ${
          isVisible ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        {/* Header */}
        <div className="sticky top-0 bg-[#0E0E10]/95 backdrop-blur border-b border-white/10 px-6 py-4 flex items-center justify-between z-20">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono text-[#D4A15C] font-semibold">
                AUDIT RECORD #{current.id}
              </span>
              <span className="text-xs text-[#8E8A83]">·</span>
              <span className="text-xs font-mono text-[#8E8A83] flex items-center gap-1">
                <Clock size={12} />
                {new Date(current.timestamp || Date.now()).toLocaleTimeString()}
              </span>
            </div>
            <h2 className="text-base font-bold text-[#F5F1EA] mt-0.5">
              Decision Audit & Policy Execution Trace
            </h2>
          </div>

          <button
            onClick={onClose}
            aria-label="Close drawer"
            className="p-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-[#8E8A83] hover:text-[#F5F1EA] transition-all cursor-pointer"
          >
            <X size={18} />
          </button>
        </div>

        {/* Content Body with consistent spacing */}
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
                    verdict={current.verdict}
                    confidence={current.confidence}
                    riskTier={apirisTelemetry?.risk_classification}
                    size="lg"
                  />
                </div>
                <div className="text-xs font-mono text-[#F5F1EA] leading-relaxed">
                  Factor: <code className="text-[#D4A15C]">{current.primary_factor}</code>
                </div>
              </div>

              <div className="text-right font-mono">
                <div className="text-xs text-[#8E8A83]">Amount</div>
                <div className="text-xl font-bold text-[#F5F1EA] tabular-nums">
                  ₹{(current.amount_inr ?? 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                </div>
                <div className="text-[10px] text-[#8E8A83]">
                  ({current.amount_paise ?? 0} paise)
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
                  onClick={() => copyToClipboard(current.summary || '', 'explanation')}
                  className="text-[10px] font-mono text-[#8E8A83] hover:text-[#F5F1EA] flex items-center gap-1 bg-white/5 px-2 py-0.5 rounded border border-white/10 cursor-pointer"
                >
                  {copiedExplanation ? <Check size={11} className="text-emerald-400" /> : <Copy size={11} />}
                  <span>{copiedExplanation ? 'Copied' : 'Copy'}</span>
                </button>
              </div>

              <p className="text-xs font-mono text-rose-200 leading-relaxed bg-black/40 p-3 rounded-lg border border-rose-500/20">
                "{current.summary}"
              </p>

              <div className="mt-2.5 flex items-center gap-2 text-[11px] text-[#8E8A83]">
                <Shield size={12} className="text-emerald-400 shrink-0" />
                <span><strong>Failure Handled Gracefully:</strong> Downstream Razorpay Orders API was never invoked. Zero partial side-effects.</span>
              </div>
            </div>
          )}

          {/* ALLOW PROOF POINT: Real Razorpay Order ID */}
          {isAllow && current.razorpay_order_id && (
            <div className="p-4 rounded-xl bg-emerald-950/30 border border-emerald-500/30">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-1.5 text-xs font-semibold text-emerald-400 font-mono">
                  <CreditCard size={14} />
                  <span>Downstream Razorpay Test-Mode Order</span>
                </div>
                <button
                  onClick={() => copyToClipboard(current.razorpay_order_id || '', 'order')}
                  className="text-[10px] font-mono text-[#8E8A83] hover:text-[#F5F1EA] flex items-center gap-1 bg-white/5 px-2 py-0.5 rounded border border-white/10 cursor-pointer"
                >
                  {copiedOrderId ? <Check size={11} className="text-emerald-400" /> : <Copy size={11} />}
                  <span>{copiedOrderId ? 'Copied' : 'Copy Order ID'}</span>
                </button>
              </div>

              <div className="flex items-center justify-between bg-black/40 p-3 rounded-lg border border-emerald-500/20 font-mono text-xs">
                <span className="text-[#F5F1EA] font-semibold">{current.razorpay_order_id}</span>
                <span className="text-emerald-400 text-[11px] flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  Verified on Razorpay Test API
                </span>
              </div>

              {current.allow_token && (
                <div className="mt-2 text-[10px] font-mono text-[#8E8A83] truncate">
                  HMAC ALLOW Token: <code>{current.allow_token.slice(0, 32)}...</code>
                </div>
              )}
            </div>
          )}

          {/* 1. Policy Hierarchy Waterfall Trace */}
          <section>
            <h4 className="text-xs font-mono uppercase tracking-wider text-[#D4A15C] mb-2.5 flex items-center gap-2 font-semibold">
              <span className="w-1.5 h-1.5 rounded-full bg-[#D4A15C]" />
              1. Policy Hierarchy Execution Trace
            </h4>
            <PolicyWaterfall
              amountInr={current.amount_inr}
              riskWeight={apirisTelemetry?.risk_weight ?? 0.05}
              hasBehaviorFlag={behaviorTelemetry?.flag ?? false}
              activeVerdict={current.verdict}
              primaryFactor={current.primary_factor}
            />
          </section>

          {/* 2. Apiris CAD Triad Health & Inverted Risk */}
          <section>
            <h4 className="text-xs font-mono uppercase tracking-wider text-[#D4A15C] mb-2.5 flex items-center gap-2 font-semibold">
              <span className="w-1.5 h-1.5 rounded-full bg-[#D4A15C]" />
              2. Apiris Security Telemetry
            </h4>
            <ApirisScoreTriad telemetry={apirisTelemetry} />
          </section>

          {/* 3. Behavioral Telemetry Signals */}
          <section>
            <h4 className="text-xs font-mono uppercase tracking-wider text-[#D4A15C] mb-2.5 flex items-center gap-2 font-semibold">
              <span className="w-1.5 h-1.5 rounded-full bg-[#D4A15C]" />
              3. Session & Behavioral Signals
            </h4>
            <div className="p-4 rounded-xl bg-[#111113] border border-white/10 space-y-3 font-mono text-xs shadow-xl">
              <div className="flex items-center justify-between">
                <span className="text-[#8E8A83]">Agent ID:</span>
                <span className="text-[#F5F1EA] font-semibold">{current.agent_id}</span>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-[#8E8A83]">Behavior Flag Status:</span>
                <span
                  className={
                    behaviorTelemetry?.flag
                      ? 'text-amber-400 font-bold'
                      : 'text-emerald-400 font-semibold'
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
          </section>

          {/* 4. A2A Protocol Handshake Transcript */}
          <section>
            <h4 className="text-xs font-mono uppercase tracking-wider text-[#D4A15C] mb-2.5 flex items-center gap-2 font-semibold">
              <span className="w-1.5 h-1.5 rounded-full bg-[#D4A15C]" />
              4. A2A Protocol Handshake Transcript
            </h4>
            <AgentTimeline
              receipt={{
                mandate_id: `mandate_${current.id}`,
                buyer_agent_id: current.agent_id,
                merchant_id: 'merchant_razorgate_cloud',
                sku: String((current.evidence as any)?.request?.notes?.sku || 'compute-gpu-h100-1hr'),
                amount_paise: current.amount_paise,
                amount_inr: current.amount_inr,
                currency: 'INR',
                verdict: current.verdict,
                primary_factor: current.primary_factor,
                summary: current.summary,
                confidence: current.confidence,
                audit_id: current.id,
                order: current.razorpay_order_id ? { id: current.razorpay_order_id } : null,
              }}
              explanation={current.summary}
            />
          </section>
        </div>
      </div>
    </div>
  );
};

