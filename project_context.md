# RazorGate + apiris — Complete System Context
### High-Level Design, Low-Level Design, and In-Depth Implementation Analysis
### Status as of Phase 8 completion (Day 2 of 3)

---

# PART A — EXECUTIVE SUMMARY

Two artifacts, deliberately separated, now integrated:

1. **`apiris`** — a real, independently published PyPI package (v1.1.1) that scores individual API calls for reliability/security risk across a Confidentiality/Availability/Integrity (CAD) model. Pre-existing (2,815+ downloads, 3 startups before this project touched it), hardened during this sprint, now a genuine dependency of RazorGate, not copied code.
2. **RazorGate** — the Buildathon submission. A payments trust layer for Razorpay that gates AI-agent-initiated transactions through a deterministic policy engine, backed by `apiris` for per-call risk scoring, a custom behavioral/session-drift signal, and a novel Agent-to-Agent (A2A) commerce protocol that makes a merchant "transactable by an AI buyer end to end" — directly answering Track 01's core requirement.

Both are complete through what the phase plan calls Phase 8. Phase 9 (frontend) and Phase 10 (packaging/pitch) remain.

---

# PART B — HIGH-LEVEL DESIGN (HLD)

## B.1 System boundary

```
+---------------------------------------------------------------------------+
|                         RazorGate A2A Commerce System                      |
|                                                                             |
|  +---------------+   protocol msgs   +--------------------+                |
|  |  Buyer Agent   |<----------------->|  Merchant Agent     |               |
|  |  (LLM-driven)  |                   |  (fronts backend)   |               |
|  +---------------+                    +---------+----------+               |
|                                                    |                        |
|                                        +-----------v-----------+           |
|                                        |   Control Plane        |           |
|                                        |   (FastAPI)             |          |
|                                        |  /gate/check /orders    |          |
|                                        |  /decisions /*/stream   |          |
|                                        +-----------+------------+          |
|                        +---------------------------+------------------+    |
|              +---------v--------+      +-----------v---------+  +-----v---+|
|              |   Gate Engine     |      |   Payments Layer      |  |  Audit  ||
|              |                   |      |                       |  |  Ledger ||
|              | +---------------+ |      |  razorpay_client.py   |  | SQLite  ||
|              | | adapter.py    |-+------>  ALLOW-token gated    |  |decisions||
|              | | (real apiris) | |      |  Razorpay Orders API   |  |  table  ||
|              | +---------------+ |      |  (test mode, real)     |  +---------+|
|              | +---------------+ |      +-----------------------+            |
|              | | behavior.py   | |                                           |
|              | | (session      | |                                           |
|              | |  drift)       | |                                           |
|              | +---------------+ |                                           |
|              | +---------------+ |                                           |
|              | | policy.py     | |                                           |
|              | | (ALLOW/FLAG/  | |                                           |
|              | |  BLOCK        | |                                           |
|              | |  hierarchy)   | |                                           |
|              | +---------------+ |                                           |
|              +-------------------+                                          |
|                                                                              |
|  External dependency: apiris==1.1.1 (published, independent PyPI package)   |
|  External integration: Razorpay Orders API (test mode, real network calls)  |
+-----------------------------------------------------------------------------+
```

## B.2 Design principles actually followed (not aspirational — each has a corresponding test)

1. **The gate is a pure function of state.** `adapter.check(...)` takes a call description and returns a verdict; all internal state (session windows) is encapsulated behind a swappable storage interface.
2. **Hard hierarchy, first-match-wins.** Deterministic policy ceilings always evaluate before probabilistic risk signals; behavioral anomalies can only ever escalate toward FLAG, never independently trigger BLOCK. This asymmetry is deliberate — a rolling-window heuristic has real false-positive risk and must not unilaterally kill a legitimate transaction.
3. **Explanations are template-rendered, not LLM-narrated.** Every audit record is a deterministic function of the same structured fields a test can assert against — no hallucination surface in the safety-critical explanation path.
4. **No self-reported authorization.** The agent (or Merchant Agent on its behalf) cannot claim it received an ALLOW; the payments layer independently re-validates a short-lived, cryptographically signed, request-bound token.
5. **Single source of truth for every threshold.** Any number that governs a decision (ceiling, frequency threshold, deviation threshold) lives in exactly one canonical place (`policy.yaml`), with every consumer reading it live rather than duplicating the literal — enforced by dedicated regression tests after this was caught as a real bug pattern mid-project (see Part D.4).
6. **Real integrations only.** `apiris` is a genuine pip dependency, not copied source. Razorpay orders are created and fetched back from live test-mode infrastructure at every phase gate, not mocked at the final assertion.

