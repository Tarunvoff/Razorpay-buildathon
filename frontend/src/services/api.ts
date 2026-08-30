import type {
  CreateOrderPayload,
  CreateOrderResponse,
  DecisionRecord,
  GateCheckRequest,
  GateCheckResponse,
  MetricsSummary,
  ScenarioRunResult,
  VerifyOrderPayload,
  VerifyOrderResponse,
} from '../types';


const API_BASE = '';

export const INITIAL_SEED_DECISIONS: DecisionRecord[] = [
  {
    id: 1042,
    timestamp: new Date(Date.now() - 1000 * 120).toISOString(),
    agent_id: 'buyer_enterprise_exec_8832',
    amount_paise: 6500000,
    amount_inr: 65000.0,
    verdict: 'BLOCK',
    confidence: 1.0,
    primary_factor: 'amount_exceeded_ceiling',
    summary:
      'Transaction of ₹65,000.00 BLOCKED: Exceeds policy amount ceiling. Rule reasons: Order amount ₹65,000.00 exceeds policy ceiling of ₹50,000.00.',
    razorpay_order_id: null,
    evidence: {
      apiris: {
        action: 'pass_through',
        risk_weight: 0.05,
        confidence: 0.98,
        
        health_scores: { confidentiality: 0.99, availability: 0.98, integrity: 1.0 },
        risk_weights: { confidentiality: 0.01, availability: 0.02, integrity: 0.0 },
      },
      behavior: {
        flag: false,
        reasons: [],
        session_call_count: 1,
        frequency: 1,
      },
      policy: {
        verdict: 'BLOCK',
        primary_factor: 'amount_exceeded_ceiling',
        reasons: ['Order amount ₹65,000.00 exceeds policy ceiling of ₹50,000.00'],
        amount_inr: 65000.0,
      },
    },
  },
  {
    id: 1041,
    timestamp: new Date(Date.now() - 1000 * 300).toISOString(),
    agent_id: 'buyer_burst_dev_4219',
    amount_paise: 4900,
    amount_inr: 49.0,
    verdict: 'FLAG',
    confidence: 0.85,
    primary_factor: 'behavior_anomaly',
    summary:
      'Transaction of ₹49.00 FLAGGED for verification: Behavioral anomaly triggered (call_frequency_exceeded, 6 calls in rolling window).',
    razorpay_order_id: 'order_TUkozs6yo8Ju23',
    evidence: {
      apiris: {
        action: 'pass_through',
        risk_weight: 0.12,
        confidence: 0.94,
        
        health_scores: { confidentiality: 0.95, availability: 0.92, integrity: 0.98 },
        risk_weights: { confidentiality: 0.05, availability: 0.08, integrity: 0.02 },
      },
      behavior: {
        flag: true,
        reasons: ['call_frequency_exceeded: 6 calls in 300s window exceeds threshold 5'],
        session_call_count: 6,
        frequency: 6,
      },
      policy: {
        verdict: 'FLAG',
        primary_factor: 'behavior_anomaly',
        reasons: ['Behavioral anomalies detected: call_frequency_exceeded'],
        amount_inr: 49.0,
      },
    },
  },
  {
    id: 1040,
    timestamp: new Date(Date.now() - 1000 * 600).toISOString(),
    agent_id: 'buyer_h100_cluster_1904',
    amount_paise: 29900,
    amount_inr: 299.0,
    verdict: 'ALLOW',
    confidence: 1.0,
    primary_factor: 'policy_cleared',
    summary: 'Transaction of ₹299.00 APPROVED: All policy and telemetry safety checks passed.',
    razorpay_order_id: 'order_TUkjWMgUTBNytJ',
    evidence: {
      apiris: {
        action: 'pass_through',
        risk_weight: 0.02,
        confidence: 0.99,
        
        health_scores: { confidentiality: 1.0, availability: 0.98, integrity: 1.0 },
        risk_weights: { confidentiality: 0.0, availability: 0.02, integrity: 0.0 },
      },
      behavior: {
        flag: false,
        reasons: [],
        session_call_count: 1,
        frequency: 1,
      },
      policy: {
        verdict: 'ALLOW',
        primary_factor: 'policy_cleared',
        reasons: ['All policy and telemetry safety checks passed'],
        amount_inr: 299.0,
      },
    },
  },
];

export const DEFAULT_METRICS: MetricsSummary = {
  ledger: {
    total_decisions: 184,
    allow_count: 148,
    flag_count: 24,
    block_count: 12,
  },
  apiris_specs: {
    version: '1.1.1',
    p50_latency_ms: 0.061,
    p95_latency_ms: 0.137,
    throughput_rps_core: 14500,
    memory_footprint_mb: 24,
    cve_count: 65,
    vendor_count: 47,
    telemetry_sent: 0,
    air_gapped: true,
  },
  policy_ceiling_inr: 50000.0,
  token_ttl_seconds: 30,
};

