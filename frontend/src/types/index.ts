export type Verdict = 'ALLOW' | 'FLAG' | 'BLOCK';

export type ApirisRiskTier = 'LOW' | 'MODERATE' | 'ELEVATED' | 'HIGH' | 'CRITICAL';

export type ApirisMitigationAction =
  | 'pass_through'
  | 'mask_sensitive_fields'
  | 'serve_stale_cache'
  | 'delay_response'
  | 'downgrade_fidelity'
  | 'reject_response';

export interface ApirisHealthScores {
  confidentiality: number;
  availability: number;
  integrity: number;
}

export interface ApirisRiskWeights {
  confidentiality: number;
  availability: number;
  integrity: number;
}

export interface ApirisTelemetry {
  action?: ApirisMitigationAction;
  risk_weight: number;
  confidence?: number;
  risk_classification?: ApirisRiskTier;
  health_scores?: ApirisHealthScores;
  risk_weights?: ApirisRiskWeights;
  justification?: string;
}

export interface BehaviorTelemetry {
  flag: boolean;
  reasons: string[];
  session_call_count?: number;
  frequency?: number;
  amount_deviation_zscore?: number;
  window_mean_amount?: number;
  window_std_amount?: number;
}

export interface PolicyTelemetry {
  verdict: Verdict;
  primary_factor: string;
  reasons: string[];
  amount_inr: number;
}

export interface DecisionEvidence {
  apiris?: ApirisTelemetry;
  behavior?: BehaviorTelemetry;
  policy?: PolicyTelemetry;
  request?: Record<string, unknown>;
  allow_token?: string;
  [key: string]: unknown;
}

export interface DecisionRecord {
  id: number;
  timestamp: string;
  agent_id: string;
  amount_paise: number;
  amount_inr: number;
  verdict: Verdict;
  confidence: number;
  primary_factor: string;
  summary: string;
  evidence: DecisionEvidence;
  evidence_json?: string;
  razorpay_order_id?: string | null;
  allow_token?: string | null;
}

export interface AgentOffer {
  sku: string;
  name: string;
  description: string;
  category: string;
  amount_paise: number;
  currency: string;
  unit: string;
  specs: Record<string, unknown>;
  gate_disclosure: string;
}

export interface PaymentMandateData {
  mandate_id: string;
  buyer_agent_id: string;
  merchant_id: string;
  sku: string;
  amount_paise: number;
  currency: string;
  timestamp: number;
  reasoning: string;
  signature: string;
  receipt_ref?: string;
}

export interface A2AStep {
  step: 'capability_discovery' | 'task_request' | 'received_offers' | 'payment_mandate' | 'receipt' | string;
  timestamp: number;
  data: Record<string, unknown>;
}

export interface ReceiptData {
  mandate_id: string;
  buyer_agent_id: string;
  merchant_id: string;
  sku: string;
  amount_paise: number;
  amount_inr: number;
  currency: string;
  verdict: Verdict;
  primary_factor: string;
  summary: string;
  confidence: number;
  audit_id?: number | null;
  order?: Record<string, unknown> | null;
  evidence?: Record<string, unknown>;
  error?: string | null;
}

export interface ScenarioRunResult {
  scenario: 'clean_allow' | 'behavior_flag' | 'forced_failure_block' | string;
  agent_id: string;
  receipt: ReceiptData;
  transcript: A2AStep[];
  explanation: string;
  verdict: Verdict;
  primary_factor: string;
  confidence: number;
  amount_inr: number;
  audit_id?: number;
  order?: Record<string, unknown> | null;
}

export interface MetricsSummary {
  ledger: {
    total_decisions: number;
    allow_count: number;
    flag_count: number;
    block_count: number;
  };
  apiris_specs: {
    version: string;
    p50_latency_ms: number;
    p95_latency_ms: number;
    throughput_rps_core: number;
    memory_footprint_mb: number;
    cve_count: number;
    vendor_count: number;
    telemetry_sent: number;
    air_gapped: boolean;
  };
  policy_ceiling_inr: number;
  token_ttl_seconds: number;
}

export interface GateCheckRequest {

  amount: number;
  currency?: string;
  agent_id?: string;
  receipt?: string;
  category?: string;
  action?: string;
}

export interface GateCheckResponse {
  verdict: Verdict;
  confidence: number;
  primary_factor: string;
  summary: string;
  allow_token?: string;
  audit_id: number;
  explanation_record?: Record<string, unknown>;
  apiris_score?: Record<string, unknown>;
  behavior_signal?: Record<string, unknown>;
  decision?: Record<string, unknown>;
}

export interface CreateOrderPayload {
  agent_id: string;
  amount_paise: number;
  receipt: string;
  allow_token: string;
  currency?: string;
  audit_id?: number;
  notes?: Record<string, unknown>;
}

export interface CreateOrderResponse {
  status: string;
  order: {
    id: string;
    entity: string;
    amount: number;
    currency: string;
    status: string;
    receipt?: string;
    [key: string]: unknown;
  };
  audit_id?: number;
  key_id?: string;
}

export interface VerifyOrderPayload {
  razorpay_payment_id: string;
  razorpay_order_id: string;
  razorpay_signature: string;
  audit_id?: number;
}

export interface VerifyOrderResponse {
  status: string;
  verified: boolean;
  razorpay_payment_id: string;
  razorpay_order_id: string;
  audit_id?: number;
  order: Record<string, unknown>;
}

declare global {
  interface Window {
    Razorpay?: any;
  }
}

