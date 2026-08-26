# PROJECT CONTEXT — RazorGate

*Reference document. Read this before generating code, writing the README, or recording the pitch — it's the "why," not the "how." The setup prompt and roadmap already cover the how.*

## What this project is

RazorGate is a trust/enforcement layer that sits between an AI buyer agent and Razorpay's payment APIs. Before the agent's decision to spend money actually executes, RazorGate scores the request and decides ALLOW, BLOCK, or FLAG — with an explanation and an audit trail. It's built for Track 01 of the Razorpay AI Buildathon ("AI Growth & Agentic Commerce"), whose stated bar is that every money action an agent takes must be "explainable, bounded, and gated."

## What Apiris is, stated accurately

Apiris is a package Tarun built and shipped independently, before this Buildathon existed. It's an offline-first API decision-intelligence engine: a drop-in interceptor that predicts latency, detects statistical anomalies (Isolation Forest, z-score/IQR), does multi-objective cost/latency trade-off analysis, and cross-references an offline CVE database — across 130+ vendors, in ~4ms per call, entirely locally, no telemetry leaving the host. It's genuinely in use: 2,815 verified PyPI downloads (pepy.tech, CI traffic included) and 3 startups running it in their API layer. It also has a real, working control-plane dashboard — pipeline visualization, a live decision feed, vendor trust ranking, a simulation injector for fault testing.

The one fact that matters most for everything downstream: **Apiris's own decision engine outputs PROCEED or WARNED. It has never blocked a request. It was deliberately built advisory-only**, so a false positive never takes down a production system it's watching. That's a real, sound design choice for its original purpose — and it's also exactly the gap RazorGate exists to fill.

## What RazorGate adds on top

Apiris tells you a call *looks* risky. RazorGate is the new work that decides what to *do* about that, specifically for money: it takes Apiris's PROCEED/WARNED signal, layers payments-native rules on top (amount ceilings, retry-count-in-a-window, call-frequency-vs-baseline — things Apiris has no native concept of, because API latency telemetry and fintech risk are genuinely different problems), and for the first time turns an advisory signal into an actual ALLOW/BLOCK/FLAG enforcement decision, wired to real Razorpay test-mode Orders API calls, with a buyer agent that has to reckon with a FLAG instead of just obeying a rule.

That's the honest shape of the project: **one proven, general-purpose intelligence engine, plus new, purpose-built enforcement logic for a domain where blocking — not just advising — is the actual requirement.**

## How this enhances Apiris itself, not just RazorGate

This isn't a one-way relationship where Apiris helps the Buildathon project and gets nothing back. Building RazorGate is the first time Apiris's scoring has ever been asked to power a real decision instead of a warning — that's a genuine capability gap in Apiris (no enforcement mode exists yet) that this project fills, and the enforcement/policy layer built here (`gate/adapter.py`, `policy.yaml`) is generalizable back into Apiris itself later as an opt-in "enforcement mode," not something thrown away after the Buildathon. Apiris also gets a second, concrete vertical use case (fintech, alongside general API reliability) and a Razorpay vendor entry in its own CVE/trust database it didn't have before. The relationship runs both directions.

## How this helps Tarun specifically

- **It's the strongest possible answer to "Build Quality — would you trust it."** A reviewer can install `apiris` from PyPI right now, today, independent of anything submitted to the Buildathon, and see real download numbers and real usage. That's evidence no fresh hackathon build can produce, no matter how polished.
- **It directly demonstrates "AI Judgment" — the right tool in the right place, and where you chose not to use one.** Choosing deterministic ML (Isolation Forest, rule-based policy) for the enforcement gate instead of routing every decision through an LLM is a real, defensible architecture choice, not a hedge — and it's exactly the kind of judgment call the rubric is built to surface.
- **It's not a sunk cost if this specific Buildathon doesn't convert to a callback.** The enforcement-mode extension to Apiris has value independent of the outcome — it's a legitimate next release for an existing open-source project, and a technical writeup on "adding deterministic enforcement to an advisory ML pipeline for agentic payments" is portfolio material regardless of what Razorpay decides.
- **It compounds instead of resetting.** Every other Track 01 applicant starts from zero engineering credibility and has to prove it in ~10 days. Tarun starts from an already-shipped, already-adopted artifact and only has to prove the *extension* — a smaller, more finishable claim, which is also just a more honest one.

## The one discipline this context is meant to protect

Everything above only holds if the distinction between "what Apiris already proved" and "what RazorGate newly proves" stays sharp and stated plainly, everywhere — README, pitch video, live Q&A. The moment that line blurs (claiming Apiris already blocks things, rounding the download number up, treating an unverified CVE example as solid), the whole credibility advantage this project is built on is the first thing that breaks. Keep the claims exactly as accurate as the engine itself.