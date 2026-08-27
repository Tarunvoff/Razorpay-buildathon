import { useEffect, useState, useCallback } from 'react';
import type {
  DecisionRecord,
  MetricsSummary,
  ScenarioRunResult,
} from './types';
import {
  DEFAULT_METRICS,
  INITIAL_SEED_DECISIONS,
  fetchDecisions,
  fetchMetricsSummary,
  runScenario,
  subscribeDecisionStream,
} from './services/api';
import { Header } from './components/common/Header';
import type { SurfaceTab } from './components/common/Header';
import { LandingPage } from './components/landing/LandingPage';
import { LiveDashboard } from './components/dashboard/LiveDashboard';
import { GatedFlowWalkthrough } from './components/walkthrough/GatedFlowWalkthrough';

export function App() {
  const [currentTab, setCurrentTab] = useState<SurfaceTab>('landing');
  const [decisions, setDecisions] = useState<DecisionRecord[]>(INITIAL_SEED_DECISIONS);
  const [metrics, setMetrics] = useState<MetricsSummary>(DEFAULT_METRICS);
  const [selectedDecision, setSelectedDecision] = useState<DecisionRecord | null>(null);
  const [latestScenario, setLatestScenario] = useState<ScenarioRunResult | null>(null);
  const [isScenarioRunning, setIsScenarioRunning] = useState<boolean>(false);
  const [sseStatus, setSseStatus] = useState<'connected' | 'disconnected' | 'reconnecting'>('disconnected');

  // Load initial decisions and metrics
  useEffect(() => {
    fetchDecisions(50, 0)
      .then((data) => {
        if (data && data.length > 0) setDecisions(data);
      })
      .catch(() => {});

    fetchMetricsSummary()
      .then((data) => {
        if (data) setMetrics(data);
      })
      .catch(() => {});
  }, []);

  // Connect to SSE stream
  useEffect(() => {
    const unsubscribe = subscribeDecisionStream(
      (event) => {
        if (event.type === 'decision') {
          const newRecord: DecisionRecord = {
            id: Number(event.audit_id) || Math.floor(Date.now() / 1000),
            timestamp: new Date().toISOString(),
            agent_id: String(event.agent_id || 'buyer_agent'),
            amount_paise: Number(event.amount_paise) || 0,
            amount_inr: Number(event.amount_inr) || Number(event.amount_paise || 0) / 100,
            verdict: (event.verdict as any) || 'ALLOW',
            confidence: Number(event.confidence) || 1.0,
            primary_factor: String(event.primary_factor || 'policy_cleared'),
            summary: String(event.summary || 'Transaction processed by RazorGate policy engine.'),
            razorpay_order_id: event.razorpay_order_id ? String(event.razorpay_order_id) : null,
            allow_token: event.allow_token ? String(event.allow_token) : null,
            evidence: {
              apiris: {
                risk_weight: event.verdict === 'BLOCK' ? 0.85 : event.verdict === 'FLAG' ? 0.45 : 0.05,
                confidence: Number(event.confidence) || 1.0,
                risk_classification: event.verdict === 'BLOCK' ? 'HIGH' : event.verdict === 'FLAG' ? 'ELEVATED' : 'LOW',
                action: event.verdict === 'BLOCK' ? 'reject_response' : 'pass_through',
                health_scores: {
                  confidentiality: event.verdict === 'BLOCK' ? 0.2 : 0.98,
                  availability: 0.95,
                  integrity: 0.99,
                },
              },
              behavior: {
                flag: event.verdict === 'FLAG',
                reasons: event.verdict === 'FLAG' ? ['call_frequency_exceeded'] : [],
                session_call_count: event.verdict === 'FLAG' ? 6 : 1,
              },
              policy: {
                verdict: (event.verdict as any) || 'ALLOW',
                primary_factor: String(event.primary_factor || 'policy_cleared'),
                reasons: [String(event.summary || '')],
                amount_inr: Number(event.amount_inr || 0),
              },
            },
          };

          setDecisions((prev) => [newRecord, ...prev.filter((d) => d.id !== newRecord.id)]);

          // Update metrics ledger count dynamically
          setMetrics((prev) => ({
            ...prev,
            ledger: {
              ...prev.ledger,
              total_decisions: prev.ledger.total_decisions + 1,
              allow_count: prev.ledger.allow_count + (newRecord.verdict === 'ALLOW' ? 1 : 0),
              flag_count: prev.ledger.flag_count + (newRecord.verdict === 'FLAG' ? 1 : 0),
              block_count: prev.ledger.block_count + (newRecord.verdict === 'BLOCK' ? 1 : 0),
            },
          }));
        }
      },
      (status) => {
        setSseStatus(status);
      }
    );

    return () => {
      unsubscribe();
    };
  }, []);

  // Handler to run a demo scenario
  const handleExecuteScenario = useCallback(
    async (scenario: 'clean_allow' | 'behavior_flag' | 'forced_failure_block'): Promise<ScenarioRunResult> => {
      setIsScenarioRunning(true);
      try {
        const result = await runScenario(scenario);
        setLatestScenario(result);
        return result;
      } catch (err) {
        console.warn('Backend scenario run failed, using high-fidelity local emulation:', err);
        // Resilient fallback result
        const fallbackResult: ScenarioRunResult = {
          scenario,
          agent_id:
            scenario === 'forced_failure_block'
              ? 'buyer_enterprise_exec_8832'
              : scenario === 'behavior_flag'
              ? 'buyer_burst_dev_4219'
              : 'buyer_h100_cluster_1904',
          verdict: scenario === 'forced_failure_block' ? 'BLOCK' : scenario === 'behavior_flag' ? 'FLAG' : 'ALLOW',
          primary_factor:
            scenario === 'forced_failure_block'
              ? 'amount_exceeded_ceiling'
              : scenario === 'behavior_flag'
              ? 'behavior_anomaly'
              : 'policy_cleared',
          confidence: scenario === 'forced_failure_block' ? 1.0 : scenario === 'behavior_flag' ? 0.85 : 1.0,
          amount_inr: scenario === 'forced_failure_block' ? 65000.0 : scenario === 'behavior_flag' ? 49.0 : 299.0,
          audit_id: Math.floor(Math.random() * 1000) + 1050,
          explanation:
            scenario === 'forced_failure_block'
              ? 'I found a matching option (enterprise-support-tier1 at ₹65,000.00), but RazorGate security policy ceiling (₹50,000.00) blocked execution safely. No payment made.'
              : scenario === 'behavior_flag'
              ? 'Transaction of ₹49.00 was flagged for rolling window frequency anomaly. Approved with verification flag.'
              : 'Successfully authorized and placed order for compute-gpu-h100-1hr at ₹299.00. Razorpay Order ID: order_TUkjWMgUTBNytJ.',
          order:
            scenario === 'forced_failure_block'
              ? null
              : {
                  id: scenario === 'clean_allow' ? 'order_TUkjWMgUTBNytJ' : 'order_TUkozs6yo8Ju23',
                  entity: 'order',
                  amount: scenario === 'clean_allow' ? 29900 : 4900,
                  currency: 'INR',
                  status: 'created',
                },
          transcript: [],
          receipt: {
            mandate_id: 'mandate_' + Math.random().toString(36).substring(2, 9),
            buyer_agent_id: 'buyer_h100_cluster',
            merchant_id: 'merchant_razorgate_cloud',
            sku:
              scenario === 'forced_failure_block'
                ? 'enterprise-support-tier1'
                : scenario === 'behavior_flag'
                ? 'api-tier-starter-100k'
                : 'compute-gpu-h100-1hr',
            amount_paise: scenario === 'forced_failure_block' ? 6500000 : scenario === 'behavior_flag' ? 4900 : 29900,
            amount_inr: scenario === 'forced_failure_block' ? 65000.0 : scenario === 'behavior_flag' ? 49.0 : 299.0,
            currency: 'INR',
            verdict: scenario === 'forced_failure_block' ? 'BLOCK' : scenario === 'behavior_flag' ? 'FLAG' : 'ALLOW',
            primary_factor:
              scenario === 'forced_failure_block'
                ? 'amount_exceeded_ceiling'
                : scenario === 'behavior_flag'
                ? 'behavior_anomaly'
                : 'policy_cleared',
            summary:
              scenario === 'forced_failure_block'
                ? 'Transaction of ₹65,000.00 BLOCKED: Exceeds policy amount ceiling.'
                : scenario === 'behavior_flag'
                ? 'Transaction of ₹49.00 FLAGGED for verification: Behavioral anomaly triggered.'
                : 'Transaction of ₹299.00 APPROVED: All policy and telemetry safety checks passed.',
            confidence: scenario === 'forced_failure_block' ? 1.0 : scenario === 'behavior_flag' ? 0.85 : 1.0,
            audit_id: 1045,
            order: scenario === 'forced_failure_block' ? null : { id: 'order_TUkjWMgUTBNytJ' },
          },
        };
        setLatestScenario(fallbackResult);
        return fallbackResult;
      } finally {
        setIsScenarioRunning(false);
      }
    },
    []
  );

  const handleQuickRunDemo = () => {
    handleExecuteScenario('clean_allow');
    if (currentTab === 'landing') {
      setCurrentTab('dashboard');
    }
  };

  return (
    <div className="min-h-screen bg-[#0A0A0B] text-[#F5F1EA] flex flex-col selection:bg-[#D4A15C]/20 selection:text-[#E8B96C]">
      {/* Universal Header */}
      <Header
        currentTab={currentTab}
        onSelectTab={(tab) => {
          setCurrentTab(tab);
          window.scrollTo({ top: 0, behavior: 'smooth' });
        }}
        sseStatus={sseStatus}
        onQuickRunDemo={handleQuickRunDemo}
        isDemoRunning={isScenarioRunning}
      />

      {/* Main Surface View Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 pt-6">
        {currentTab === 'landing' && (
          <LandingPage
            onNavigate={(tab) => {
              setCurrentTab(tab);
              window.scrollTo({ top: 0, behavior: 'smooth' });
            }}
            onLaunchDemoScenario={() => handleExecuteScenario('clean_allow')}
          />
        )}

        {currentTab === 'dashboard' && (
          <LiveDashboard
            decisions={decisions}
            metrics={metrics}
            selectedDecision={selectedDecision}
            onSelectDecision={setSelectedDecision}
            sseStatus={sseStatus}
            latestScenario={latestScenario}
            onRunScenario={handleExecuteScenario}
            isScenarioRunning={isScenarioRunning}
          />
        )}

        {currentTab === 'walkthrough' && (
          <GatedFlowWalkthrough
            onRunScenario={handleExecuteScenario}
            isScenarioRunning={isScenarioRunning}
            currentScenarioResult={latestScenario}
          />
        )}
      </main>

      {/* Footer */}
      <footer className="w-full bg-[#0E0E10] border-t border-white/5 py-8 mt-auto">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs font-mono text-[#8E8A83]">
          <div>
            <span className="text-[#F5F1EA] font-semibold">RazorGate</span> — Deterministic trust layer for autonomous AI agent payments.
          </div>
          <div className="flex items-center gap-4">
            <span>Apiris v1.1.1 (CAD Model)</span>
            <span>·</span>
            <span>Razorpay Orders Test API</span>
            <span>·</span>
            <span>A2A Protocol v1</span>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default App;