---

# PART C — LOW-LEVEL DESIGN (LLD)

## C.1 `apiris` (external dependency, v1.1.1)

### C.1.1 Core scoring model
`DecisionEngine._compute_score` computes **health scores**, not risk scores, per CAD dimension:
```
Score = max(0.0, 1.0 - signal_rate x weight)
```
1.0 = clean/optimal; dropping toward 0.0 = detected defects (latency > budget, HTTP 5xx, leaked auth/secrets, verbose errors, schema drift). This is the single most important semantic fact about apiris that RazorGate's own code must respect — a naive reader could mistake a high score for "high risk," which is backwards. `adapter.py` performs the explicit inversion (`risk_weight = 1.0 - health_score`) and this inversion is unit-tested in both directions.

### C.1.2 Fixes shipped in 1.1.1 (root-caused, not just patched)

| Bug | Root cause | Fix | Verified by |
|---|---|---|---|
| Always-maximal-risk scoring | `ApirisConfig` defaults were `integrity_threshold=0.0`, `availability_threshold=0.0`, `anomaly_threshold=0.0` — any nonzero score already exceeded every threshold | Empirically-derived non-zero defaults (0.40 / 0.40 / 0.70) from a labeled synthetic clean-traffic corpus; legacy behavior preserved behind `strict_zero_tolerance: true` opt-in | `test_regression_scoring.py`, corpus-driven `calibrate_thresholds.py` |
| CVE vendor misattribution (Ghost CMS -> Anthropic, Gogs -> Pusher, LangChain -> OpenAI) | No automated cross-check against vendor aliases; manual dataset entry | `validate_cve_data.py` audits all 47 vendors/65 CVEs against alias lists; verified retroactively against the actual pre-fix historical commit, catching all 3 real mistags plus schema errors | `test_cve_validation.py` (5 dedicated tests, including named regressions per mistag) |
| Broken test collection | `drift_analyzer` imported from unreleased `cadlens` codebase, never backported | Scoped, apiris-appropriate reimplementation of `DriftAnalyzer`, `RiskAggregator`, `VendorProfileBuilder` | Full suite now collects cleanly |
| Single global anomaly baseline for all APIs | One baseline applied regardless of per-API normal behavior | Per-`api_name` baselines with `_global`/`default` fallback, derived via pooled weighted mean/variance (law-of-total-variance style, not naive std-averaging) across existing per-API models (n=1,224 pooled) | `apiris models list` distinguishes trained vs. placeholder baselines explicitly |
| Hard action-selection cutoffs (flapping risk) | Borderline scores could flip actions on noise | `hysteresis_band = 0.05` added to `DecisionEngine` | `test_hysteresis_smoothing_prevents_flapping` |
| Confidence collapsed to a near-constant value regardless of severity | `min_dist` over a single dimension, clamped to a narrow margin — a 1-factor and a 3-factor+HTTP-403 breach both landed at 0.92 | Multi-dimensional confidence: clean-call clearance-based for `pass_through`; breach-depth + multi-pillar-reinforcement + signal-intensity blend for escalated actions | `test_confidence_relative_ordering_moderate_vs_critical`, live-fixture regression tests (weather.gov vs. nasa.gov style) |
| Risk classification badge decoupled from the new confidence model | Static `min(scores) < 0.20` shortcut, so a single minor header leak and a severe multi-pillar 403 both read CRITICAL | Multi-dimensional `classify_risk()`: factor count, failing-dimension count, HTTP status, action/tradeoff — 5 documented tiers (LOW/MODERATE/ELEVATED/HIGH/CRITICAL) | `test_risk_classification_all_five_tiers`, deterministic fixture demos for all 5 tiers |

### C.1.3 CLI surface (10 commands total, up from 4)
`version`, `status`, `check`, `cve` (pre-existing) + `benchmark`, `calibrate`, `models list`, `models train`, `drift`, `doctor`, `report` (added this sprint). All new commands share one visual grammar (rich-based panels, the CIA factor-tree pattern, a consistent risk-tier color scale) rather than each inventing its own formatting. `doctor` is CI-usable (non-zero exit on failure).

