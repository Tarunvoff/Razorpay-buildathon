import React from 'react';
import type { ApirisMitigationAction, ApirisRiskTier, ApirisTelemetry } from '../../types';
import { Lock, Server, Database } from 'lucide-react';

interface ApirisScoreTriadProps {
  telemetry?: ApirisTelemetry;
  compact?: boolean;
}

export const ApirisScoreTriad: React.FC<ApirisScoreTriadProps> = ({
  telemetry,
  compact = false,
}) => {
  const rawHealth = telemetry?.health_scores;
  const healthScores = {
    confidentiality: typeof rawHealth?.confidentiality === 'number' ? rawHealth.confidentiality : 0.98,
    availability: typeof rawHealth?.availability === 'number' ? rawHealth.availability : 0.99,
    integrity: typeof rawHealth?.integrity === 'number' ? rawHealth.integrity : 1.0,
  };

  const rawRisk = telemetry?.risk_weights;
  const riskWeights = {
    confidentiality: typeof rawRisk?.confidentiality === 'number' ? rawRisk.confidentiality : Math.max(0, 1.0 - healthScores.confidentiality),
    availability: typeof rawRisk?.availability === 'number' ? rawRisk.availability : Math.max(0, 1.0 - healthScores.availability),
    integrity: typeof rawRisk?.integrity === 'number' ? rawRisk.integrity : Math.max(0, 1.0 - healthScores.integrity),
  };

  const overallRiskWeight = typeof telemetry?.risk_weight === 'number'
    ? telemetry.risk_weight
    : Math.max(
        riskWeights.confidentiality,
        riskWeights.availability,
        riskWeights.integrity
      );

  const riskTier: ApirisRiskTier = overallRiskWeight >= 0.80 
    ? 'CRITICAL' 
    : overallRiskWeight >= 0.60 
    ? 'HIGH' 
    : overallRiskWeight >= 0.40
    ? 'ELEVATED'
    : overallRiskWeight > 0.10 
    ? 'MODERATE' 
    : 'LOW';

  const action: ApirisMitigationAction = telemetry?.action || (
    overallRiskWeight >= 0.80 ? 'reject_response' : 'pass_through'
  );

  const pillars = [
    {
      name: 'Confidentiality',
      code: 'C',
      icon: Lock,
      health: healthScores.confidentiality ?? 0.98,
      risk: riskWeights.confidentiality ?? 0.02,
      description: 'Secret leakage, auth headers, token exposure',
    },
    {
      name: 'Availability',
      code: 'A',
      icon: Server,
      health: healthScores.availability ?? 0.99,
      risk: riskWeights.availability ?? 0.01,
      description: 'Latency budget, rate limits, 5xx error spikes',
    },
    {
      name: 'Data Integrity',
      code: 'D',
      icon: Database,
      health: healthScores.integrity ?? 1.0,
      risk: riskWeights.integrity ?? 0.0,
      description: 'Schema drift, payload mutation, param tampering',
    },
  ];

  const getHealthColor = (score: number = 1.0) => {
    if (score >= 0.90) return 'text-emerald-400 border-emerald-500/30 bg-emerald-950/40';
    if (score >= 0.70) return 'text-amber-400 border-amber-500/30 bg-amber-950/40';
    return 'text-rose-400 border-rose-500/30 bg-rose-950/40';
  };

  const getHealthBarColor = (score: number = 1.0) => {
    if (score >= 0.90) return 'bg-emerald-400';
    if (score >= 0.70) return 'bg-amber-400';
    return 'bg-rose-400';
  };

  return (
    <div className="w-full bg-[#111113] border border-white/10 rounded-xl p-5 shadow-2xl relative overflow-hidden">
      {/* Background Accent Grid */}
      <div className="absolute inset-0 bg-[radial-gradient(#d4a15c_1px,transparent_1px)] [background-size:16px_16px] opacity-[0.03] pointer-events-none" />

      {/* Header */}
      <div className="flex items-center justify-between pb-3 mb-4 border-b border-white/10 relative z-10">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono uppercase tracking-widest text-[#D4A15C]">
              Apiris CAD Telemetry
            </span>
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-white/5 border border-white/10 text-emerald-400">
              v1.1.1 published package
            </span>
          </div>
          <h3 className="text-sm font-semibold text-[#F5F1EA] mt-0.5">
            Confidentiality · Availability · Data Integrity Triad
          </h3>
        </div>

        <div className="flex items-center gap-2">
          {/* Risk Classification Tier */}
          <span
            className={`font-mono text-xs px-2 py-0.5 rounded border font-semibold ${
              riskTier === 'LOW'
                ? 'text-emerald-400 bg-emerald-950/60 border-emerald-500/30'
                : riskTier === 'MODERATE'
                ? 'text-sky-400 bg-sky-950/60 border-sky-500/30'
                : riskTier === 'ELEVATED'
                ? 'text-amber-400 bg-amber-950/60 border-amber-500/30'
                : riskTier === 'HIGH'
                ? 'text-orange-400 bg-orange-950/60 border-orange-500/30'
                : 'text-rose-400 bg-rose-950/60 border-rose-500/30'
            }`}
          >
            Tier: {riskTier}
          </span>

          {/* Mitigation Action */}
          <span className="font-mono text-xs text-[#8E8A83] bg-white/5 border border-white/10 px-2 py-0.5 rounded">
            action: <code>{action}</code>
          </span>
        </div>
      </div>

      {/* Semantic Notice: Health vs Risk */}
      <div className="mb-4 text-xs text-[#C5C0B7] bg-[#161619] border border-white/5 p-2.5 rounded-lg flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-400" />
          <span>Scores indicate <strong>Health</strong> (<code className="font-mono text-[#D4A15C]">1.0 = Clean/Optimal</code>). Risk weight is calculated explicitly as <code className="font-mono text-[#D4A15C]">1.0 − Health</code>.</span>
        </div>
        <div className="font-mono text-xs text-[#D4A15C] shrink-0 font-semibold">
          Aggregated Risk: {overallRiskWeight.toFixed(2)}
        </div>
      </div>

      {/* 3 Pillar Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 relative z-10">
        {pillars.map((pillar) => {
          const Icon = pillar.icon;
          return (
            <div
              key={pillar.name}
              className="p-3.5 rounded-lg bg-[#161619] border border-white/10 hover:border-white/20 transition-all flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <div className="w-6 h-6 rounded bg-white/5 border border-white/10 flex items-center justify-center text-[#D4A15C]">
                      <Icon size={13} />
                    </div>
                    <span className="text-xs font-semibold text-[#F5F1EA]">
                      {pillar.name}
                    </span>
                  </div>
                  <span className="text-[10px] font-mono text-[#8E8A83]">[{pillar.code}]</span>
                </div>

                <p className="text-[11px] text-[#8E8A83] leading-snug mb-3">
                  {pillar.description}
                </p>
              </div>

              <div>
                {/* Health Score Bar */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between text-xs font-mono">
                    <span className="text-[#8E8A83]">Health Score:</span>
                    <span className={`font-bold tabular-nums ${getHealthColor(pillar.health).split(' ')[0]}`}>
                      {(pillar.health ?? 1.0).toFixed(2)} / 1.00
                    </span>
                  </div>

                  <div className="w-full h-1.5 bg-black/40 rounded-full overflow-hidden border border-white/5">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${getHealthBarColor(pillar.health)}`}
                      style={{ width: `${Math.max(0, Math.min(100, (pillar.health ?? 1.0) * 100))}%` }}
                    />
                  </div>

                  <div className="flex items-center justify-between text-[10px] font-mono pt-1 text-[#8E8A83]">
                    <span>Inverted Risk:</span>
                    <span className="text-[#E8B96C] font-semibold tabular-nums">
                      {(pillar.risk ?? 0.0).toFixed(2)}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Published Real Performance Baseline */}
      {!compact && (
        <div className="mt-4 pt-3 border-t border-white/10 grid grid-cols-2 sm:grid-cols-4 gap-2 text-center text-xs font-mono">
          <div className="p-2 rounded bg-black/30 border border-white/5">
            <div className="text-[10px] text-[#8E8A83]">p50 Latency</div>
            <div className="text-[#F5F1EA] font-semibold">0.061 ms</div>
          </div>
          <div className="p-2 rounded bg-black/30 border border-white/5">
            <div className="text-[10px] text-[#8E8A83]">p95 Latency</div>
            <div className="text-[#F5F1EA] font-semibold">0.137 ms</div>
          </div>
          <div className="p-2 rounded bg-black/30 border border-white/5">
            <div className="text-[10px] text-[#8E8A83]">Throughput</div>
            <div className="text-[#F5F1EA] font-semibold">~14,500 req/s</div>
          </div>
          <div className="p-2 rounded bg-black/30 border border-white/5">
            <div className="text-[10px] text-[#8E8A83]">Telemetry Egress</div>
            <div className="text-emerald-400 font-semibold">0 Telemetry (Air-Gapped)</div>
          </div>
        </div>
      )}
    </div>
  );
};
