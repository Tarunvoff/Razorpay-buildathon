# STATUS — Where You Are Right Now

*Read this last, act on it first. Points into PHASE_PLAN.md for detail.*

## Current state

Phase 1 (scaffolding) is complete — you ran the setup prompt already. Before touching any new code this session, confirm the Phase 1 checklist in PHASE_PLAN.md actually passes. Don't assume it still does if any time has passed or anything changed since you ran it — a 30-second re-check now beats debugging a Phase-4 failure that's actually a broken Phase-1 foundation.

## What to do in this sitting, in order

1. Re-run the Phase 1 checklist (`pytest`, `uvicorn`, `/health`, frontend shell). Fix anything broken before proceeding.
2. Start Phase 2: add `apiris` as a real dependency, replace the always-ALLOW stub in `gate/adapter.py` with a real call into it. Don't touch Phase 3 or later until Phase 2's exit criterion is genuinely met.
3. Stop the session at the first natural checkpoint (a phase's exit criterion met, tests green) rather than mid-phase — makes the next resume point unambiguous.

## The one rule for the rest of this sprint

Work through PHASE_PLAN.md in order. No phase starts before the previous one's exit criterion is actually verified — not "should work," actually run and confirmed. If something breaks, fix it inside the phase where it broke before moving forward. This is what "nothing goes in between" means in practice: no skipping ahead to a more interesting phase while an earlier one is half-done.

## What's explicitly not part of this sprint

The cadlens-dashboard-into-apiris project. If a build session starts drifting toward "let's make this dashboard more complete/general-purpose," that's the wrong project bleeding into this one — stop, note it for later, and return to whatever RazorGate phase you were actually on.

## Files in this set

- `PROJECT_CONTEXT.md` — the why, the apiris/cadlens split, the honesty framework. Read before writing the README or the pitch.
- `PHASE_PLAN.md` — the how, phase by phase, with exit criteria for each.
- `STATUS.md` (this file) — where you are, what's next, right now.