### C.1.4 What's honestly still a placeholder
`_global`/`default` anomaly baselines are explicitly documented as conservative placeholders for unseen APIs, not calibrated per-API models — this is stated in `TRAINING_ANOMALY_MODELS.md` and `MIGRATION_v1.1.0.md` deliberately, not left implicit.

---

## C.2 RazorGate backend

### C.2.1 `gate/adapter.py`
- Public function: `check(payment_call: dict) -> dict`.
- Calls real `apiris.ApirisClient`/`ObservationEvaluator`/`DecisionEngine` with a realistic Razorpay-shaped request/response telemetry construction (structured JSON body, `x-razorpay-session-id` header, rate-limit headers on clean responses).
- Returns raw apiris `action`, per-dimension health scores, and the explicitly inverted `risk_weight = 1.0 - health_score` — named unambiguously to prevent the sign-confusion bug class from recurring downstream.
- **Removed entirely:** an invented `PROCEED`/`WARNED` vocabulary layer that briefly existed and was caught and eliminated — apiris's real action vocabulary and RazorGate's own ALLOW/FLAG/BLOCK vocabulary are the only two vocabularies in the system; nothing sits between them.

### C.2.2 `gate/behavior.py`
- `SessionWindow` / pluggable `WindowStore` protocol (get/append/evict), in-memory implementation today, designed to swap to Redis without touching scoring logic.
- Rolling window (default 300s) per `agent_id`. Two flag types, deliberately limited to exactly these two per the original scope discipline:
  - `high_frequency`: call count in window exceeds a threshold.
  - `amount_deviation`: current amount more than a configured number of standard deviations from the window's running mean (guarded against divide-by-zero on low-N windows).
- **Both flag types are independently proven to fire and to discriminate** (burst-vs-isolated test for frequency; stable-baseline-then-outlier test for deviation) — this took three rounds to fully close after amount_deviation was initially left untested, now resolved.
- Threshold values (`max_calls_per_agent_per_window`, `amount_deviation_std_threshold`) are read live from `policy.yaml` via `_get_default_policy_thresholds()` rather than duplicated as separate constants — fixed after the same drift-risk pattern caused a real bug in apiris's own config (Part D.4).

### C.2.3 `gate/policy.py` + `policy.yaml`
Decision hierarchy, strictly first-match-wins:
1. `amount_inr > max_order_amount_inr` -> **BLOCK** (`amount_exceeded_ceiling`), deterministic, confidence 1.00, independent of any telemetry.
2. `risk_weight >= apiris_risk_block` (0.80) -> **BLOCK** (`apiris_high_risk`), confidence inherited from apiris's own boundary-distance confidence.
3. `risk_weight >= apiris_risk_flag` (0.40) OR behavior flag present -> **FLAG**. Behavior-only flags can *never* independently reach BLOCK — this asymmetry is a deliberate design choice, explicitly tested (`test_behavior_flag_with_clean_apiris_produces_flag_never_block`).
4. Otherwise -> **ALLOW**.

FLAG confidence is boundary-distance-scaled across the `[apiris_risk_flag, apiris_risk_block)` interval (`0.70 + 0.25 x position`), not a flat floor — this replaced an earlier `max(apiris_conf, 0.85)` formula that was caught as backwards relative to the whole boundary-distance-confidence philosophy the project otherwise follows.

### C.2.4 `audit/explainer.py` + `audit/db.py`
- `build_explanation()` is a pure template-rendering function over `PolicyDecision`'s existing structured fields — no LLM call in the safety-critical explanation path, by deliberate design (deterministic, testable, no hallucination surface).
- SQLite `decisions` table: id, timestamp, agent_id, amount_paise, amount_inr, verdict, confidence, primary_factor, summary, evidence_json, `razorpay_order_id` (added in Phase 6 for forward audit-to-payment traceability).
- Endpoints, all tested at the FastAPI layer via `TestClient`, not just at the DB-function level: `POST /gate/check`, `GET /decisions?limit=&agent_id=`, `GET /decisions/{id}`, `GET /decisions/stream` (SSE, `asyncio.Queue`-based broadcast, 15s heartbeat) — the SSE route had to be declared before the `/decisions/{id}` path parameter route to avoid FastAPI swallowing stream requests as malformed IDs, a real routing bug caught and fixed.

