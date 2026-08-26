# PHASE PLAN — RazorGate Build (Razorpay Buildathon Sprint Only)

*Sequential. Each phase assumes the previous one is genuinely done, not "mostly done." Phase 1 is already complete — start reading at Phase 2. Nothing here includes the post-sprint cadlens-dashboard-into-apiris work; see PROJECT_CONTEXT.md's scope boundary.*

## Phase 1 — Scaffolding ✅ DONE

You already ran the setup prompt. Confirm before moving on, don't assume:
- [ ] `pytest -v` runs and fails cleanly (red) on `test_block_prevents_downstream_razorpay_call`, not an import/crash error
- [ ] `uvicorn backend.api:app --reload` boots, `/health` returns ok, `/decisions/stream` heartbeats
- [ ] Frontend shell fetches `/health` and renders it
- [ ] `.env` has real Razorpay test-mode keys and a real Anthropic key, both confirmed working standalone

If any of these aren't true, fix them before Phase 2 — everything downstream assumes a working skeleton.

## Phase 2 — Real per-call scoring via `apiris` (replaces the stub)

- Add `apiris` to `backend/requirements.txt` as a real dependency, `pip install apiris`.
- In `gate/adapter.py`, replace the always-ALLOW stub with a real call into `apiris`'s client/decision engine. Map its real action output (`pass_through`, `mask_sensitive_fields`, `serve_stale_cache`, `reject_response`, `downgrade_fidelity`, `delay_response`) — not PROCEED/WARNED — into an internal risk signal your policy layer will consume in Phase 4.
- Confirm your Phase-1 test still fails red for the right reason (policy logic isn't wired yet), and add one more test confirming a normal/low-risk call maps to a non-blocking apiris action correctly.
- **Exit criterion:** `gate/adapter.py` genuinely calls `apiris`, not a stub, and you can point to the exact import.

## Phase 3 — Behavioral signal, adapted from `cadlens`

- Create `gate/behavior.py`. Port the *pattern*, not the file verbatim, from `cadlens`'s `drift_analyzer.py`/`brownout_detector.py`: track a rolling window of recent calls per agent/session (count, frequency, amount trend) and flag when the current call's context deviates from that window.
- This is intentionally simpler than `cadlens`'s full version — you need "is this session's call pattern anomalous," not the full multi-service correlation engine. Resist porting more than that.
- **Exit criterion:** a burst of rapid calls in a short window produces a distinguishable behavioral flag from a normal single call, provable with one test.

## Phase 4 — Payments-native policy (the actual new work)

- `gate/policy.yaml`: define real thresholds — max order amount, max retries per order in a time window, max call frequency per agent.
- `gate/policy.py`: combine apiris's per-call signal (Phase 2) + the behavioral signal (Phase 3) + these policy rules into one function returning `ALLOW`/`BLOCK`/`FLAG` with a confidence and a reason.
- Wire `gate/adapter.py`'s public `check()` function to call this combined policy, replacing the Phase-2 apiris-only version.
- **Exit criterion:** the Phase-1 test now passes green — BLOCK genuinely prevents the downstream Razorpay call — and a second test proves a legitimate call gets ALLOW.

## Phase 5 — Audit/explanation, adapted from `cadlens`

- `audit/explainer.py`: port the shape of `cadlens`'s `build_explanation()` — turn a policy decision into a structured, human-readable record (summary, primary risk factor, supporting evidence, confidence), not just a raw verdict.
- Every `gate.check()` call writes one row to the SQLite audit table (already scaffolded in Phase 1) using this explanation, not just the bare verdict.
- **Exit criterion:** `GET /decisions` returns real rows with real natural-language explanations, not placeholder text.

## Phase 6 — Razorpay Orders API integration

- `payments/razorpay_client.py`: real test-mode `create_order`/`fetch_order` calls, already scaffolded in Phase 1 — confirm it's wired to real keys, not still using placeholder values.
- Wire the full path: agent → `gate.check()` → if ALLOW, call `razorpay_client.create_order()` → confirm via webhook or a fetch-after-create → log outcome to the audit table.
- **Exit criterion:** one real, end-to-end successful order creation, visible in both your own audit log and (if you check) Razorpay's own test-mode dashboard.

## Phase 7 — Buyer agent, staged reasoning

- `agent/buyer_agent.py`: raw Anthropic tool-use, 3 tools (`search_catalog`, `check_gate`, `create_order`), reading intent/budget → picking a product → calling the gate before touching Razorpay.
- On ALLOW: proceed. On BLOCK: explain and stop. On FLAG: the agent's own logic decides — retry with reduced scope, or request human confirmation (a simple y/n prompt is a fine stand-in, say so plainly in the README).
- **Exit criterion:** a full run — agent reasons, gate scores, Razorpay executes or blocks — with no manual intervention except the FLAG confirmation step.

## Phase 8 — Forced failures (both required, not optional)

- **Certain:** an order over the policy ceiling → BLOCK, explanation shown, audit row written, agent stops cleanly without crashing.
- **Stretch, only if Phase 2–7 finished with 2+ days to spare:** a burst script tripping the Phase-3 behavioral flag, or a simulated downstream Razorpay timeout with visible retry/backoff.
- **Exit criterion:** at least the certain case is reproducible on demand, not something that happened once during development.

## Phase 9 — Minimal demo surface (not a dashboard)

- One page: live decision feed (poll `/decisions`), each row showing verdict/explanation/timestamp. That's it — no vendor trust ranking, no executive summary, no multi-page nav. This is intentionally smaller than earlier drafts of this plan; the full dashboard is explicitly deferred (see PROJECT_CONTEXT.md).
- **Exit criterion:** the page shows real rows from Phase 5–8's actual runs, refreshing live.

## Phase 10 — README, fixes, recording, submission

- Write the README using the three-tier honesty framework from PROJECT_CONTEXT.md exactly.
- Fix or disclose the `apiris` broken-test and CVE-misattribution issues before linking anything publicly.
- Record the 5-minute pitch: problem (30s) → what RazorGate does (30s) → live run against real APIs (2 min) → forced failure handled gracefully (1 min) → 1-minute close naming exactly what came from `apiris`, what came from `cadlens`, what's new.
- Submit a few days before Sept 5, not on it — leaves room to fix anything that breaks on a clean-machine run.

## Non-negotiable ordering

Phases 2 → 4 must happen in order and each must be *verified* done (tests passing, not "looks right") before the next starts — this is the safety-critical core of the whole submission. Phases 5, 7, 9 can slip a day each without damaging the core story. Phase 8's certain case cannot be cut; the stretch case can. If time runs out anywhere past Phase 6, stop adding scope and polish what exists instead.
