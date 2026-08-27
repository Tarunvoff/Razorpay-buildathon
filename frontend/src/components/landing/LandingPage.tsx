import React from 'react';
import type { SurfaceTab } from '../common/Header';
import { PolicyWaterfall } from '../common/PolicyWaterfall';
import { ArrowRight, Terminal, Activity, Bug } from 'lucide-react';

interface LandingPageProps {
  onNavigate: (tab: SurfaceTab) => void;
  onLaunchDemoScenario?: () => void;
}

export const LandingPage: React.FC<LandingPageProps> = ({
  onNavigate,
}) => {
  return (
    <div className="space-y-16 pb-20">
      {/* 1. HERO SECTION */}
      <section className="relative pt-12 pb-8 overflow-hidden">
        {/* Subtle Ambient Background Gradients */}
        <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[700px] h-[350px] bg-[#D4A15C]/5 blur-[120px] rounded-full pointer-events-none" />

        <div className="max-w-5xl mx-auto text-center relative z-10 px-4">
          {/* Track Badge */}
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#161619] border border-[#D4A15C]/30 text-xs font-mono text-[#E8B96C] mb-6">
            <span className="w-2 h-2 rounded-full bg-[#D4A15C] animate-ping" />
            <span>Razorpay Buildathon — Track 01 Submission</span>
          </div>

          {/* Headline */}
          <h1 className="text-4xl sm:text-6xl font-extrabold tracking-tight text-[#F5F1EA] leading-[1.1] mb-6">
            The trust layer that lets AI agents <span className="text-transparent bg-clip-text bg-gradient-to-r from-[#E8B96C] via-[#D4A15C] to-[#C48C3D]">actually pay.</span>
          </h1>

          {/* Sub-line */}
          <p className="max-w-3xl mx-auto text-base sm:text-lg text-[#C5C0B7] leading-relaxed mb-8">
            Every autonomous money action is explainable, bounded, and gated by a deterministic policy engine — with exactly three verdicts: <span className="font-mono text-emerald-400 font-semibold">ALLOW</span>, <span className="font-mono text-amber-400 font-semibold">FLAG</span>, and <span className="font-mono text-rose-400 font-semibold">BLOCK</span>.
          </p>

          {/* CTAs */}
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-12">
            <button
              onClick={() => onNavigate('walkthrough')}
              className="w-full sm:w-auto px-6 py-3.5 rounded-xl bg-[#D4A15C] hover:bg-[#E8B96C] text-black font-semibold text-sm shadow-[0_0_25px_rgba(212,161,92,0.3)] transition-all flex items-center justify-center gap-2"
            >
              <Terminal size={16} />
              <span>Watch it gate a live transaction</span>
              <ArrowRight size={15} />
            </button>

            <button
              onClick={() => onNavigate('dashboard')}
              className="w-full sm:w-auto px-6 py-3.5 rounded-xl bg-[#161619] hover:bg-[#1F1F24] border border-white/10 text-[#F5F1EA] font-semibold text-sm transition-all flex items-center justify-center gap-2"
            >
              <Activity size={16} className="text-emerald-400" />
              <span>See the live audit trail</span>
            </button>
          </div>

          {/* Key System Metrics Strip */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 max-w-4xl mx-auto text-left font-mono">
            <div className="p-3.5 rounded-lg bg-[#111113] border border-white/10">
              <div className="text-[11px] text-[#8E8A83]">p50 Scoring Latency</div>
              <div className="text-base font-bold text-[#F5F1EA] mt-0.5">0.061 ms</div>
              <div className="text-[10px] text-emerald-400">Published Apiris v1.1.1</div>
            </div>

            <div className="p-3.5 rounded-lg bg-[#111113] border border-white/10">
              <div className="text-[11px] text-[#8E8A83]">Deterministic Token</div>
              <div className="text-base font-bold text-[#F5F1EA] mt-0.5">HMAC · 30s TTL</div>
              <div className="text-[10px] text-[#D4A15C]">No self-reported auth</div>
            </div>

            <div className="p-3.5 rounded-lg bg-[#111113] border border-white/10">
              <div className="text-[11px] text-[#8E8A83]">Safety Path LLM</div>
              <div className="text-base font-bold text-[#F5F1EA] mt-0.5">0 Hallucinations</div>
              <div className="text-[10px] text-emerald-400">Pure template explainer</div>
            </div>

            <div className="p-3.5 rounded-lg bg-[#111113] border border-white/10">
              <div className="text-[11px] text-[#8E8A83]">Air-Gapped Telemetry</div>
              <div className="text-base font-bold text-[#F5F1EA] mt-0.5">0 Bytes Egress</div>
              <div className="text-[10px] text-[#8E8A83]">Local offline evaluation</div>
            </div>
          </div>
        </div>
      </section>

      {/* 2. WHY NOW SECTION */}
      <section className="max-w-5xl mx-auto px-4">
        <div className="p-6 sm:p-8 rounded-2xl bg-[#111113] border border-white/10 relative overflow-hidden">
          <div className="max-w-3xl">
            <div className="text-xs font-mono uppercase tracking-widest text-[#D4A15C] mb-2">
              Context & Protocol Landscape
            </div>
            <h2 className="text-2xl font-bold text-[#F5F1EA] mb-4">
              Why Now: The Autonomous Agent Commerce Shift
            </h2>
            <p className="text-sm sm:text-base text-[#C5C0B7] leading-relaxed mb-4">
              With NPCI Unified Agentic Payments (UAP) initiative and the emerging Google AP2, ACP, and x402 protocol race, AI agents are transitioning from informational chat assistants to autonomous economic actors. But letting an LLM invoke money APIs directly is catastrophic without deterministic boundaries.
            </p>
            <p className="text-xs sm:text-sm text-[#8E8A83] font-mono leading-relaxed bg-black/40 p-3.5 rounded-lg border border-white/5">
              <strong className="text-[#E8B96C]">Scope Discipline:</strong> RazorGate is <em>inspired by</em> the ACP/AP2/x402 protocol space rather than claiming formal compliance with any single unfinalized draft. We build a clean, typed 6-step A2A protocol that interfaces natively with Razorpay test-mode infrastructure.
            </p>
          </div>
        </div>
      </section>

      {/* 3. HOW IT DECIDES: POLICY WATERFALL */}
      <section className="max-w-5xl mx-auto px-4">
        <div className="mb-6 text-center sm:text-left">
          <div className="text-xs font-mono uppercase tracking-widest text-[#D4A15C] mb-1">
            Deterministic Decision Tree
          </div>
          <h2 className="text-2xl font-bold text-[#F5F1EA]">
            How RazorGate Decides: Hard Hierarchy, First-Match-Wins
          </h2>
          <p className="text-sm text-[#8E8A83] mt-1">
            Rules are evaluated in strict order. Probabilistic signals can never override hard financial ceilings.
          </p>
        </div>

        <PolicyWaterfall amountInr={299.0} riskWeight={0.05} hasBehaviorFlag={false} activeVerdict="ALLOW" />
      </section>

      {/* 4. UNDER THE HOOD: 3 CORE ENGINES */}
      <section className="max-w-5xl mx-auto px-4">
        <div className="mb-6 text-center sm:text-left">
          <div className="text-xs font-mono uppercase tracking-widest text-[#D4A15C] mb-1">
            Real Engineering Under The Hood
          </div>
          <h2 className="text-2xl font-bold text-[#F5F1EA]">
            Three Decoupled, Production-Grade Pillars
          </h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {/* Card 1: Apiris */}
          <div className="p-5 rounded-xl bg-[#111113] border border-white/10 hover:border-[#D4A15C]/30 transition-all flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-3">
                <span className="font-mono text-xs text-[#D4A15C] bg-[#D4A15C]/10 px-2 py-0.5 rounded border border-[#D4A15C]/20">
                  PyPI: apiris==1.1.1
                </span>
                <span className="text-xs text-[#8E8A83] font-mono">0.061ms p50</span>
              </div>
              <h3 className="text-base font-bold text-[#F5F1EA] mb-2">
                `apiris` CAD Scoring
              </h3>
              <p className="text-xs text-[#8E8A83] leading-relaxed mb-4">
                Real, independently published security package scoring Confidentiality, Availability, and Data Integrity (1.0 = clean health). Evaluates API payload defect rates with zero telemetry egress.
              </p>
            </div>

            <div className="pt-3 border-t border-white/5 font-mono text-[11px] text-[#C5C0B7] space-y-1">
              <div><code>ApirisClient</code></div>
              <div><code>ObservationEvaluator</code></div>
              <div className="text-emerald-400">47 vendors / 65 CVEs</div>
            </div>
          </div>

          {/* Card 2: Gate Engine */}
          <div className="p-5 rounded-xl bg-[#111113] border border-white/10 hover:border-[#D4A15C]/30 transition-all flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-3">
                <span className="font-mono text-xs text-[#D4A15C] bg-[#D4A15C]/10 px-2 py-0.5 rounded border border-[#D4A15C]/20">
                  policy.yaml
                </span>
                <span className="text-xs text-emerald-400 font-mono">Deterministic</span>
              </div>
              <h3 className="text-base font-bold text-[#F5F1EA] mb-2">
                Gate & Policy Engine
              </h3>
              <p className="text-xs text-[#8E8A83] leading-relaxed mb-4">
                Pure state function combining ceiling bounds, inverted Apiris risk weights, and rolling session anomaly detection. Issues cryptographically signed HMAC ALLOW tokens with 30s TTL.
              </p>
            </div>

            <div className="pt-3 border-t border-white/5 font-mono text-[11px] text-[#C5C0B7] space-y-1">
              <div><code>PolicyDecision</code></div>
              <div><code>HMAC-SHA256 Token Mint</code></div>
              <div className="text-[#D4A15C]">No self-reported auth</div>
            </div>
          </div>

          {/* Card 3: A2A Protocol */}
          <div className="p-5 rounded-xl bg-[#111113] border border-white/10 hover:border-[#D4A15C]/30 transition-all flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-3">
                <span className="font-mono text-xs text-[#D4A15C] bg-[#D4A15C]/10 px-2 py-0.5 rounded border border-[#D4A15C]/20">
                  Pydantic Schemas
                </span>
                <span className="text-xs text-sky-400 font-mono">6-Step Flow</span>
              </div>
              <h3 className="text-base font-bold text-[#F5F1EA] mb-2">
                A2A Commerce Protocol
              </h3>
              <p className="text-xs text-[#8E8A83] leading-relaxed mb-4">
                End-to-end multi-agent protocol between Buyer Agent and Merchant Agent. Enforces capability discovery, dynamic comparative reasoning, signed mandates, and explainable receipts.
              </p>
            </div>

            <div className="pt-3 border-t border-white/5 font-mono text-[11px] text-[#C5C0B7] space-y-1">
              <div><code>AgentCard → TaskRequest</code></div>
              <div><code>PaymentMandate (Signed)</code></div>
              <div className="text-sky-400">Verbatim Reasoning</div>
            </div>
          </div>
        </div>
      </section>

      {/* 5. PROOF & BUG-CATCHING SECTION */}
      <section className="max-w-5xl mx-auto px-4">
        <div className="p-6 sm:p-8 rounded-2xl bg-[#111113] border border-white/10">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 mb-6 border-b border-white/10">
            <div>
              <div className="text-xs font-mono uppercase tracking-widest text-emerald-400 mb-1">
                Engineering Rigor & Proven Reliability
              </div>
              <h2 className="text-2xl font-bold text-[#F5F1EA]">
                64 Automated Tests · 3 Live Reproducibility Runs
              </h2>
            </div>
            <div className="px-3.5 py-1.5 rounded-lg bg-emerald-950/60 border border-emerald-500/40 text-emerald-400 font-mono text-xs font-semibold shrink-0">
              ✓ All 64 Tests Passing
            </div>
          </div>

          <p className="text-sm text-[#C5C0B7] leading-relaxed mb-6">
            Unlike hackathon prototypes that paper over edge cases, RazorGate's engineering process proactively surfaced, root-caused, and wrote automated regression tests for real production-shaped failure modes:
          </p>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 font-mono text-xs">
            {/* Bug 1 */}
            <div className="p-4 rounded-lg bg-[#161619] border border-white/5">
              <div className="flex items-center gap-2 text-rose-400 font-semibold mb-2">
                <Bug size={14} />
                <span>1. Zero-Threshold Bug</span>
              </div>
              <p className="text-[11px] text-[#8E8A83] font-sans leading-relaxed">
                Apiris config defaults had 0.0 thresholds, causing every clean call to read as maximal risk. Root-caused via labeled clean corpus calibration to 0.40/0.40/0.70.
              </p>
            </div>

            {/* Bug 2 */}
            <div className="p-4 rounded-lg bg-[#161619] border border-white/5">
              <div className="flex items-center gap-2 text-amber-400 font-semibold mb-2">
                <Bug size={14} />
                <span>2. Invented Vocabulary</span>
              </div>
              <p className="text-[11px] text-[#8E8A83] font-sans leading-relaxed">
                An intermediate PROCEED/WARNED layer briefly existed. Eliminated entirely — keeping only Apiris actions and RazorGate ALLOW/FLAG/BLOCK.
              </p>
            </div>

            {/* Bug 3 */}
            <div className="p-4 rounded-lg bg-[#161619] border border-white/5">
              <div className="flex items-center gap-2 text-[#E8B96C] font-semibold mb-2">
                <Bug size={14} />
                <span>3. Confidence Collapse</span>
              </div>
              <p className="text-[11px] text-[#8E8A83] font-sans leading-relaxed">
                Confidence had clamped to flat 0.92 regardless of severity. Replaced with dynamic boundary-distance scaling across risk tiers.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* 6. FOOTER CTA */}
      <section className="max-w-5xl mx-auto px-4 text-center">
        <div className="p-8 rounded-2xl bg-gradient-to-b from-[#161619] to-[#111113] border border-[#D4A15C]/20 shadow-2xl">
          <h3 className="text-2xl font-bold text-[#F5F1EA] mb-3">
            Experience the Control Room Live
          </h3>
          <p className="text-sm text-[#C5C0B7] max-w-xl mx-auto mb-6">
            Watch real Server-Sent Events stream decisions, inspect the policy hierarchy trace per-transaction, and replay the A2A negotiation.
          </p>

          <div className="flex justify-center gap-4">
            <button
              onClick={() => onNavigate('dashboard')}
              className="px-6 py-3 rounded-xl bg-[#D4A15C] hover:bg-[#E8B96C] text-black font-semibold text-sm shadow-lg transition-all flex items-center gap-2"
            >
              <span>Enter Live Dashboard</span>
              <ArrowRight size={15} />
            </button>
          </div>
        </div>
      </section>
    </div>
  );
};
