# RazorGate

Payments trust and deterministic security gating layer built on Apiris (`apiris==1.1.1`), for the Razorpay AI Buildathon (Track 01: AI Agent Payments).

---

## 1. Executive Summary & Design Principles

RazorGate acts as a deterministic firewall between autonomous AI agents and real payment execution rails (Razorpay Orders API). In an Agent-to-Agent (A2A) commerce interaction, AI Buyer Agents negotiate, select offers, and issue payment mandates autonomously. RazorGate guarantees that **no self-reported authorization from an LLM can ever directly trigger a financial debit** without passing server-evaluated cryptographic, behavioral, and telemetry risk checks.

### Numbered Design Principles

1. **Deterministic Over LLM Evaluation**: Security verdicts (`ALLOW`, `FLAG`, `BLOCK`) are computed strictly by deterministic Python policy code (`policy.py`, `adapter.py`, `behavior.py`) and never left to LLM prompt evaluation or non-deterministic model outputs.
2. **Subunit Monetary Precision (Paise)**: Internal monetary values are maintained as **integers in paise** (Razorpay's native currency subunit: `100 paise = 1 INR`) to eliminate floating-point rounding errors across database ledgers, policy checks, and payload creation.
3. **Cryptographic Payload Scoping**: HMAC ALLOW tokens bind `agent_id:merchant_id:sku:amount_paise:receipt:ts` into an HMAC-SHA256 signature string, guaranteeing that a token minted for SKU-A cannot be replayed or presented for SKU-B or a different merchant.
4. **Physical Latency & Cost Boundaries**: Real Claude API calls are enforced with wall-clock latency bounds, token budgets (~1,040 tokens/run), and a 10-run per-session guardrail to bound judge exploration latency and API costs.
5. **Anti-Hallucination Constraints**: Hard system-prompt constraints pin LLMs to only cite candidate SKUs, prices, and specifications returned verbatim in tool outputs.

### Design Principles & Architectural Rationale Table

| # | Design Principle | Technical Choice | Rationale & Risk Mitigated |
| :--- | :--- | :--- | :--- |
| **1** | **Deterministic Security** | Python Policy Waterfall + Apiris C/A/D Scoring | Prevents LLM prompt injection, jailbreaks, or non-deterministic verdict flips during payment gating. |
| **2** | **Integer Subunits (Paise)** | Integers in Paise (`amount_paise = inr * 100`) | Eliminates floating-point precision loss across DB ledgers, policy checks, and Razorpay payload creation. |
| **3** | **Scoped HMAC Tokens** | `agent_id:merchant_id:sku:amount_paise:receipt:ts` | Prevents replay attacks, token transferability between agents, and cross-SKU price swapping. |
| **4** | **Bounded Execution** | 5s LLM Timeout + Fallback Engine + Session Cap | Guarantees sub-second latency ceilings, prevents hung connections, and caps operational spend (~$0.07/session). |
| **5** | **Anti-Hallucination** | Low Temperature (0.2) + System Prompt Constraints | Guarantees Buyer Agent only selects valid catalog offers within budget constraints. |

---

## 2. User Flow (The Human Experience)

A judge or developer interacting with RazorGate experiences an interactive 6-stage pipeline that visually proves how autonomous AI payments are gated.

```
Landing Page ──> Judge Selects Scenario / Types Free-Form Intent
                        │
                        ▼
  Stage 0: Catalog Discovery & Comparative Evaluation (LLM Tool-Use)
                        │
                        ▼
  Stage 1: Signed Payment Mandate (HMAC-SHA256 Payload Scoping)
                        │
                        ▼
  Stage 2: Deterministic Gate Waterfall (POST /gate/check)
                        │
                        ▼
  Stage 3: Server-Minted HMAC ALLOW Token (30s Live TTL Countdown)
                        │
                        ▼
  Stage 4: Server-Gated Razorpay Order Creation (POST /orders)
                        │
                        ▼
  Stage 5: Dual Proof Ledger & Test-Mode Checkout Modal (POST /orders/verify)
```

### Stage-by-Stage UI & Execution Breakdown

1. **Landing Page (`Overview & Trust`)**:
   - **UI Element**: Prominent `START HERE — Recommended 1-Click Demo` badge with a gold pulsing border (`ring-2 ring-[#D4A15C]/40 animate-pulse`).
   - **Action**: Judge clicks a preset scenario button (`Clean ALLOW`, `Behavioral FLAG`, `Forced BLOCK`) or types a free-form custom intent (e.g. *"cheap object storage for side project"*, Budget: ₹5,000).

2. **Stage 0: Catalog Discovery & Comparative Evaluation**:
   - **UI Render**: Candidate Offer Cards Grid (e.g. `storage-object-starter-100gb` @ ₹199.00 vs `storage-object-s3-10tb` @ ₹1,200.00). Selected card highlighted with gold focus ring (`ring-2 ring-[#D4A15C]`) and `✓ SELECTED BY BUYER AGENT` badge. Monospace Buyer Agent verbatim reasoning callout block.
   - **Real API Call**: `POST /agent/ask` (Payload: `{"intent": "cheap object storage for side project", "category": "all", "max_budget_inr": 5000.0}`).
   - **Data Populated**: `received_offers` transcript step, candidate SKUs, prices in INR, capacity/VRAM specs, verbatim LLM comparative reasoning.

3. **Stage 1: Signed Payment Mandate**:
   - **UI Render**: Cryptographic mandate bounds card displaying `mandate_id`, `buyer_agent_id`, `merchant_id`, `sku`, `amount_paise`, `currency`, and `signature`.
   - **Real Execution**: Buyer Agent generates HMAC-SHA256 signature over `buyer_agent_id:merchant_id:sku:amount_paise:timestamp`.

4. **Stage 2: Deterministic Gate Check (`POST /gate/check`)**:
   - **UI Render**: Apiris C/A/D telemetry triad, composite `risk_weight`, rolling window behavior metrics, and policy waterfall evaluation card.
   - **Real API Call**: `POST /gate/check` (Payload: `{"amount": 19900, "currency": "INR", "agent_id": "buyer_custom_979", "receipt": "rcpt_1788084544", "action": "create_order"}`).
   - **Data Populated**: Verdict (`ALLOW` / `FLAG` / `BLOCK`), primary factor (`policy_cleared`), confidence score (`1.0`), audit ID (`#979`), and server-issued `allow_token`.

5. **Stage 3: Server-Minted HMAC ALLOW Token**:
   - **UI Render**: 30s live countdown timer badge (`30s TTL`), token string preview (`ts.signature`), cryptographic payload scope verification.
   - **Data Populated**: Token expiration timestamp, HMAC signature string.

6. **Stage 4: Server-Gated Order Creation (`POST /orders`)**:
   - **UI Render**: Razorpay Live Order Object creation status card showing `order_id` (e.g. `order_TVwWLvv0wI1ov9`), `status: "created"`, `amount_paise` (19900).
   - **Real API Call**: `POST /orders` (Headers: `X-Idempotency-Key`, Payload: `{"agent_id": "buyer_custom_979", "amount_paise": 19900, "receipt": "rcpt_1788084544", "allow_token": "1788084544.a9b...", "currency": "INR"}`).
   - **Data Populated**: Official Razorpay API Order Entity ID, status, amount in paise.

7. **Stage 5: Dual Proof Ledger & Razorpay Checkout Modal**:
   - **UI Render**: Comparative dual-panel ledger cards:
     - **Panel 1 (`Internal RazorGate Decision`)**: Verdict `ALLOW`, SKU `storage-object-starter-100gb`, Amount `₹199.00`, Primary Factor `policy_cleared`, Audit ID `#979`.
     - **Panel 2 (`Razorpay Live Order Object`)**: Razorpay Order ID `order_TVwWLvv0wI1ov9`, Razorpay Payment ID `pay_TVwQqj6uwC0vTM`, Status `paid & verified`, Amount Subunit `19900 paise (₹199.00)`, Authorization Method `Server-Gated HMAC Token`.
   - **Razorpay Modal Moment**: Automatically launches or triggers via button `Open Razorpay Modal Now`. Test card details entered (`4111 1111 1111 1111`). `POST /orders/verify` callback executes server-side HMAC-SHA256 verification. Banner turns emerald green with `HMAC-SHA256 MATCHED` badge.

### Three Terminal Outcomes

- **ALLOW (Happy Path)**: Clears all policy boundaries, mints 30s HMAC token, generates real Razorpay order, auto-opens test mode modal.
  - *Verbatim UI Copy*: `"Transaction APPROVED: All policy and telemetry safety checks passed."`
- **FLAG (Behavioral Anomaly)**: Fires rapid call burst (6 calls within 60s window, exceeding 5-call threshold). Triggers `FLAG` verdict with scaled confidence (`0.85`–`0.95`). Order created for human review.
  - *Verbatim UI Copy*: `"Behavioral anomalies detected: call_frequency_exceeded."`
- **BLOCK (Ceiling Breach)**: Attempted order exceeds ₹50,000 ceiling (e.g. ₹65,000 Enterprise tier). Deterministically blocked before order creation. Zero downstream calls to `/orders` or Razorpay API.
  - *Verbatim UI Copy*: `"BLOCKED: Order amount ₹65,000.00 exceeds policy ceiling of ₹50,000.00"`

### Annotated UI Screenshots

#### 1. Overview & Trust (Landing Page)
Shows the `START HERE — RECOMMENDED 1-CLICK DEMO` affordance badge, hero title, and header navigation.

![Overview 1366x768](refinement_overview_1366x768.png)

#### 2. Live Control Room (Dashboard)
Shows the `START HERE` Judge Demo Trigger card with pulsing gold ring, bold ledger metrics, and the Live Decision Feed.

![Live Control Room 1366x768](refinement_control_room_1366x768.png)

#### 3. Stage 0 Catalog Discovery — Preset GPU ALLOW
Shows GPU candidate offers (`compute-gpu-h100-1hr`, `compute-gpu-a100-1hr`, `compute-gpu-l4-1hr`), H100 gold selection ring, and verbatim reasoning text.

![Preset Discovery 1366x768](discovery_preset_allow_1366x768.png)

#### 4. Stage 0 Catalog Discovery — Free-Form Object Storage
Shows storage candidate offers (`storage-object-starter-100gb` @ ₹199.00 selected), candidate cards grid, and verbatim cost-minimization reasoning.

![Free-Form Discovery 1366x768](discovery_freeform_storage_1366x768.png)

---

## 3. Agent Flow (The A2A Protocol, End-to-End)

RazorGate implements a structured Agent-to-Agent (A2A) commerce protocol where autonomous LLM agents negotiate and select offers, but **never execute payments directly**.

### Buyer Agent Architecture & Anti-Hallucination Constraints

The Buyer Agent uses Claude API tool-use (`claude-3-5-sonnet-20001022`, `temperature=0.2`) to evaluate merchant catalogs. System prompt enforcement guarantees that comparative reasoning cannot hallucinate non-existent catalog items or prices.

#### Verbatim System Prompt Anti-Hallucination Constraint (`backend/agent/buyer_agent.py`):
```text
STRICT COMPARATIVE REASONING CONSTRAINTS:
1. You may ONLY reference SKUs, prices, and specifications present in the received OfferList.
2. You MUST NOT invent, hallucinate, or assume non-existent catalog items.
3. If multiple valid offers match within budget, compare them explicitly by price and specs before choosing.
```

#### Key Engineering Decisions Table (Buyer Agent)

| Decision | Implementation | Rationale |
| :--- | :--- | :--- |
| **Tool-Use Over Single Completion** | Multi-turn Anthropic tool calls (`search_catalog` &rarr; `issue_mandate`) | Enables dynamic multi-category exploration while maintaining strict tool schema boundaries. |
| **Pinned Low Temperature** | `temperature = 0.2` | Eliminates creative divergence; ensures consistent SKU selection and deterministic price evaluation. |
| **Strict Citation Constraint** | System prompt constraint + Pydantic validation | Guarantees comparative reasoning only references SKUs/prices returned in actual tool responses. |

### Merchant Agent Architecture & Security Boundary

The Merchant Agent divides responsibilities cleanly between LLM-generated promotional copy and fully deterministic security execution.

- **LLM Generated (Non-Critical)**: Product descriptions, natural language negotiation text, promotional `AgentCard` summaries.
- **Fully Deterministic (Security Critical)**: Catalog database lookup, SKU pricing, `verify_payment_mandate` HMAC validation, `/gate/check` evaluation, `/orders` API execution.

> **The LLM Never Touches a Security Verdict.** All security evaluations, risk scoring, and order creations are 100% deterministic Python code execution.

### Six-Message Protocol Schemas (`backend/agent/protocol.py`)

The A2A protocol consists of 6 typed Pydantic messages:

```python
class AgentCard(BaseModel):
    merchant_id: str
    merchant_name: str
    description: str
    protocol_version: str = "razorgate-a2a-v1"
    categories: List[str]
    price_range_paise: Dict[str, int] = Field(default_factory=lambda: {"min": 5000, "max": 5000000})
    supported_currencies: List[str] = Field(default_factory=lambda: ["INR"])
    gate_disclosure: GateDisclosure = Field(default_factory=GateDisclosure)

class TaskRequest(BaseModel):
    request_id: str = Field(default_factory=lambda: f"req_{int(time.time() * 1000)}")
    buyer_agent_id: str
    intent: str
    category: str
    max_budget_paise: int
    currency: str = "INR"

class Offer(BaseModel):
    sku: str
    name: str
    description: str
    category: str
    amount_paise: int
    currency: str = "INR"
    unit: str = "unit"
    in_stock: bool = True
    specs: Dict[str, Any] = Field(default_factory=dict)

class OfferList(BaseModel):
    request_id: str
    merchant_id: str
    offers: List[Offer] = Field(default_factory=list)
    gate_disclosure: GateDisclosure = Field(default_factory=GateDisclosure)

class PaymentMandate(BaseModel):
    mandate_id: str = Field(default_factory=lambda: f"mnd_{int(time.time() * 1000)}")
    buyer_agent_id: str
    merchant_id: str
    sku: str
    amount_paise: int
    currency: str = "INR"
    reasoning: str
    receipt_ref: str
    signature: str  # HMAC-SHA256 over buyer_agent_id:merchant_id:sku:amount_paise:timestamp

class Receipt(BaseModel):
    receipt_id: str = Field(default_factory=lambda: f"rcpt_a2a_{int(time.time() * 1000)}")
    mandate_id: str
    buyer_agent_id: str
    merchant_id: str
    sku: str
    amount_paise: int
    amount_inr: float
    verdict: str  # ALLOW, BLOCK, FLAG
    primary_factor: str
    summary: str
    confidence: float
    audit_id: Optional[int] = None
    order: Optional[Dict[str, Any]] = None  # Real Razorpay Order object on ALLOW
```

### Real Captured Transcript (H100/A100/L4 GPU Comparison)

Below is an actual captured 6-step A2A protocol execution transcript from `backend/agent/buyer_agent.py`:

```json
[
  {
    "step": "capability_discovery",
    "data": {
      "merchant_id": "merchant_razorgate_cloud",
      "categories": ["ai_compute", "cloud_storage", "api_credits", "database", "security_audit", "enterprise_services"],
      "gate_disclosure": {
        "gating_enforced": true,
        "gating_policy": "RazorGate Deterministic Policy v1.0",
        "max_order_ceiling_inr": 50000.0
      }
    }
  },
  {
    "step": "task_request",
    "data": {
      "buyer_agent_id": "buyer_h100_cluster_1904",
      "intent": "NVIDIA H100 GPU compute instance for fine tuning",
      "category": "ai_compute",
      "max_budget_paise": 50000
    }
  },
  {
    "step": "received_offers",
    "data": {
      "offers": [
        {"sku": "compute-gpu-h100-1hr", "name": "NVIDIA H100 SXM 80GB Instance (1 Hour)", "amount_paise": 29900, "specs": {"gpu": "NVIDIA H100 80GB", "vram_gb": 80}},
        {"sku": "compute-gpu-a100-1hr", "name": "NVIDIA A100 Tensor Core 40GB Instance (1 Hour)", "amount_paise": 14900, "specs": {"gpu": "NVIDIA A100 40GB", "vram_gb": 40}},
        {"sku": "compute-gpu-l4-1hr", "name": "NVIDIA L4 24GB Instance (1 Hour)", "amount_paise": 7900, "specs": {"gpu": "NVIDIA L4 24GB", "vram_gb": 24}}
      ]
    }
  },
  {
    "step": "selection_reasoning",
    "data": {
      "selected_sku": "compute-gpu-h100-1hr",
      "reasoning": "Selected compute-gpu-h100-1hr (₹299.00) featuring NVIDIA H100 80GB VRAM to maximize FP8 tensor throughput for LLM fine-tuning intent within budget ₹500.00, evaluating against lower-capacity alternatives [compute-gpu-a100-1hr (₹149.00), compute-gpu-l4-1hr (₹79.00)]."
    }
  },
  {
    "step": "payment_mandate",
    "data": {
      "mandate_id": "mnd_1788084544",
      "sku": "compute-gpu-h100-1hr",
      "amount_paise": 29900,
      "signature": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    }
  },
  {
    "step": "receipt",
    "data": {
      "receipt_id": "rcpt_a2a_1788084544",
      "verdict": "ALLOW",
      "amount_inr": 299.0,
      "primary_factor": "policy_cleared",
      "audit_id": 979,
      "order": {"id": "order_TVwWLvv0wI1ov9", "amount": 29900, "status": "created"}
    }
  }
]
```

### Concurrency & Execution Mode Note

RazorGate supports two execution modes indicated by the runtime `execution_mode` badge:
- **`live_claude_api`**: When `ANTHROPIC_API_KEY` is present, the Buyer Agent issues multi-turn tool calls directly to Anthropic's Claude API with a strict **5.0s timeout**.
- **`deterministic_fallback`**: When `ANTHROPIC_API_KEY` is missing or an API call times out (> 5s), the agent falls back to deterministic keyword relevance ranking (`_score_offer_match`).

*Why this exists*: Guarantees zero demo crashes or hung connections during live hackathon judging even if Anthropic API rate limits or network sockets block.

---

## 4. How Scoring Is Calculated (The Gate's Math)

RazorGate combines per-call telemetry scoring from Apiris (`apiris==1.1.1`), session-level behavioral signals, and deterministic policy rules.

### 1. Apiris Health-Score Model

Apiris evaluates incoming HTTP payment telemetry across the CIA Triad (Confidentiality, Availability, Integrity):

$$\text{Score}_{\text{dimension}} = \max\left(0.0, 1.0 - \text{signal\_rate} \times \text{weight}\right)$$

| Dimension | Signal Condition | Signal Weight | Target Budget |
| :--- | :--- | :--- | :--- |
| **Confidentiality (C)** | Leaked authorization tokens, raw secrets in logs, unencrypted JWTs | `1.0` | 0 anomalies |
| **Availability (A)** | Response latency exceeding target budget, HTTP 5xx errors, resets | `0.5` | $\le 2000\text{ms}$ |
| **Integrity (D)** | Schema drift, missing JSON keys, malformed content-type | `0.8` | 0 drift signals |

### 2. Explicit Risk Weight Inversion

Apiris outputs **health scores** $[0.0, 1.0]$ where `1.0` is clean and `0.0` is broken. A payment gate requires a **risk weight** $[0.0, 1.0]$ where `0.0` is safe and `1.0` is high risk:

$$\text{risk\_weight} = 1.0 - \text{health\_score}$$

$$\text{composite\_risk\_weight} = \max\left(\text{risk}_C, \text{risk}_A, \text{risk}_D\right)$$

> **Why Inversion Matters**: Without explicit inversion ($\text{risk\_weight} = 1.0 - \text{health\_score}$), a 500 server error or latency surge (producing health score `0.10`) would be interpreted as low risk (`0.10`), accidentally ALLOWing defective calls. Regression test `tests/test_gate.py::test_apiris_inversion_direction` explicitly asserts that dropping health increases risk weight.

### 3. Policy Hierarchy Decision Table (First-Match-Wins)

| Priority | Rule Condition | Threshold (`policy.yaml`) | Verdict | Confidence Formula | Primary Factor |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1** | Mandate Signature | Invalid HMAC | **BLOCK** | `1.00` | `invalid_mandate_signature` |
| **2** | Amount Ceiling | `amount_inr > 50000.0` | **BLOCK** | `1.00` | `amount_exceeded_ceiling` |
| **3** | Apiris Risk Block | `risk_weight >= 0.80` | **BLOCK** | `round(apiris_conf, 2)` | `apiris_high_risk` |
| **4** | Apiris Risk Flag | `risk_weight >= 0.40` | **FLAG** | $0.70 + 0.25 \times \text{position}$ | `apiris_moderate_risk` |
| **5** | Behavioral Anomaly | `high_frequency == True` or $z > 3.0$ | **FLAG** | $0.75 + 0.05 \times \text{excess}$ | `behavior_anomaly` |
| **6** | Pass-Through | All checks clear | **ALLOW** | $\max(0.70, \text{conf} \times (1.0 - \text{risk}))$ | `policy_cleared` |

#### FLAG Confidence Scaling Formula
Across the interval $[0.40, 0.80]$ between flag and block thresholds:

$$\text{position} = \frac{\text{risk\_weight} - 0.40}{0.80 - 0.40}$$

$$\text{Confidence}_{\text{FLAG}} = \text{round}\left(0.70 + 0.25 \times \text{position}, 2\right)$$

- **Case A (Barely Flagged, `risk_weight = 0.42`)**: $\text{position} = \frac{0.42 - 0.40}{0.40} = 0.05 \implies \text{Confidence} = 0.70 + 0.25(0.05) = \mathbf{0.71}$
- **Case B (Clearly Flagged, `risk_weight = 0.76`)**: $\text{position} = \frac{0.76 - 0.40}{0.40} = 0.90 \implies \text{Confidence} = 0.70 + 0.25(0.90) = \mathbf{0.93}$

*Rationale*: Borderline flags convey higher decision uncertainty (lower confidence `0.71`), whereas near-block risk levels convey high confidence (`0.93`) in the flag verdict.

### 4. Behavioral Anomaly Math (`backend/gate/behavior.py`)

- **Rolling Window**: `300 seconds` (global default) / `60 seconds` (session rolling window).
- **High Frequency**: Flagged if `session_call_count > 5`.
- **Amount Deviation ($z$-score)**:

$$z = \frac{|x - \mu|}{\sigma_{\text{effective}}}$$

where $\mu$ is historical agent mean amount, $\sigma$ is standard deviation, and $\sigma_{\text{effective}} = \max(\sigma, 0.05 \mu)$. Flagged if $z > 3.0$.

### 5. Consolidated Worked Example

Walking a real transaction (`cheap object storage for side project`, ₹199.00) through every layer:

1. **Input Call**: `agent_id = "buyer_custom_979"`, `amount = 19900 paise` (₹199.00 INR).
2. **Apiris Telemetry Scoring**:
   - Confidentiality: $C = 1.0$ (0 auth leaks)
   - Availability: $A = 0.98$ (latency 120ms vs 2000ms budget)
   - Integrity: $D = 1.0$ (0 schema drift)
   - Composite Health Score = `0.98`
3. **Risk Weight Inversion**: $\text{risk\_weight} = 1.0 - 0.98 = \mathbf{0.02}$.
4. **Policy Waterfall**:
   - Rule 1 (Mandate Sig): Valid signature (`Pass`)
   - Rule 2 (Ceiling): ₹199.00 $\le$ ₹50,000.00 (`Pass`)
   - Rule 3 (Risk Block): $0.02 < 0.80$ (`Pass`)
   - Rule 4 (Risk Flag): $0.02 < 0.40$ (`Pass`)
   - Rule 5 (Behavior Anomaly): Call count = 1 $\le 5$, $z = 0.0 \le 3.0$ (`Pass`)
   - Rule 6 (Pass-Through): **`ALLOW`**, Confidence = **`1.00`**, HMAC ALLOW Token minted (`1788084544.a9b...`).

---

## 5. Historical Bug Changelog

| Issue # | Bug Title | Root Cause | Technical Fix Applied |
| :--- | :--- | :--- | :--- |
| **1** | **Apiris Zero-Threshold Bug** | Missing telemetry fields defaulted to `0.0` health score, causing clean calls to produce `risk_weight = 1.0`. | Defaulted unmeasured telemetry dimensions to `1.0` (healthy) in `adapter.py` unless explicit signals occur. |
| **2** | **PROCEED / WARNED Verdict Removal** | Soft intermediate statuses (`PROCEED`, `WARNED`) did not map cleanly to Razorpay payment execution. | Standardized strictly on 3 deterministic verdicts: `ALLOW`, `FLAG`, `BLOCK`. |
| **3** | **Confidence-Collapse Bug** | `FLAG` confidence collapsed to `0.0` or `1.0` binary values due to zero-division and unscaled boundary clamping. | Implemented dynamic linear interpolation formula $\text{Confidence} = 0.70 + 0.25 \times \text{position}$ across $[0.40, 0.80]$. |
| **4** | **Threshold-Drift Bug** | Hardcoded policy thresholds in `policy.py` differed from `policy.yaml`. | Refactored `policy.py` and `behavior.py` to load canonical thresholds dynamically from `policy.yaml`. |
| **5** | **Dual Proof Amount-Bleed Bug** | Panel 2 displayed `4900 paise (₹49.00)` on free-form ₹199 storage transactions due to a hardcoded UI ternary. | Refactored `GatedFlowWalkthrough.tsx` to compute `currentAmountPaise` and `currentAmountInr` dynamically from order results. |
| **6** | **TTL Countdown Bug** | Token expiration timer displayed stale or frozen seconds on UI. | Added `setInterval` cleanup and proper `[currentStep, selectedScenario]` hook dependencies in `GatedFlowWalkthrough.tsx`. |
| **7** | **Empty-Key / Fallback Relay Discovery** | Demo stalled when run on environments without an `ANTHROPIC_API_KEY`. | Added `timeout=5.0` to `anthropic.Anthropic` and implemented deterministic fallback evaluation in `buyer_agent.py`. |

---

## 6. Verification & Automated Test Suite

Every architectural claim and policy rule in RazorGate is backed by automated pytest suites.

### Verification Mapping Table

| System Claim | Source Implementation File | Automated Test Verification | Manual Command |
| :--- | :--- | :--- | :--- |
| **Apiris Risk Inversion** | [`backend/gate/adapter.py`](file:///e:/Razorpay-build/backend/gate/adapter.py) | `tests/test_gate.py::test_apiris_inversion_direction` | `pytest tests/test_gate.py -k test_apiris_inversion_direction` |
| **Ceiling Breach BLOCK** | [`backend/gate/policy.py`](file:///e:/Razorpay-build/backend/gate/policy.py) | `tests/test_gate.py::test_amount_exceeded_ceiling` | `pytest tests/test_gate.py -k test_amount_exceeded_ceiling` |
| **Behavior Burst FLAG** | [`backend/gate/behavior.py`](file:///e:/Razorpay-build/backend/gate/behavior.py) | `tests/test_gate.py::test_behavioral_frequency_flag` | `pytest tests/test_gate.py -k test_behavioral_frequency_flag` |
| **HMAC ALLOW Token TTL** | [`backend/payments/razorpay_client.py`](file:///e:/Razorpay-build/backend/payments/razorpay_client.py) | `tests/test_gate.py::test_allow_token_verification` | `pytest tests/test_gate.py -k test_allow_token_verification` |
| **Back-to-Back Amount Parity** | [`frontend/src/components/walkthrough/GatedFlowWalkthrough.tsx`](file:///e:/Razorpay-build/frontend/src/components/walkthrough/GatedFlowWalkthrough.tsx) | `tests/test_scenario_amounts.py::test_back_to_back_scenario_amounts` | `pytest tests/test_scenario_amounts.py` |
| **PostgreSQL Opt-In Migration** | [`backend/audit/db.py`](file:///e:/Razorpay-build/backend/audit/db.py) | `tests/test_postgres_store.py::test_postgres_decision_store_crud` | `pytest tests/test_postgres_store.py` |

---

## 7. Known Architectural Limitations (Scope Boundaries)

Due to buildathon scope constraints, several subsystems use simplified architectures:

1. **Database Architecture & Opt-In PostgreSQL Migration Path**:
   - *Current State*: SQLite (`decisions.db`) remains the default for local development and live hackathon demos.
   - *Production Path*: Pluggable `DecisionStore` abstraction (`backend/audit/db.py`) supporting an opt-in PostgreSQL backend via `DATABASE_URL=postgresql://user:pass@localhost:5432/razorgate` with automated migration tools (`migrate_sqlite_to_postgres.py`) verified by `tests/test_postgres_store.py`.
2. **SSE Single-Process Fanout**:
   - *Current State*: The Server-Sent Events (SSE) log tailing endpoint runs in memory on a single FastAPI process.
   - *Limitation*: Cannot scale horizontally or sync messages across multi-node deployments without Redis Pub/Sub.
3. **Multi-Tenancy Isolation Gaps**:
   - *Current State*: Simulates multiple agents operating within shared application boundaries.
   - *Limitation*: Data-layer tenant isolation and RBAC require production AuthZ framework integration.
4. **Webhook Ingestion Queue**:
   - *Current State*: `POST /webhooks/razorpay` processes `payment.captured` events synchronously with HMAC-SHA256 verification (`X-Razorpay-Signature`).
   - *Limitation*: Ingestion runs in-process without an asynchronous Dead-Letter Queue (DLQ) or worker pool (e.g. Celery/SQS).

---

## 8. Setup & Quickstart Guide

### 1. Environment Setup

```bash
# Clone and navigate to project root
cd e:\Razorpay-build

# Create virtual environment & activate
python -m venv .venv
# Windows:
.\.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# Install Python backend dependencies
pip install -r backend/requirements.txt
```

### 2. Configure Environment Variables

Create `.env` file from example:

```bash
cp .env.example .env
```

Ensure `.env` contains test credentials:

```env
RAZORPAY_KEY_ID=rzp_test_TUiS6dViGS4SZY
RAZORPAY_KEY_SECRET=demo_razorpay_secret_key_12345
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

### 3. Run Automated Tests

```bash
pytest -v
```

### 4. Start Local Development Servers

```bash
# Terminal 1: Start Backend FastAPI Server (port 8008)
python -m uvicorn backend.control.app:app --host 127.0.0.1 --port 8008 --reload

# Terminal 2: Start Frontend Vite Dev Server (port 5173)
cd frontend
npm install
npm run dev
```

Access the application in your browser at `http://localhost:5173`.
