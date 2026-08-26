# PROJECT CONTEXT — RazorGate (Razorpay AI Buildathon, Track 01)

*Read this before any build session. It's the "why" and the "what's real," not the "how" — that's in PHASE_PLAN.md.*

## Scope boundary — read this first

This document and PHASE_PLAN.md cover **only** the Razorpay Buildathon submission, due September 5. A second, separate initiative — porting `cadlens`'s full dashboard into `apiris` itself as a real released feature — is explicitly **out of scope here** and happens after the Buildathon sprint ends, as its own plan. Nothing in this sprint should grow to try to accomplish that second project. If a task starts to feel like "let's make this a proper standalone dashboard," that's scope creep from the wrong project — cut it back to what the Buildathon demo actually needs.

## What RazorGate is

A trust/enforcement layer between an AI buyer agent and Razorpay's test-mode payment APIs. Before the agent's spend decision executes, RazorGate scores it and returns ALLOW, BLOCK, or FLAG, with an explanation and an audit trail — answering Track 01's bar: every money action must be "explainable, bounded, and gated."

## The two-source split — what comes from where, and why

RazorGate is built from two of Tarun's own existing codebases, each used for what it's actually good at, plus new work neither of them has:

**`apiris`** (installed as a real `pip install apiris` dependency, not copied code) — the released, adopted artifact. 2,815 verified PyPI downloads (pepy.tech, CI traffic included), 3 startups running it in production. Used for **per-call risk scoring**: CIA-triad evaluation, Isolation Forest anomaly detection, offline CVE advisory, on each individual Razorpay API attempt. This is what makes the "already shipped, already trusted" claim literally checkable by a reviewer.

**`cadlens`** (Tarun's own more advanced, unreleased development repo — same lineage as `apiris`, ahead of what's been published) — adapted, not pip-installed, since it isn't packaged yet. Two pieces get ported into RazorGate's own code:
- `explainer.py`'s `build_explanation()` pattern → adapted into RazorGate's own audit/explanation module, for natural-language decision records.
- `drift_analyzer.py`/`brownout_detector.py`'s pattern → adapted into a `behavior.py` module that scores the *shape of a session* (is this agent's call pattern anomalous over time), which is a genuinely different signal from `apiris`'s single-call scoring.

**New, in neither repo** — the actual work being judged: payments-native policy (amount ceilings, retry/velocity rules), the ALLOW/BLOCK/FLAG decision itself, the Razorpay Orders API integration, and the buyer agent.

## Decision-output terminology — use this exactly, don't invent new terms

`apiris`'s real decision engine (confirmed by direct code inspection, not README claims) outputs one of: `pass_through`, `mask_sensitive_fields`, `serve_stale_cache`, `reject_response`, `downgrade_fidelity`, `delay_response`. There is no "PROCEED/WARNED" pair in the actual code — drop that terminology entirely if it shows up anywhere. RazorGate's own new enforcement layer maps these real actions plus its own payments-native rules into its own new vocabulary: **ALLOW / BLOCK / FLAG**. State the mapping explicitly in the README so it's clear which vocabulary belongs to which layer.

## The honesty framework — state exactly this, nothing rounder

1. **Released and adopted:** `apiris` on PyPI — 2,815 downloads, 3 startups, real and independently verifiable today.
2. **Built by me, not yet released:** `cadlens` — same engine, extended with explainability and behavioral-drift analysis, plus a real FastAPI control plane and dashboard (not part of this submission, referenced only as prior work).
3. **New for this submission:** the payments-native enforcement layer — RazorGate itself.

Never let tier 2 or 3 get described as if it were tier 1. That's the one discipline everything else in this project depends on.

## Known accuracy items to keep straight

- `apiris`'s repo currently has a broken test collection (`ModuleNotFoundError: apiris.intelligence.drift_analyzer`) because that module exists in `cadlens` but was never backported/released. Fix or explicitly note this before anything gets linked publicly.
- `apiris`'s CVE-advisory examples have at least one confirmed vendor-misattribution bug (a Ghost CMS CVE mistagged under "Anthropic") — don't feature the CVE-advisory pillar as a headline claim unless it's fixed.
- Frontend for this sprint is minimal — a working demo surface proving the pipeline is real, not a multi-page dashboard. The full dashboard is the deferred, separate project.