### C.2.5 `payments/razorpay_client.py`
- Wraps the official `razorpay` Python SDK (`client.order.create`, `client.order.fetch`) against real test-mode credentials — not a raw HTTP client, not a mock at the integration boundary.
- **ALLOW-token gate**: HMAC-SHA256 over `agent_id + sku/amount + timestamp` (later extended to also bind `sku` explicitly once same-amount/different-SKU substitution was identified as an unclosed gap), 30-second TTL, minted only at the exact moment `/gate/check` returns ALLOW.
- `/orders` independently re-validates the token server-side; five negative-path tests confirm rejection on: missing/forged token, expired token, agent mismatch, amount tampering, receipt mismatch — plus the SKU-substitution case added after review.
- **Proven against live infrastructure, not mocked**, multiple times across Phases 6-7: real order IDs (`order_TUiaWDa6Uzr8u5`, `order_TUkjWMgUTBNytJ`, `order_TUkozs6yo8Ju23`, others) each independently fetched back via `client.order.fetch()` and visually confirmed in the Razorpay test-mode dashboard.

---

## C.3 The Agent-to-Agent (A2A) Protocol

### C.3.1 Why this exists, precisely
Track 01's core requirement is a merchant "transactable by an AI buyer end to end." A single agent calling internal tools models this weakly. Two agents exchanging structured, schema-defined messages — one representing the buyer's autonomous decision-making, one fronting the merchant's real backend — models it accurately, and it directly engages the problem statement's own framing (it explicitly names the ACP/AP2/x402 protocol race as "why now").

**Explicit scope discipline maintained throughout:** this is documented as "an original, lightweight protocol inspired by the AP2/ACP/x402 pattern space," never claimed as literal compliance with any named spec (Google AP2, NPCI UAP, Visa VIC). This distinction is stated verbatim in `docs/A2A_PROTOCOL.md`.

### C.3.2 Message flow (six steps, each a typed Pydantic model in `agent/protocol.py`)

1. **`AgentCard`** (capability discovery) — Merchant Agent advertises categories, price range, supported currencies, and a `gate_disclosure` object stating gating is enforced, naming the policy version, listing supported verdicts, and exposing `max_order_ceiling_inr` — read live from `policy.yaml`'s canonical value (verified by a dedicated regression test after this was flagged as a duplication risk).
2. **`TaskRequest`** — Buyer Agent sends structured intent (`intent`, `category`, `max_budget_paise`), not free text.
3. **`OfferList`** — Merchant Agent calls the real `search_catalog`, returns 2-4 ranked offers, each carrying its own `gate_disclosure` string.
4. **Selection + `PaymentMandate`** — Buyer Agent states one-line comparison reasoning (constrained to only reference SKUs/prices actually returned — verified anti-hallucination guardrail) and issues a signed mandate: `agent_id, merchant_id, sku, amount_paise, timestamp, reasoning, signature`. HMAC-SHA256 binds `buyer_agent_id : merchant_id : sku : amount_paise : timestamp` — SKU is bound into the signature explicitly (not just amount), closing a same-price/different-SKU substitution gap identified during review.
5. **Gated execution** — Merchant Agent submits the mandate to the real `/gate/check` -> `/orders` pipeline, unchanged from Phase 6.
6. **`Receipt`** — verdict, primary_factor, human-readable summary, confidence, audit_id, and — on ALLOW — the real Razorpay order object.