export async function fetchHealth(): Promise<{ status: string; service: string }> {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) throw new Error('Health check failed');
  return res.json();
}

export async function fetchDecisions(limit = 50, offset = 0, agentId?: string): Promise<DecisionRecord[]> {
  try {
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    if (agentId) params.append('agent_id', agentId);
    const res = await fetch(`${API_BASE}/decisions?${params.toString()}`);
    if (!res.ok) throw new Error('Failed to fetch decisions');
    const data = await res.json();
    return data;
  } catch {
    return INITIAL_SEED_DECISIONS;
  }
}

export async function fetchDecisionById(id: number): Promise<DecisionRecord | null> {
  try {
    const res = await fetch(`${API_BASE}/decisions/${id}`);
    if (!res.ok) throw new Error(`Decision ${id} not found`);
    return res.json();
  } catch {
    return INITIAL_SEED_DECISIONS.find((d) => d.id === id) || null;
  }
}

export async function fetchMetricsSummary(): Promise<MetricsSummary> {
  try {
    const res = await fetch(`${API_BASE}/metrics/summary`);
    if (!res.ok) throw new Error('Failed to fetch metrics summary');
    return res.json();
  } catch {
    return DEFAULT_METRICS;
  }
}

export async function runScenario(
  scenario: 'clean_allow' | 'behavior_flag' | 'forced_failure_block',
  customBudgetPaise?: number
): Promise<ScenarioRunResult> {
  const res = await fetch(`${API_BASE}/demo/run-scenario`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ scenario, custom_budget_paise: customBudgetPaise }),
  });
  if (!res.ok) {
    const errText = await res.text();
    throw new Error(`Scenario run failed: ${errText}`);
  }
  return res.json();
}

export function subscribeDecisionStream(
  onEvent: (event: Record<string, unknown>) => void,
  onStatusChange?: (status: 'connected' | 'disconnected' | 'reconnecting') => void
): () => void {
  let eventSource: EventSource | null = null;
  let retryTimeout: number | null = null;
  let isClosed = false;

  function connect() {
    if (isClosed) return;
    try {
      eventSource = new EventSource(`${API_BASE}/decisions/stream`);

      eventSource.onopen = () => {
        onStatusChange?.('connected');
      };

      eventSource.onmessage = (e) => {
        try {
          const parsed = JSON.parse(e.data);
          onEvent(parsed);
        } catch (err) {
          console.error('Failed to parse SSE payload:', err);
        }
      };

      eventSource.onerror = () => {
        onStatusChange?.('disconnected');
        if (eventSource) {
          eventSource.close();
          eventSource = null;
        }
        if (!isClosed) {
          onStatusChange?.('reconnecting');
          retryTimeout = window.setTimeout(connect, 3000);
        }
      };
    } catch {
      onStatusChange?.('disconnected');
      if (!isClosed) {
        retryTimeout = window.setTimeout(connect, 5000);
      }
    }
  }

  connect();

  return () => {
    isClosed = true;
    if (retryTimeout) clearTimeout(retryTimeout);
    if (eventSource) {
      eventSource.close();
      eventSource = null;
    }
  };
}

export async function checkGate(payload: GateCheckRequest): Promise<GateCheckResponse> {
  const res = await fetch(`${API_BASE}/gate/check`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const errText = await res.text();
    throw new Error(`Gate check failed: ${errText}`);
  }
  return res.json();
}

export async function createOrder(payload: CreateOrderPayload): Promise<CreateOrderResponse> {
  const res = await fetch(`${API_BASE}/orders`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const errText = await res.text();
    throw new Error(`Order creation failed: ${errText}`);
  }
  return res.json();
}

export async function verifyOrder(payload: VerifyOrderPayload): Promise<VerifyOrderResponse> {
  const res = await fetch(`${API_BASE}/orders/verify`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const errText = await res.text();
    throw new Error(`Signature verification failed: ${errText}`);
  }
  return res.json();
}

export async function askBuyerAgent(
  intent: string,
  category = 'all',
  maxBudgetInr = 5000.0
): Promise<ScenarioRunResult> {
  const res = await fetch(`${API_BASE}/agent/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ intent, category, max_budget_inr: maxBudgetInr }),
  });
  if (!res.ok) {
    const errText = await res.text();
    throw new Error(`Free-form Agent execution failed: ${errText}`);
  }
  return res.json();
}

export function loadRazorpayScript(): Promise<boolean> {
  return new Promise((resolve) => {
    if (window.Razorpay) {
      resolve(true);
      return;
    }
    const script = document.createElement('script');
    script.src = 'https://checkout.razorpay.com/v1/checkout.js';
    script.onload = () => resolve(true);
    script.onerror = () => resolve(false);
    document.body.appendChild(script);
  });
}


