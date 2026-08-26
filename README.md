# RazorGate

Payments trust/gating layer built on Apiris, for the Razorpay AI Buildathon (Track 01).

## Architecture & Scoring Conventions

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
1. `high_frequency`: Call bursts exceeding window threshold.
2. `amount_deviation`: Amount deviating $> N$ standard deviations from running mean.

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
