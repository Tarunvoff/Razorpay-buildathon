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
- Calls without a valid token or with an expired token return `403 Forbidden`.

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
