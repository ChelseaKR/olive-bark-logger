# Ideation — Large-Scale Fixes & Expansions

**Drafted: 2026-07-01.** This folder is the third documentation layer for Olive's Bark
Logger, produced from a fresh full read of the code, tests, CI, and audits:

1. [`ROADMAP.md`](../ROADMAP.md) — the canonical build spec (M0–M6 shipped, P0–P2
   productionization ADRs). Source of truth for scope and the MoSCoW gates.
2. `RESEARCH-ROADMAP.md` + `USER-RESEARCH.md` — the 2026-06-30 synthetic-stakeholder
   research pass (remediations R1–R9, expansions E1–E7). **Note:** as of 2026-07-01
   these two documents and their implemented items (R1 cover page, R2 calibration
   banner, R3 duration rollup, R5 no-audio note) live on the unmerged
   `research-panel-and-roadmap` branch (commit `0f98ce0`), not on `main` — see
   [`01-deep-dive.md`](./01-deep-dive.md) §Debt.
3. **This folder** — deeper structural fixes and larger expansions that neither of the
   above contains. Everything here is **net-new**: where an idea builds on an existing
   R#/E# or ROADMAP section, it references that ID and goes beyond it rather than
   restating it.

## Contents

| File | What it holds |
|------|---------------|
| [`01-deep-dive.md`](./01-deep-dive.md) | Current-state assessment from reading the code: architecture map with file paths, genuine strengths, structural debt actually observed, strategic position in the 21-repo portfolio. |
| [`02-large-scale-fixes.md`](./02-large-scale-fixes.md) | FIX-01…FIX-13 — deep structural fixes (correctness, data model, privacy, a11y, operability), each with effort tier, risks, and a measurable excellence bar. |
| [`03-expansions.md`](./03-expansions.md) | EXP-01…EXP-16 — expansion ideas in three horizons: H1 deepen the core, H2 adjacent capabilities/audiences, H3 transformative bets. |
| [`04-impact-and-sequencing.md`](./04-impact-and-sequencing.md) | Impact×effort matrix over every FIX/EXP ID, dependency notes, a Now/Next/Later sequence beyond the existing roadmaps, and the items gated on humans, lawyers, SMEs, or real data. |

## How to read this honestly

These are **ideas for evaluation, not commitments.** Nothing here has been sized against
real demand — this repo's own research pass is explicit that its personas are synthetic
and "not evidence of demand," and the same discipline applies doubly to this layer.
Several items end in an explicit gate (real-data validation, legal review, native-speaker
review, ethics review); per the portfolio ethos those gates are **deferred and reported
honestly, never faked.** Every claim below is grounded in a file that was actually read;
where a claim is an inference rather than an observation, it says so.
