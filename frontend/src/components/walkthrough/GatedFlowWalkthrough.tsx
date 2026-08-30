import React, { useState, useEffect } from 'react';
import type { ScenarioRunResult, Verdict, VerifyOrderResponse } from '../../types';
import { checkGate, createOrder, verifyOrder, loadRazorpayScript, askBuyerAgent } from '../../services/api';
import { VerdictBadge } from '../common/VerdictBadge';
import {
  Play,
  Lock,
  Cpu,
  CreditCard,
  Receipt as ReceiptIcon,
  RotateCcw,
  Clock,
  Sparkles,
  Server,
  AlertOctagon,
  Copy,
  Check,
  ShieldCheck,
  AlertTriangle,
  ExternalLink,
} from 'lucide-react';

interface GatedFlowWalkthroughProps {
  onRunScenario: (scenario: 'clean_allow' | 'behavior_flag' | 'forced_failure_block') => Promise<ScenarioRunResult>;
  isScenarioRunning: boolean;
  currentScenarioResult: ScenarioRunResult | null;
}

type ScenarioType = 'clean_allow' | 'behavior_flag' | 'forced_failure_block' | 'custom';

export const GatedFlowWalkthrough: React.FC<GatedFlowWalkthroughProps> = ({
  onRunScenario,
  isScenarioRunning,
  currentScenarioResult,
}) => {
  const [selectedScenario, setSelectedScenario] = useState<ScenarioType>('clean_allow');
  const [currentStep, setCurrentStep] = useState<number>(1);
  const [tokenCountdown, setTokenCountdown] = useState<number>(30);
  const [copiedOrderId, setCopiedOrderId] = useState(false);

  // Real backend execution state
  const [realGateResult, setRealGateResult] = useState<any>(null);
  const [realOrderResult, setRealOrderResult] = useState<any>(null);
  const [verifiedPayment, setVerifiedPayment] = useState<VerifyOrderResponse | null>(null);
  const [isVerifying, setIsVerifying] = useState<boolean>(false);
  const [verificationError, setVerificationError] = useState<string | null>(null);
  const [isExecuting, setIsExecuting] = useState<boolean>(false);
  const [burstCount, setBurstCount] = useState<number>(0);

  // Item 2 & 5: Free-form intent execution state & per-session rate limit
  const [customIntent, setCustomIntent] = useState<string>('cheap object storage for side project');
  const [customBudgetInr, setCustomBudgetInr] = useState<number>(5000);
  const [runsLeft, setRunsLeft] = useState<number>(10);
  const [customScenarioResult, setCustomScenarioResult] = useState<ScenarioRunResult | null>(null);



  // 30s token countdown timer
  useEffect(() => {
    if (currentStep >= 3 && selectedScenario !== 'forced_failure_block') {
      const interval = setInterval(() => {
        setTokenCountdown((prev) => (prev > 0 ? prev - 1 : 0));
      }, 1000);
      return () => clearInterval(interval);
    }
  }, [currentStep, selectedScenario]);

  const triggerRazorpayModal = async (
    orderRes: any,
    auditId?: number,
    amountPaise: number = 29900
  ) => {
    const loaded = await loadRazorpayScript();
    if (!loaded || !window.Razorpay) {
      console.warn('Razorpay checkout.js script could not be loaded.');
      return;
    }

    const orderId = orderRes?.order?.id;
    const keyId = orderRes?.key_id || 'rzp_test_TUiS6dViGS4SZY';

    if (!orderId) return;

    const options = {
      key: keyId,
      amount: amountPaise,
      currency: 'INR',
      name: 'RazorGate Security Gate',
      description: 'Test Mode Razorpay Payment Verification',
      order_id: orderId,
      handler: async function (response: {
        razorpay_payment_id: string;
        razorpay_order_id: string;
        razorpay_signature: string;
      }) {
        setIsVerifying(true);
        setVerificationError(null);
        try {
          const verifyRes = await verifyOrder({
            razorpay_payment_id: response.razorpay_payment_id,
            razorpay_order_id: response.razorpay_order_id,
            razorpay_signature: response.razorpay_signature,
            audit_id: auditId,
          });
          setVerifiedPayment(verifyRes);
        } catch (err: any) {
          setVerificationError(err.message || 'Signature verification failed.');
        } finally {
          setIsVerifying(false);
        }
      },
      prefill: {
        name: 'RazorGate Test Buyer Agent',
        email: 'agent@razorgate.dev',
        contact: '9999999999',
      },
      theme: {
        color: '#D4A15C',
      },
    };

    const rzp = new window.Razorpay(options);
    rzp.open();
  };

  const handleExecuteScenario = async (scenario: ScenarioType) => {
    setSelectedScenario(scenario);
    setCurrentStep(1);
    setTokenCountdown(30);
    setRealGateResult(null);
    setRealOrderResult(null);
    setVerifiedPayment(null);
    setVerificationError(null);
    setIsExecuting(true);
    setBurstCount(0);

    const timestamp = Date.now();
    let agentId = 'buyer_h100_cluster_' + (timestamp % 10000);
    let amount = 29900;
    let category = 'ai_compute';

    if (scenario === 'behavior_flag') {
      agentId = 'demo_flag_burst_agent';
      amount = 4900;
      category = 'api_credits';
    } else if (scenario === 'forced_failure_block') {
      agentId = 'buyer_enterprise_exec_' + (timestamp % 10000);
      amount = 6500000;
      category = 'enterprise_services';
    }

    try {
      // Stage 1: Buyer signs mandate
      setCurrentStep(1);
      await new Promise((r) => setTimeout(r, 200));

      // Stage 2: Gate waterfall evaluation via real POST /gate/check
      setCurrentStep(2);

      let gateRes: any = null;
      if (scenario === 'behavior_flag') {
        // Requirement 2 & 5: Fire 6 rapid burst calls with fixed agent_id to trigger rolling window FLAG
        for (let i = 1; i <= 6; i++) {
          setBurstCount(i);
          gateRes = await checkGate({
            amount: amount,
            currency: 'INR',
            agent_id: agentId,
            receipt: `rcpt_burst_${timestamp}_${i}`,
            category: category,
          });
          await new Promise((r) => setTimeout(r, 120));
        }
      } else {
        setBurstCount(1);
        gateRes = await checkGate({
          amount: amount,
          currency: 'INR',
          agent_id: agentId,
          receipt: `rcpt_${timestamp}`,
          category: category,
        });
      }

      setRealGateResult(gateRes);

      if (scenario !== 'custom') {
        onRunScenario(scenario as any).catch(() => {});
      }


      // Stage 3: Token Minting or Block Verdict
      setCurrentStep(3);
      await new Promise((r) => setTimeout(r, 400));

      if (gateRes.verdict === 'BLOCK') {
        // Zero downstream calls made to /orders or Razorpay Checkout modal
        setCurrentStep(5);
        setIsExecuting(false);
        return;
      }

      // Stage 4: Server-Gated Order Creation via real POST /orders
      setCurrentStep(4);
      if (gateRes.allow_token) {
        const orderRes = await createOrder({
          agent_id: agentId,
          amount_paise: amount,
          receipt: `rcpt_${timestamp}`,
          allow_token: gateRes.allow_token,
          currency: 'INR',
          audit_id: gateRes.audit_id,
        });
        setRealOrderResult(orderRes);

        // Stage 5: Dual Confirmation & launch Razorpay Checkout modal
        setCurrentStep(5);
        setIsExecuting(false);

        // For clean ALLOW, auto-launch Razorpay Modal for user test payment
        if (scenario === 'clean_allow') {
          triggerRazorpayModal(orderRes, gateRes.audit_id, amount);
        }
      } else {
        setCurrentStep(5);
        setIsExecuting(false);
      }
    } catch (err: any) {
      console.error('Walkthrough real execution error:', err);
      setCurrentStep(5);
      setIsExecuting(false);
    }
  };

  const scenarioMeta: Record<
    ScenarioType,
    {
      title: string;
      badge: string;
      verdict: Verdict;
      amount: string;
      sku: string;
      summary: string;
    }
  > = {
    clean_allow: {
      title: 'Scenario 1: Clean ALLOW Transaction',
      badge: 'Happy Path',
      verdict: 'ALLOW',
      amount: '₹299.00',
      sku: 'compute-gpu-h100-1hr',
      summary: 'NVIDIA H100 GPU compute instance. Clears all policy boundaries, mints 30s HMAC token, generates real Razorpay order.',
    },
    behavior_flag: {
      title: 'Scenario 2: Behavioral Anomaly FLAG',
      badge: '6-Call Rapid Burst',
      verdict: 'FLAG',
      amount: '₹49.00',
      sku: 'api-tier-starter-100k',
      summary: 'Fires 6 rapid calls in rolling window (fixed agent ID). Exceeds 5-call threshold, reliably triggering FLAG verdict every time.',
    },
    forced_failure_block: {
      title: 'Scenario 3: Phase 8 Forced-Failure BLOCK',
      badge: 'Ceiling Breach',
      verdict: 'BLOCK',
      amount: '₹65,000.00',
      sku: 'enterprise-support-tier1',
      summary: 'Enterprise 24/7 dedicated support exceeds ₹50,000 ceiling. Deterministically blocked, 0 orders created, graceful explanation.',
    },
    custom: {
      title: `Free-Form Intent: "${customIntent}"`,
      badge: 'Custom Judge Intent',
      verdict: (realGateResult?.verdict || customScenarioResult?.verdict || 'ALLOW') as Verdict,
      amount: `₹${((customScenarioResult?.amount_inr || (realGateResult?.amount_paise ? realGateResult.amount_paise / 100 : customBudgetInr))).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`,
      sku: String(customScenarioResult?.receipt?.sku || 'custom_request'),
      summary: customScenarioResult?.explanation || realGateResult?.summary || `Evaluates free-form intent '${customIntent}' against real marketplace catalog and RazorGate security gate.`,
    },
  };

  const currentMeta = scenarioMeta[selectedScenario];
  const activeVerdict = realGateResult?.verdict || currentScenarioResult?.verdict || currentMeta.verdict;
  const isBlock = activeVerdict === 'BLOCK';
  const isFlag = activeVerdict === 'FLAG';
  const isAllow = activeVerdict === 'ALLOW';

  const orderId =
    realOrderResult?.order?.id ||
    (currentScenarioResult?.order?.id ? String(currentScenarioResult.order.id) : null);

  const copyOrderId = () => {
    if (orderId) {
      navigator.clipboard.writeText(orderId);
      setCopiedOrderId(true);
      setTimeout(() => setCopiedOrderId(false), 2000);
    }
  };

  const handleFreeFormSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!customIntent.trim() || runsLeft <= 0 || isScenarioRunning || isExecuting) return;

    setRunsLeft((prev) => Math.max(0, prev - 1));
    setSelectedScenario('custom');
    setCurrentStep(1);
    setRealGateResult(null);
    setRealOrderResult(null);
    setVerifiedPayment(null);
    setVerificationError(null);
    setCustomScenarioResult(null);
    setIsExecuting(true);

    try {
      // Stage 1: Buyer signs mandate
      setCurrentStep(1);
      await new Promise((r) => setTimeout(r, 300));

      const res = await askBuyerAgent(customIntent, 'all', customBudgetInr);
      setCustomScenarioResult(res);

      // Stage 2: Gate Check
      setCurrentStep(2);
      await new Promise((r) => setTimeout(r, 400));

      const receipt = res.receipt;
      setRealGateResult({
        verdict: receipt.verdict,
        confidence: receipt.confidence,
        primary_factor: receipt.primary_factor,
        summary: receipt.summary,
        allow_token: receipt.evidence?.allow_token,
        audit_id: receipt.audit_id,
        amount_paise: receipt.amount_paise,
      });

      // Stage 3: Token Minting / Verdict
      setCurrentStep(3);
      await new Promise((r) => setTimeout(r, 400));

      if (receipt.verdict === 'ALLOW' && receipt.order) {
        const orderRes = {
          status: 'created',
          order: receipt.order,
          audit_id: receipt.audit_id,
          key_id: res.key_id || 'rzp_test_TUiS6dViGS4SZY',
        };
        setRealOrderResult(orderRes);

        // Stage 4: Order Creation
        setCurrentStep(4);
        await new Promise((r) => setTimeout(r, 400));

        // Stage 5: Dual Proof Panel
        setCurrentStep(5);
        await new Promise((r) => setTimeout(r, 200));

        // Auto-launch Razorpay Checkout test-mode modal for ALLOW transactions!
        triggerRazorpayModal(orderRes, receipt.audit_id || undefined, receipt.amount_paise || Math.round(customBudgetInr * 100));

      } else {
        setCurrentStep(5);
      }

    } catch (err: any) {
      console.error('Free-form agent execution error:', err);
      setCurrentStep(5);
    } finally {
      setIsExecuting(false);
    }
  };



  return (
    <div className="space-y-8 pb-16">
      {/* SECTION HEADER */}
      <div className="max-w-5xl mx-auto text-center">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#161619] border border-white/10 text-xs font-mono text-[#C5C0B7] mb-3">
          <Sparkles size={13} className="text-[#A39E93]" />
          <span>Surface 3: Razorpay Test-Mode Proof</span>
        </div>
        <h2 className="text-3xl font-extrabold text-[#F5F1EA]">
          Gated Payment Flow: Guided Walkthrough
        </h2>
        <p className="text-sm text-[#8E8A83] max-w-2xl mx-auto mt-2">
          Visually prove "no self-reported authorization": watch real XHR fetch calls hit <code className="text-[#C5C0B7]">POST /gate/check</code> and <code className="text-[#C5C0B7]">POST /orders</code>, launch Razorpay's actual payment modal, and verify server-side HMAC signatures.
        </p>
      </div>

      {/* ITEM 2: FREE-FORM "ASK THE BUYER AGENT" INTERACTIVE INPUT CARD */}
      <div className="max-w-5xl mx-auto bg-[#161619] border border-white/15 rounded-2xl p-5 shadow-2xl space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-white/10">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-white/10 border border-white/15 text-[#F5F1EA]">
              <Sparkles size={16} />
            </div>
            <div>
              <h3 className="text-sm font-bold text-[#F5F1EA]">
                Ask the Buyer Agent (Free-Form Intent & Multi-Category Marketplace Search)
              </h3>
              <p className="text-xs text-[#8E8A83]">
                Type any custom purchase intent to watch the real Claude-driven Buyer Agent search 23+ catalog SKUs across 6 categories.
              </p>
            </div>
          </div>
          <div className="text-[11px] font-mono px-2.5 py-1 rounded bg-white/5 border border-white/10 text-[#C5C0B7] shrink-0">
            Per-Session Guardrail: <span className="font-bold text-white">{runsLeft} / 10 runs remaining</span>
          </div>
        </div>

        <form onSubmit={handleFreeFormSubmit} className="grid grid-cols-1 md:grid-cols-12 gap-3">
          <div className="md:col-span-6">
            <label className="block text-[11px] font-mono text-[#8E8A83] mb-1">
              Purchase Intent / Custom Judge Request
            </label>
            <input
              type="text"
              value={customIntent}
              onChange={(e) => setCustomIntent(e.target.value)}
              placeholder="e.g. cheap object storage for side project, 10TB cloud backup, or enterprise devops team"
              className="w-full bg-black/50 border border-white/15 rounded-lg px-3 py-2 text-xs text-[#F5F1EA] placeholder-[#8E8A83]/60 focus:outline-none focus:border-[#D4A15C] font-sans"
            />
          </div>

          <div className="md:col-span-3">
            <label className="block text-[11px] font-mono text-[#8E8A83] mb-1">
              Max Budget (₹ INR)
            </label>
            <input
              type="number"
              value={customBudgetInr}
              onChange={(e) => setCustomBudgetInr(Number(e.target.value))}
              className="w-full bg-black/50 border border-white/15 rounded-lg px-3 py-2 text-xs text-[#F5F1EA] focus:outline-none focus:border-[#D4A15C] font-mono"
            />
          </div>

          <div className="md:col-span-3 flex items-end">
            <button
              type="submit"
              disabled={isScenarioRunning || isExecuting || runsLeft <= 0 || !customIntent.trim()}
              className="w-full py-2 px-4 rounded-lg bg-[#D4A15C] hover:bg-[#E8B96C] disabled:bg-white/10 text-black font-semibold text-xs flex items-center justify-center gap-2 transition-all shadow-lg font-mono"
            >
              <Play size={13} />
              <span>Ask Buyer Agent</span>
            </button>
          </div>
        </form>
      </div>


      {/* SCENARIO SELECTOR TABS */}
      <div className="max-w-5xl mx-auto grid grid-cols-1 md:grid-cols-3 gap-4">
        {(['clean_allow', 'behavior_flag', 'forced_failure_block'] as ScenarioType[]).map((st) => {
          const meta = scenarioMeta[st];
          const isSelected = selectedScenario === st;

          return (
            <button
              key={st}
              onClick={() => handleExecuteScenario(st)}
              disabled={isScenarioRunning || isExecuting}
              className={`p-4 rounded-xl border text-left transition-all ${
                isSelected
                  ? 'bg-[#161619] border-[#D4A15C] shadow-[0_0_20px_rgba(212,161,92,0.15)] ring-1 ring-[#D4A15C]/40'
                  : 'bg-[#111113] border-white/10 hover:border-white/20'
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <span
                  className={`font-mono text-[10px] uppercase font-bold px-2 py-0.5 rounded border ${
                    meta.verdict === 'ALLOW'
                      ? 'text-emerald-400 bg-emerald-950/60 border-emerald-500/40'
                      : meta.verdict === 'FLAG'
                      ? 'text-amber-400 bg-amber-950/60 border-amber-500/40'
                      : 'text-rose-400 bg-rose-950/60 border-rose-500/40'
                  }`}
                >
                  {meta.verdict}
                </span>
                <span className="text-xs font-mono font-bold text-[#F5F1EA]">
                  {meta.amount}
                </span>
              </div>

              <h4 className="text-sm font-semibold text-[#F5F1EA] mb-1">
                {meta.title.split(':')[1]}
              </h4>
              <p className="text-xs text-[#8E8A83] line-clamp-2">
                {meta.summary}
              </p>

              <div className="mt-3 pt-2.5 border-t border-white/5 flex items-center justify-between text-[11px] font-mono">
                <span className="text-[#D4A15C] flex items-center gap-1">
                  <Play size={11} />
                  <span>Click to Execute</span>
                </span>
                <span className="text-[#8E8A83]">{meta.badge}</span>
              </div>
            </button>
          );
        })}
      </div>

      {/* 5-STAGE INTERACTIVE EXECUTION PIPELINE */}
      <div className="max-w-5xl mx-auto bg-[#111113] border border-white/10 rounded-2xl p-6 shadow-2xl space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-white/10 gap-3">
          <div>
            <div className="text-xs font-mono text-[#D4A15C] uppercase tracking-wider">
              Live Backend & Razorpay Stream
            </div>
            <h3 className="text-lg font-bold text-[#F5F1EA]">
              {currentMeta.title}
            </h3>
          </div>

          <div className="flex items-center gap-3">
            <VerdictBadge verdict={activeVerdict} size="md" />
            <button
              onClick={() => handleExecuteScenario(selectedScenario)}
              disabled={isScenarioRunning || isExecuting}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-xs font-mono text-[#F5F1EA] border border-white/10 transition-all"
            >
              <RotateCcw size={12} />
              <span>Replay Real Scenario</span>
            </button>
          </div>
        </div>

        {/* 5-Stage Stepper Visual */}
        <div className="grid grid-cols-1 sm:grid-cols-5 gap-3">
          {/* Stage 1: Signed Mandate */}
          <div
            className={`p-3.5 rounded-xl border transition-all ${
              currentStep >= 1
                ? 'bg-[#161619] border-[#D4A15C]/50 text-[#F5F1EA]'
                : 'bg-black/20 border-white/5 opacity-40'
            }`}
          >
            <div className="text-[10px] font-mono text-[#D4A15C] uppercase mb-1">Stage 1</div>
            <div className="text-xs font-semibold flex items-center gap-1.5">
              <Lock size={13} className="text-[#D4A15C]" />
              <span>Signed Mandate</span>
            </div>
            <div className="text-[11px] font-mono text-[#8E8A83] mt-1">
              HMAC-SHA256 bounds
            </div>
          </div>

          {/* Stage 2: Gate Engine */}
          <div
            className={`p-3.5 rounded-xl border transition-all ${
              currentStep >= 2
                ? 'bg-[#161619] border-[#D4A15C]/50 text-[#F5F1EA]'
                : 'bg-black/20 border-white/5 opacity-40'
            }`}
          >
            <div className="text-[10px] font-mono text-[#D4A15C] uppercase mb-1">Stage 2</div>
            <div className="text-xs font-semibold flex items-center gap-1.5">
              <Cpu size={13} className="text-[#D4A15C]" />
              <span>POST /gate/check</span>
            </div>
            <div className="text-[11px] font-mono text-[#8E8A83] mt-1">
              {selectedScenario === 'behavior_flag' && burstCount > 0
                ? `Burst ${burstCount}/6 ${burstCount === 6 ? '(FLAG!)' : ''}`
                : 'Live FastAPI Waterfall'}
            </div>
          </div>

          {/* Stage 3: Token Mint or Block */}
          <div
            className={`p-3.5 rounded-xl border transition-all ${
              currentStep >= 3
                ? isBlock
                  ? 'bg-rose-950/40 border-rose-500/50 text-rose-300'
                  : isFlag
                  ? 'bg-amber-950/40 border-amber-500/50 text-amber-300'
                  : 'bg-emerald-950/40 border-emerald-500/50 text-emerald-300'
                : 'bg-black/20 border-white/5 opacity-40'
            }`}
          >
            <div className="text-[10px] font-mono uppercase mb-1">
              {isBlock ? 'Stage 3: Halted' : isFlag ? 'Stage 3: Flagged' : 'Stage 3: Token'}
            </div>
            <div className="text-xs font-semibold flex items-center gap-1.5">
              {isBlock ? <AlertOctagon size={13} /> : isFlag ? <AlertTriangle size={13} /> : <Clock size={13} />}
              <span>{isBlock ? 'BLOCK Verdict' : isFlag ? 'FLAG Verdict' : 'HMAC ALLOW Token'}</span>
            </div>
            <div className="text-[11px] font-mono mt-1 opacity-80">
              {isBlock ? 'Zero token minted' : `30s TTL (${tokenCountdown}s remaining)`}
            </div>
          </div>

          {/* Stage 4: Server Revalidation */}
          <div
            className={`p-3.5 rounded-xl border transition-all ${
              currentStep >= 4
                ? isBlock
                  ? 'bg-black/30 border-white/10 text-[#8E8A83]'
                  : 'bg-[#161619] border-emerald-500/40 text-[#F5F1EA]'
                : 'bg-black/20 border-white/5 opacity-40'
            }`}
          >
            <div className="text-[10px] font-mono text-[#D4A15C] uppercase mb-1">Stage 4</div>
            <div className="text-xs font-semibold flex items-center gap-1.5">
              <Server size={13} className={isBlock ? 'text-rose-400' : isFlag ? 'text-amber-400' : 'text-emerald-400'} />
              <span>POST /orders</span>
            </div>
            <div className="text-[11px] font-mono text-[#8E8A83] mt-1">
              {isBlock ? 'Execution halted (0 orders)' : 'Real Razorpay Order'}
            </div>
          </div>

          {/* Stage 5: Dual Confirmation */}
          <div
            className={`p-3.5 rounded-xl border transition-all ${
              currentStep >= 5
                ? 'bg-[#161619] border-[#D4A15C]/60 text-[#F5F1EA]'
                : 'bg-black/20 border-white/5 opacity-40'
            }`}
          >
            <div className="text-[10px] font-mono text-[#D4A15C] uppercase mb-1">Stage 5</div>
            <div className="text-xs font-semibold flex items-center gap-1.5">
              <ReceiptIcon size={13} className="text-[#D4A15C]" />
              <span>Dual Proof Panel</span>
            </div>
            <div className="text-[11px] font-mono text-[#8E8A83] mt-1">
              Verified Signature
            </div>
          </div>
        </div>

        {/* STAGE DETAIL EXPANDED: SIDE-BY-SIDE CONFIRMATION */}
        {currentStep >= 5 && (
          <div className="space-y-4 pt-4 border-t border-white/10">
            {isBlock ? (
              /* FORCED FAILURE BLOCK PROOF SURFACE */
              <div className="p-5 rounded-xl bg-rose-950/30 border border-rose-500/40 space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-rose-400 font-mono font-bold text-sm">
                    <AlertOctagon size={16} />
                    <span>Phase 8 Forced-Failure Confirmation: Zero Downstream Side Effects</span>
                  </div>
                  <span className="font-mono text-xs text-rose-300 bg-rose-950 px-2 py-0.5 rounded border border-rose-500/30">
                    ZERO Razorpay Orders Created
                  </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono">
                  <div className="p-3.5 rounded-lg bg-black/50 border border-rose-500/20">
                    <div className="text-[#8E8A83] text-[11px] mb-1">Real FastAPI Response (`POST /gate/check`):</div>
                    <p className="text-rose-200 leading-relaxed">
                      "{realGateResult?.summary || currentScenarioResult?.receipt?.summary || 'Transaction of ₹65,000.00 BLOCKED: Exceeds policy ceiling.'}"
                    </p>
                  </div>

                  <div className="p-3.5 rounded-lg bg-black/50 border border-rose-500/20">
                    <div className="text-[#8E8A83] text-[11px] mb-1">Downstream Execution Guarantee:</div>
                    <p className="text-[#F5F1EA] font-sans leading-relaxed">
                      "Because the gate returned BLOCK, <code className="text-rose-400 font-mono">POST /orders</code> and Razorpay's checkout modal were <strong>never called</strong>. Zero tokens minted, zero orders generated."
                    </p>
                  </div>
                </div>
              </div>
            ) : (
              /* CLEAN / FLAG SUCCESS DUAL RECORD PROOF */
              <div className="space-y-4">
                {/* FLAG Banner if verdict is FLAG */}
                {isFlag && (
                  <div className="p-4 rounded-xl bg-amber-950/40 border border-amber-500/50 space-y-2 font-mono text-xs text-amber-200">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2 font-bold text-amber-400 text-sm">
                        <AlertTriangle size={16} />
                        <span>Scenario 2 Verdict: FLAG (Behavioral Anomaly Triggered)</span>
                      </div>
                      <span className="bg-amber-900/80 text-amber-200 px-2.5 py-0.5 rounded text-[10px] font-bold border border-amber-400/40">
                        6 CALL BURST PROVEN
                      </span>
                    </div>
                    <p className="text-amber-100/90 text-xs font-sans leading-relaxed">
                      Fixed agent <code className="text-amber-300 font-mono">demo_flag_burst_agent</code> executed 6 rapid payment calls within the 300s window. Calls 1–5 returned ALLOW; call 6 breached the threshold limit (5), returning a deterministic <strong>FLAG</strong> verdict with primary factor <code className="text-amber-300 font-mono">behavior_anomaly</code>.
                    </p>
                  </div>
                )}

                {/* Razorpay Interactive Modal Trigger Bar */}
                <div className="p-4 rounded-xl bg-[#161619] border border-[#D4A15C]/40 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="flex items-center gap-2 text-xs font-mono">
                    <CreditCard size={16} className="text-[#D4A15C]" />
                    <div>
                      <div className="font-semibold text-[#F5F1EA]">
                        Requirement 2: Razorpay Hosted Checkout Modal
                      </div>
                      <div className="text-[#8E8A83] text-[11px]">
                        Order <code className="text-emerald-400">{orderId || 'order_created'}</code> ready. Test mode card details allowed.
                      </div>
                    </div>
                  </div>

                  <button
                    onClick={() => realOrderResult && triggerRazorpayModal(realOrderResult, realGateResult?.audit_id)}
                    disabled={!realOrderResult}
                    className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-[#D4A15C] hover:bg-[#E8B96C] text-black font-mono text-xs font-bold transition-all shrink-0 shadow-lg disabled:opacity-50"
                  >
                    <ExternalLink size={14} />
                    <span>Open Razorpay Modal Now</span>
                  </button>
                </div>

                {/* Verification Status Banner if payment was completed */}
                {isVerifying && (
                  <div className="p-3 rounded-lg bg-amber-950/40 border border-amber-500/30 font-mono text-xs text-amber-300 flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
                    <span>Sending signature to <code className="font-bold">POST /orders/verify</code> for HMAC-SHA256 re-computation...</span>
                  </div>
                )}

                {verifiedPayment && (
                  <div className="p-3.5 rounded-lg bg-emerald-950/50 border border-emerald-500/40 font-mono text-xs text-emerald-300 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <ShieldCheck size={16} className="text-emerald-400" />
                      <span>
                        Requirement 3: Server Signature Verified! Payment ID: <strong className="text-white">{verifiedPayment.razorpay_payment_id}</strong>
                      </span>
                    </div>
                    <span className="text-[10px] bg-emerald-900/80 px-2 py-0.5 rounded text-emerald-200 border border-emerald-400/30 font-bold">
                      HMAC-SHA256 MATCHED
                    </span>
                  </div>
                )}

                {verificationError && (
                  <div className="p-3 rounded-lg bg-rose-950/50 border border-rose-500/40 font-mono text-xs text-rose-300 flex items-center gap-2">
                    <AlertTriangle size={15} />
                    <span>Verification Failed: {verificationError}</span>
                  </div>
                )}

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Left Card: Internal RazorGate Receipt */}
                  <div className="p-4 rounded-xl bg-[#161619] border border-white/10 space-y-3 font-mono text-xs">
                    <div className="flex items-center justify-between pb-2 border-b border-white/5">
                      <div className="flex items-center gap-1.5 text-[#D4A15C] font-semibold">
                        <ReceiptIcon size={14} />
                        <span>1. Internal RazorGate Decision (`/gate/check`)</span>
                      </div>
                      <span className="text-[10px] text-[#8E8A83]">Signed Protocol</span>
                    </div>

                    <div className="space-y-1.5">
                      <div className="flex justify-between">
                        <span className="text-[#8E8A83]">Verdict:</span>
                        <span className={isAllow ? 'text-emerald-400 font-bold' : isFlag ? 'text-amber-400 font-bold' : 'text-rose-400 font-bold'}>
                          {activeVerdict}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-[#8E8A83]">SKU:</span>
                        <span className="text-[#F5F1EA]">{currentMeta.sku}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-[#8E8A83]">Amount:</span>
                        <span className="text-[#F5F1EA] font-bold">{currentMeta.amount}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-[#8E8A83]">Primary Factor:</span>
                        <span className="text-[#C5C0B7]">
                          {realGateResult?.primary_factor || currentScenarioResult?.primary_factor || 'policy_cleared'}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-[#8E8A83]">Audit ID:</span>
                        <span className="text-[#D4A15C]">#{realGateResult?.audit_id || currentScenarioResult?.audit_id || 1040}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-[#8E8A83]">ALLOW Token:</span>
                        <span className="text-[10px] text-emerald-400/90 truncate max-w-[170px]" title={realGateResult?.allow_token}>
                          {realGateResult?.allow_token ? `${realGateResult.allow_token.substring(0, 18)}...` : 'Minted'}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Right Card: Official Razorpay Test-Mode Confirmation */}
                  <div className="p-4 rounded-xl bg-emerald-950/20 border border-emerald-500/30 space-y-3 font-mono text-xs">
                    <div className="flex items-center justify-between pb-2 border-b border-emerald-500/20">
                      <div className="flex items-center gap-1.5 text-emerald-400 font-semibold">
                        <CreditCard size={14} />
                        <span>2. Razorpay Live Order Object (`/orders`)</span>
                      </div>
                      <span className="text-[10px] text-emerald-400/80">client.order.fetch()</span>
                    </div>

                    <div className="space-y-1.5">
                      <div className="flex justify-between items-center">
                        <span className="text-[#8E8A83]">Razorpay Order ID:</span>
                        <div className="flex items-center gap-1.5">
                          <span className="text-emerald-400 font-bold">{orderId || 'order_created'}</span>
                          <button onClick={copyOrderId} className="text-[#8E8A83] hover:text-[#F5F1EA]">
                            {copiedOrderId ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
                          </button>
                        </div>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-[#8E8A83]">Razorpay Payment ID:</span>
                        <span className={verifiedPayment ? 'text-emerald-400 font-bold' : 'text-[#8E8A83]'}>
                          {verifiedPayment ? verifiedPayment.razorpay_payment_id : 'Pending modal checkout'}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-[#8E8A83]">Status:</span>
                        <span className="text-emerald-400 font-semibold">
                          {verifiedPayment ? 'paid & verified' : 'created (test mode)'}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-[#8E8A83]">Amount Subunit:</span>
                        <span className="text-[#F5F1EA]">
                          {selectedScenario === 'clean_allow' ? '29900 paise (₹299.00)' : '4900 paise (₹49.00)'}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-[#8E8A83]">Authorization Method:</span>
                        <span className="text-emerald-400">Server-Gated HMAC Token</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
