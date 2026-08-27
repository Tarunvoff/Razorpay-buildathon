import React from 'react';
import type { ApirisRiskTier, Verdict } from '../../types';
import { ShieldCheck, ShieldAlert, ShieldX } from 'lucide-react';

interface VerdictBadgeProps {
  verdict: Verdict;
  confidence?: number;
  riskTier?: ApirisRiskTier;
  size?: 'sm' | 'md' | 'lg';
  showConfidence?: boolean;
}

export const VerdictBadge: React.FC<VerdictBadgeProps> = ({
  verdict,
  confidence,
  riskTier,
  size = 'md',
  showConfidence = true,
}) => {
  const getStyles = () => {
    switch (verdict) {
      case 'ALLOW':
        return {
          bg: 'bg-emerald-950/60',
          border: 'border-emerald-500/40',
          text: 'text-emerald-400',
          dot: 'bg-emerald-400',
          glow: 'shadow-[0_0_12px_rgba(74,222,128,0.15)]',
          icon: ShieldCheck,
          label: 'ALLOW',
        };
      case 'FLAG':
        return {
          bg: 'bg-amber-950/60',
          border: 'border-amber-500/40',
          text: 'text-amber-400',
          dot: 'bg-amber-400',
          glow: 'shadow-[0_0_12px_rgba(245,166,35,0.15)]',
          icon: ShieldAlert,
          label: 'FLAG',
        };
      case 'BLOCK':
        return {
          bg: 'bg-rose-950/60',
          border: 'border-rose-500/40',
          text: 'text-rose-400',
          dot: 'bg-rose-400',
          glow: 'shadow-[0_0_12px_rgba(239,68,68,0.15)]',
          icon: ShieldX,
          label: 'BLOCK',
        };
    }
  };

  const style = getStyles();
  const Icon = style.icon;

  const sizeClasses = {
    sm: 'px-2 py-0.5 text-xs gap-1.5',
    md: 'px-2.5 py-1 text-xs gap-2',
    lg: 'px-3.5 py-1.5 text-sm gap-2.5 font-medium',
  }[size];

  const iconSizes = {
    sm: 12,
    md: 14,
    lg: 16,
  }[size];

  const tierColors: Record<ApirisRiskTier, string> = {
    LOW: 'text-emerald-400/80 bg-emerald-950/40 border-emerald-500/20',
    MODERATE: 'text-sky-400/80 bg-sky-950/40 border-sky-500/20',
    ELEVATED: 'text-amber-400/80 bg-amber-950/40 border-amber-500/20',
    HIGH: 'text-orange-400/80 bg-orange-950/40 border-orange-500/20',
    CRITICAL: 'text-rose-400/80 bg-rose-950/40 border-rose-500/20',
  };

  return (
    <div className="inline-flex items-center gap-1.5">
      <div
        className={`inline-flex items-center rounded-md border ${style.bg} ${style.border} ${style.text} ${style.glow} ${sizeClasses} font-mono uppercase tracking-wider font-semibold`}
      >
        <span className={`w-1.5 h-1.5 rounded-full ${style.dot} animate-pulse`} />
        <Icon size={iconSizes} className="shrink-0" />
        <span>{style.label}</span>
        {showConfidence && confidence !== undefined && (
          <span className="opacity-75 text-[0.9em] font-normal lowercase pl-1 border-l border-white/10 tabular-nums">
            {(confidence * 100).toFixed(0)}%
          </span>
        )}
      </div>

      {riskTier && (
        <span
          className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-mono uppercase border ${tierColors[riskTier]}`}
          title="Apiris CAD Risk Classification Tier"
        >
          {riskTier}
        </span>
      )}
    </div>
  );
};
