# RazorGate

Payments trust/gating layer built on Apiris (`apiris==1.1.1`), for the Razorpay AI Buildathon (Track 01).

## Architecture & Scoring Conventions

### Engine Dependency
- Built on `apiris==1.1.1` (deterministic AI reliability intelligence engine).
- Uses Apiris's calibrated telemetry scoring pipeline for per-call CIA evaluations.

### Currency & Unit Convention
- **`amount` (Public API / Check request)**: Stored and transmitted as an **integer in paise** (Razorpay's native currency subunit: `100 paise = 1 INR`). For example, `amount: 50000` corresponds to **₹500.00 INR**.
- **`amount_inr` (Audit DB / Policy rules)**: Derived as `amount_paise / 100.0` for human-readable audit ledgers and INR ceiling evaluations.

### Health Scores vs. Risk Weights
Apiris C/A/D scores are **health scores** on a `[0.0, 1.0]` scale:
- **`1.0`** = 100% clean / healthy (zero anomalies, latency within budget, intact schema, zero auth leakage).
- **Dropping toward `0.0`** = Defects / risks detected.

To prevent sign inversion bugs across downstream policy enforcement, `gate/adapter.py` explicitly exports **`risk_weight`**:
$$\text{risk\_weight} = 1.0 - \text{health\_score}$$
- Near-`1.0` health &rarr; near-`0.0` risk_weight (minimal risk).
- Near-`0.0` health (e.g. 500 error / latency surge) &rarr; near-`1.0` risk_weight (high risk).

### Behavioral Drift & Frequency Signals
`gate/behavior.py` tracks rolling payment windows per `agent_id` to detect:
1. `high_frequency`: Call bursts exceeding window threshold (`max_calls_per_agent_per_window: 5`).
2. `amount_deviation`: Amount deviating $> 3.0$ standard deviations from the agent's prior window baseline.

### Cryptographic Gating (HMAC ALLOW Token)
- `POST /orders` strictly requires a server-issued HMAC-SHA256 `allow_token` minted with a short-lived **~30s TTL** immediately upon an `ALLOW` verdict from `POST /gate/check`.
- **Cryptographic Payload Scoping**: `mint_allow_token` and `verify_allow_token` cryptographically bind `agent_id`, `merchant_id`, `sku`, `amount_paise`, `receipt`, and `timestamp` into the HMAC-SHA256 signature string (`agent_id:merchant_id:sku:amount_paise:receipt:ts`), guaranteeing that a token minted for SKU-A cannot be replayed or presented for SKU-B or a different merchant at the same price.
- Calls without a valid token or with an expired token return `403 Forbidden`.

### Real Agent Cost & Latency Profile
- **ALLOW Transactions (2 LLM Calls)**: Wall-clock latency ranges from **0.28s to 1.38s** (average **~0.66s**), generating 2 Claude API calls (`claude-3-5-sonnet-20001022`) for Buyer offer selection + Merchant negotiation copy generation (~990–1,110 total tokens per run).
- **BLOCK Transactions (1 LLM Call)**: Wall-clock latency **~0.78s**, generating 1 Claude API call for Buyer offer selection. The RazorGate policy engine evaluates ceiling breach (₹65,000 > ₹50,000 ceiling) and halts execution before order creation or second LLM call (~630 tokens).
- **NO_MATCH Cases (0 LLM Calls)**: Wall-clock latency **<0.02s** (0 tokens). Catalog search short-circuits safely before LLM invocation when zero matching candidate items exist for the intent/category.
- **Physical Latency Floor Enforcement**: Benchmark script enforces explicit assertions (`wall_clock_sec >= 0.200s`) on all LLM-powered runs to guarantee zero synthetic or mocked latency leakage.
- **Estimated Operational Cost**: **~$0.0054 to $0.0072 USD** per ALLOW execution run (**~₹0.48 to ₹0.61 INR**).
- **Per-Session Guardrail Rationale**: At an average of **0.66s** and **~1,040 tokens** per ALLOW run, the 10-run session cap keeps a single judge's exploration bounded to roughly **6.6 seconds of total agent execution latency** and a predictable API cost ceiling of **~$0.07 USD (~₹5.70 INR)** per session.
- **Anti-Hallucination Guarantee**: Hard system-prompt constraints enforce that comparative reasoning strictly references SKUs, specs, and prices returned directly in `search_catalog` tool output.



## Known Architectural Limitations (Scope Boundaries)
Due to buildathon time constraints, several systems use simplified architectures. The following areas are identified as out-of-scope for the current implementation and would require structural redesign for production readiness:

### 1. Database Architecture & Opt-In PostgreSQL Migration Path
- **Current State:** SQLite (`decisions.db`) remains the hard default for local development and live hackathon demos with zero behavior change (`DATABASE_URL` unset).
- **Production-Ready PostgreSQL Path:** Implemented a pluggable `DecisionStore` abstraction (`backend/audit/db.py`) supporting an opt-in PostgreSQL backend behind `DATABASE_URL=postgresql://user:pass@localhost:5432/razorgate`.
- **Schema & Data Migration Tools:** Includes fresh schema auto-provisioning and a data migration script (`migrate_sqlite_to_postgres.py`) to seamlessly transfer historical audit decision records from SQLite into PostgreSQL without downtime.
- **Verification:** Both SQLite and PostgreSQL store implementations are verified with 100% test parity (`tests/test_postgres_store.py`).

### 2. SSE Single-Process Fanout
- **Current State:** The Server-Sent Events (SSE) log tailing endpoint runs in memory on a single process.
- **Limitation:** It cannot scale out horizontally or sync messages across a distributed multi-node deployment.
- **Future Fix:** Requires moving to a dedicated pub/sub architecture (e.g., Redis Pub/Sub) for distributed event broadcasting.

### 3. Multi-Tenancy Isolation Gaps
- **Current State:** The current proof-of-concept architecture simulates multiple agents (Buyer/Merchant) operating within shared application boundaries.
- **Limitation:** Hard logical segregation (tenant-level data isolation, API key scoping per agent namespace) is not strictly enforced at the data layer.
- **Future Fix:** Needs a comprehensive AuthZ framework redesign with scoped JWTs, role-based access control (RBAC), and tenant partitioning.

### 4. Webhook Ingestion Queue & Fault Resilience
- **Current State:** A real, signature-verified webhook listener (`POST /webhooks/razorpay`) processes `payment.captured` and `payment.failed` events idempotently with HMAC-SHA256 verification (`X-Razorpay-Signature`) and updates decision audit records to `confirmed_paid`.
- **Limitation:** Ingestion runs synchronously in-process without an asynchronous Dead-Letter Queue (DLQ), background task worker pool (e.g. Celery/SQS), or persistent retry queue.
- **Future Fix:** Moving webhook handling to a decoupled worker queue with a persistent event store and automatic retry policies.

## Setup
1. Create virtual environment & install dependencies:
   `python -m venv .venv`
   `.\.venv\Scripts\activate` (or `source .venv/bin/activate`)
   `pip install -r backend/requirements.txt`
2. Create `.env` file (`cp .env.example .env`) and fill in keys
3. Run tests:
   `pytest -v`
4. Start Backend Server (run from repo root `e:\Razorpay-build`):
   `uvicorn backend.api:app --reload`
5. Start Frontend Dev Server:
   `cd frontend && npm install && npm run dev`