### C.3.3 What's been specifically stress-tested, beyond the happy path
- **Genuine comparison, not positional bias**: two separate scenarios constructed so the objectively correct choice is neither the first nor the median-priced offer (once for cheapest-is-correct, once for most-expensive-is-correct) — both proven with live transcripts showing the reasoning text correctly cites the deciding factor (price for one, VRAM spec for the other) and a real Razorpay order resulting from each.
- **Tamper/replay defense**: amount tampering, and specifically same-amount/different-SKU substitution — both rejected before `/orders` is ever reached.
- **Forced failure (Phase 8)**: a natural, plausible enterprise-support intent whose only matching option (Rs 65,000) exceeds the Rs 50,000 ceiling. Reproduced identically across 3 fresh-process runs — same verdict, same primary_factor, same audit behavior, zero Razorpay orders created across all three attempts (independently confirmed against the audit DB, not just the script's own claim). The Buyer Agent's final natural-language output correctly explains the failure without crashing or retrying.

---

# PART D — IN-DEPTH ANALYSIS: WHAT ACTUALLY WENT WRONG AND WAS CAUGHT

This section exists because it's the strongest evidence of engineering rigor available for the pitch — not the features themselves, but the fact that real bugs were found and root-caused rather than papered over. Worth pulling directly into the pitch's technical-depth section.

### D.1 The zero-threshold calibration bug (apiris)
A structural bug, not a typo: default thresholds of 0.0 mathematically guarantee every nonzero score reads as maximal risk. This was caught by manually running a genuinely clean fixture through the real pipeline and noticing the output (1.0/1.0/1.0, integrityRate: 0.0) didn't match what "clean" should produce — not by reading the source line first.

### D.2 The invented PROCEED/WARNED vocabulary (RazorGate)
A three-vocabulary problem briefly existed: apiris's real actions, RazorGate's ALLOW/FLAG/BLOCK, and an ad hoc PROCEED/WARNED layer bolted between them. Caught via a project-standing rule (grep for forbidden terms before considering any adapter phase done) — this is a documented example of a process control catching a design smell before it became load-bearing.

### D.3 The confidence-collapse bug (apiris, then independently in RazorGate)
The same class of bug appeared twice, independently, in two different codebases this sprint: a confidence metric that reads the same regardless of severity because it's derived from a single dimension or floored to a constant. Caught the first time via live CLI validation (two real endpoints producing identical 92% confidence despite obviously different severity) and root-caused precisely (narrow-margin single-dimension clamping). Caught the second time in RazorGate's own FLAG-path confidence (`max(apiris_conf, 0.85)` — a floor that guarantees high confidence on barely-triggered cases, exactly backwards) by applying the same scrutiny learned from the first instance.

### D.4 The single-source-of-truth threshold drift bug
Occurred concretely once (apiris's live `config.yaml` showing `integrity_threshold: 0.25` while the corpus-derived and documented value was 0.40 — a stale local-test leftover, not a hidden regression, but indistinguishable from one without investigation) and was proactively checked for and prevented a second time in RazorGate (`behavior.py`'s frequency threshold vs. `policy.yaml`'s, and `AgentCard`'s ceiling vs. `policy.yaml`'s canonical value) — both explicitly refactored to read from one canonical source with a regression test asserting the two never diverge.

### D.5 The vague-verification failure mode
Twice, a phase was reported as complete with softer language than the standard held everywhere else ("verified live network call handshake" instead of a real order ID; a test count that didn't reconcile between two reports in the same round). Both were caught by insisting on the literal artifact the exit criterion asked for — an order ID, a raw pytest count — rather than accepting a description of an action having occurred. This is arguably the single most repeated and most valuable check applied across the whole sprint.

---

# PART E — TEST COVERAGE SUMMARY

| System | Test count | What's proven |
|---|---|---|
| `apiris` | 42 (pytest) | Calibration correctness, CVE integrity (including retroactive detection against the real historical bug), confidence ordering across severity, risk classification across all 5 tiers, hysteresis, backward compatibility, all 10 CLI commands |
| RazorGate core (gate/audit/payments) | 18 | Full ALLOW/FLAG/BLOCK hierarchy including the behavior-never-solo-blocks asymmetry, audit round-trip at the API layer, SSE live-subscriber delivery, 5 payment-token negative paths, live Razorpay order creation + fetch-back |
| RazorGate A2A protocol | 4 dedicated (22 total incl. core) | Full protocol round-trip with a real order, tampered-mandate rejection (amount and SKU-substitution), genuine non-positional comparison reasoning (both extremes), over-ceiling BLOCK with correct agent-facing explanation |
| Phase 8 forced-failure | 3 live reproducibility runs (manual, demo-grade, outside pytest) | Identical BLOCK behavior across fresh processes, zero side effects independently confirmed against both the audit DB and the absence of any Razorpay order |

**Total: 64 automated tests + 3 manual reproducibility runs, all currently green, all independently re-verified at least once during this project (nothing accepted on first report without a follow-up check).**

---

# PART F — WHAT REMAINS

| Phase | Scope | Status |
|---|---|---|
| 9 | Frontend: live decision feed (SSE-driven), decision detail drawer (policy hierarchy trace), agent run timeline (rendering real A2A transcripts), live architecture view with session counts, metrics strip | Not started — deliberately deferred until real data existed to build against |
| 10 | README consolidation, three-tier honesty framework front-and-center, known-issues disclosure (apiris's historical bugs, stated proactively), pitch script assembly (Phase 8's beat already drafted), clean-machine full run-through | Not started |

Everything in Parts A-E above is the material Phase 10's README and pitch should draw from directly — the bug-catching narrative in Part D in particular is stronger technical-depth evidence than any single feature description.