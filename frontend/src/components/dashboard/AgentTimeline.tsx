import React, { useState } from 'react';
import type { A2AStep, ReceiptData } from '../../types';
import {
  Bot,
  Store,
  Layers,
  Cpu,
  Receipt as ReceiptIcon,
  Code2,
  KeyRound,
} from 'lucide-react';

interface AgentTimelineProps {
  transcript?: A2AStep[];
  receipt?: ReceiptData | null;
  explanation?: string;
}

export const AgentTimeline: React.FC<AgentTimelineProps> = ({
  transcript,
  receipt,
  explanation,
}) => {
  const [activeStepIdx, setActiveStepIdx] = useState<number>(3); // Default to Mandate step

  // High-fidelity fallback transcript when none is passed
  const steps: A2AStep[] = transcript && transcript.length > 0
    ? transcript
    : [
        {
          step: 'capability_discovery',
          timestamp: Date.now() - 15000,
          data: {
            merchant_id: 'merchant_razorgate_cloud',
            merchant_name: 'RazorGate Cloud & AI Compute Services',
            supported_categories: ['ai_compute', 'api_credits', 'cloud_infra', 'enterprise_services'],
            gate_disclosure: {
              gating_enforced: true,
              policy_version: '2026.08.27',
              supported_verdicts: ['ALLOW', 'FLAG', 'BLOCK'],
              max_order_ceiling_inr: 50000.0,
            },
          },
        },
        {
          step: 'task_request',
          timestamp: Date.now() - 12000,
          data: {
            buyer_agent_id: 'buyer_h100_cluster_1904',
            intent: 'High-throughput GPU compute instance with NVLink interconnect for 80GB model inference',
            category: 'ai_compute',
            max_budget_paise: 1000000,
          },
        },
        {
          step: 'received_offers',
          timestamp: Date.now() - 9000,
          data: {
            offers: [
              {
                sku: 'compute-gpu-h100-1hr',
                name: 'NVIDIA H100 SXM 80GB Instance (1 Hour)',
                amount_paise: 29900,
                unit: 'hour',
                specs: { gpu: 'NVIDIA H100 80GB', vram_gb: 80, interconnect: 'NVLink 900GB/s' },
              },
              {
                sku: 'compute-gpu-a100-1hr',
                name: 'NVIDIA A100 Tensor Core 40GB Instance (1 Hour)',
                amount_paise: 14900,
                unit: 'hour',
                specs: { gpu: 'NVIDIA A100 40GB', vram_gb: 40, interconnect: 'PCIe Gen4' },
              },
              {
                sku: 'compute-gpu-l4-1hr',
                name: 'NVIDIA L4 24GB Instance (1 Hour)',
                amount_paise: 7900,
                unit: 'hour',
                specs: { gpu: 'NVIDIA L4 24GB', vram_gb: 24, interconnect: 'PCIe Gen4' },
              },
            ],
          },
        },
        {
          step: 'payment_mandate',
          timestamp: Date.now() - 6000,
          data: {
            mandate_id: 'mandate_9a7f3e1b',
            buyer_agent_id: 'buyer_h100_cluster_1904',
            merchant_id: 'merchant_razorgate_cloud',
            sku: 'compute-gpu-h100-1hr',
            amount_paise: 29900,
            amount_inr: 299.0,
            currency: 'INR',
            reasoning: 'Selected compute-gpu-h100-1hr (₹299.00): provides dedicated 80GB VRAM and 900GB/s NVLink required by inference intent, well within ₹10,000.00 budget.',
            signature: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
          },
        },
        {
          step: 'gated_execution',
          timestamp: Date.now() - 3000,
          data: {
            verdict: receipt?.verdict || 'ALLOW',
            confidence: receipt?.confidence || 1.0,
            primary_factor: receipt?.primary_factor || 'policy_cleared',
            summary: receipt?.summary || 'Transaction of ₹299.00 APPROVED: All policy and telemetry safety checks passed.',
            allow_token: 'hmac_sha256_9182736450abcdef_30s_ttl',
          },
        },
        {
          step: 'receipt',
          timestamp: Date.now(),
          data: {
            mandate_id: 'mandate_9a7f3e1b',
            sku: 'compute-gpu-h100-1hr',
            verdict: receipt?.verdict || 'ALLOW',
            amount_inr: receipt?.amount_inr || 299.0,
            audit_id: receipt?.audit_id || 1040,
            razorpay_order_id: receipt?.order?.id || 'order_TUkjWMgUTBNytJ',
          },
        },
      ];

  const stepMeta = [
    { title: '1. Discovery', label: 'AgentCard', icon: Store },
    { title: '2. Intent', label: 'TaskRequest', icon: Bot },
    { title: '3. Negotiation', label: 'OfferList', icon: Layers },
    { title: '4. Selection', label: 'PaymentMandate', icon: KeyRound },
    { title: '5. Gate Check', label: 'PolicyEngine', icon: Cpu },
    { title: '6. Receipt', label: 'Audit & Order', icon: ReceiptIcon },
  ];

  const activeStep = steps[activeStepIdx] || steps[0];

  return (
    <div className="w-full bg-[#111113] border border-white/10 rounded-xl p-5 shadow-2xl relative overflow-hidden">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 mb-5 border-b border-white/10 gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono uppercase tracking-widest text-[#D4A15C]">
              Multi-Agent Protocol Trace
            </span>
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-white/5 border border-white/10 text-sky-400">
              A2A Commerce Protocol v1
            </span>
          </div>
          <h3 className="text-sm font-semibold text-[#F5F1EA] mt-0.5">
            End-to-End Buyer ↔ Merchant Handshake Transcript
          </h3>
        </div>

        {explanation && (
          <div className="text-xs font-mono text-[#C5C0B7] bg-black/40 px-3 py-1.5 rounded-lg border border-white/5 max-w-md truncate">
            <span className="text-[#D4A15C] font-semibold">Buyer Explanation:</span> "{explanation}"
          </div>
        )}
      </div>

      {/* 6-Step Horizontal Stepper Bar */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2 mb-6">
        {stepMeta.map((meta, idx) => {
          const StepIcon = meta.icon;
          const isSelected = activeStepIdx === idx;

          return (
            <button
              key={meta.label}
              onClick={() => setActiveStepIdx(idx)}
              className={`p-3 rounded-lg border text-left transition-all ${
                isSelected
                  ? 'bg-[#1F1F24] border-[#D4A15C] shadow-[0_0_15px_rgba(212,161,92,0.15)] ring-1 ring-[#D4A15C]/40'
                  : 'bg-[#161619] border-white/5 hover:border-white/15'
              }`}
            >
              <div className="flex items-center justify-between mb-1.5">
                <div
                  className={`w-6 h-6 rounded flex items-center justify-center ${
                    isSelected ? 'bg-[#D4A15C] text-black' : 'bg-white/5 text-[#8E8A83]'
                  }`}
                >
                  <StepIcon size={13} />
                </div>
                <span className="text-[10px] font-mono text-[#8E8A83]">Step {idx + 1}</span>
              </div>
              <div className="text-xs font-semibold text-[#F5F1EA] truncate">
                {meta.title}
              </div>
              <div className="text-[10px] font-mono text-[#D4A15C] truncate">
                {meta.label}
              </div>
            </button>
          );
        })}
      </div>

      {/* Active Step Inspector */}
      {activeStep && (
        <div className="p-4 rounded-xl bg-[#161619] border border-white/10 font-mono text-xs">
          <div className="flex items-center justify-between pb-2 mb-3 border-b border-white/5">
            <div className="flex items-center gap-2">
              <Code2 size={14} className="text-[#D4A15C]" />
              <span className="font-semibold text-[#F5F1EA]">
                {String(stepMeta[activeStepIdx]?.label || activeStep.step)} Payload
              </span>
            </div>
            <div className="text-[11px] text-[#8E8A83]">
              Timestamp: {new Date(activeStep.timestamp).toLocaleTimeString()}
            </div>
          </div>

          {/* VERBATIM COMPARISON REASONING HIGHLIGHT (Step 4) */}
          {Boolean(activeStep.data?.reasoning) && (
            <div className="mb-3 p-3 rounded-lg bg-[#D4A15C]/10 border border-[#D4A15C]/30 text-xs font-sans text-[#F5F1EA]">
              <div className="text-[10px] font-mono text-[#E8B96C] uppercase font-bold tracking-wider mb-1">
                Autonomous Buyer Comparison Reasoning (Verbatim):
              </div>
              <p className="italic text-[#F5F1EA] leading-relaxed">
                "{String(activeStep.data.reasoning)}"
              </p>
            </div>
          )}

          {/* Cryptographic Signature (Step 4) */}
          {Boolean(activeStep.data?.signature) && (
            <div className="mb-3 p-2.5 rounded bg-black/40 border border-white/5 text-[11px] flex items-center justify-between">
              <span className="text-[#8E8A83]">HMAC-SHA256 Mandate Signature:</span>
              <code className="text-emerald-400">
                {String(activeStep.data.signature).slice(0, 32)}...
              </code>
            </div>
          )}

          {/* Pretty-Printed JSON Payload */}
          <pre className="p-3 rounded-lg bg-black/50 border border-white/5 text-[#C5C0B7] text-[11px] overflow-x-auto max-h-60 leading-relaxed">
            {JSON.stringify(activeStep.data, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
};
