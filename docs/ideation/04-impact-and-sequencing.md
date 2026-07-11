# Impact × Effort & Sequencing — 2026-07-01

Covers FIX-01…13 (`02-large-scale-fixes.md`) and EXP-01…16 (`03-expansions.md`).
Impact is judged against this repo's mission — a trustworthy, court-usable,
privacy-first noise record — not against feature breadth. These are suggestions for
evaluation, not commitments.

## Matrix

| Impact ↓ / Effort → | S | M | L / XL |
|---|---|---|---|
| **High** | FIX-07 (browser gates) · FIX-11 (gate hardening) · FIX-12 (branch merge + release) | FIX-01 (calibration truth) · FIX-02 (param provenance) · FIX-03 (gap ledger) · FIX-04 (heartbeat/counters) · FIX-05 (PWA correctness) · FIX-06 (conformance vectors) · FIX-13 (privacy budget) · EXP-07 (interchange+merge) | EXP-01 (ambient ledger) · EXP-12 (appliance image) · EXP-14 (multi-sensor) |
| **Medium** | FIX-10 (clock guard) · EXP-04 (drift advisory) · EXP-11 (AF_UNIX hooks) | FIX-08 (schedule model) · FIX-09 (pro-rated attribution) · EXP-02 (event anatomy) · EXP-03 (sensitivity view) · EXP-05 (ops console) · EXP-08 (privacy-gate kit) · EXP-09 (bilingual) · EXP-10 (packet builder) · EXP-13 (verifier) | EXP-06 (tagged PDF/A) · EXP-15 (ML tagging — may be rejected at the ethics gate) |
| **Lower / speculative** | — | — | EXP-16 (civic aggregation — impact potentially huge but fully gated) |

Notes on placement: FIX-01 and FIX-05 are "High" because each is a live correctness
defect (calibration clobbering in `monitor/service.py`; the PWA clock-domain mismatch
in `pwa/app.js`/`report.js`), not merely an improvement. EXP-12's impact is high only
if real-user adoption is actually a goal — that is a strategy question before it is an
engineering one.

## Dependency spine

```
FIX-12 (merge research branch)  ─ precondition for building on R1/R2/R3/R5 code
FIX-01 + FIX-02  ─ one schema migration (v3): calibration history + param provenance
        └─► EXP-07 (interchange exports clean lineage)
FIX-03 ◄─ FIX-04 (crash-safe counters close gaps)   FIX-03 ─► heatmap "no data" state
FIX-13 (privacy budget) ─ gates EXP-01 ─► EXP-02, EXP-03, EXP-04
FIX-08 (schedule model) ─ prerequisite for research-roadmap E5 and for FIX-09
FIX-06 (conformance vectors) ─ keeps FIX-05, FIX-08, FIX-09, EXP-09 in Python↔PWA sync
FIX-07/FIX-11 ─ prerequisites for trusting EXP-13's verifier page and EXP-11's carve-out
EXP-07 ─► EXP-13 (verifier) and feeds research-roadmap R4/E1/E2
```

## Suggested sequence (beyond the existing roadmaps)

The research roadmap's own "Now" (R1/R2/R5/R6) and "Next" (E1/R3/R4/R7) still stand;
this sequence slots the net-new layer around them.

**Now — restore a single trustworthy trunk, fix live defects (≈2–3 weeks):**
1. FIX-12 (merge `research-panel-and-roadmap` + `ci-efficiency`; then tag v0.2.0 with
   CHANGELOG) — nothing else should build on a forked reality.
2. FIX-01 + FIX-02 as one migration — the calibration-clobber defect corrupts evidence
   value every day it exists.
3. FIX-05 (PWA timestamps/backgrounding) — the browser variant's output is likely wrong
   today for live capture.
4. FIX-07 + FIX-11 — cheap, and they make the repo's central *claim* (enforced
   guarantees) true across both implementations before anything new lands.

**Next — make absence-of-data honest, stop drift (≈3–5 weeks):**
5. FIX-04 → FIX-03 (heartbeat/counters, then the gap ledger + "not monitored" rendering).
6. FIX-06 (conformance vectors) before any further dual-implementation features.
7. FIX-13 (privacy budget) — written and review-gated *before* EXP-01 tempts anyone.
8. FIX-08 → FIX-09 (schedule model, then pro-rated attribution) — also unblocks the
   research roadmap's E5.
9. FIX-10 (clock guard), EXP-04 alongside.

**Later — deepen, then widen (quarter+):**
10. EXP-01 → EXP-03 (ambient ledger, then sensitivity view) — the biggest single upgrade
    to evidentiary strength.
11. EXP-07 → EXP-13 (interchange format, then recipient verifier), absorbing the
    research roadmap's E1/R4/E2 work as it lands.
12. EXP-05, EXP-02, EXP-10, EXP-06, EXP-08, EXP-11 as capacity allows.
13. Horizon-3 (EXP-12, EXP-14, EXP-15, EXP-16) only after the data model is stable and
    the relevant gates below are passed — each is a strategy decision, not a backlog
    item.

## Items gated on humans, legal review, SMEs, or real data (defer honestly — never fake)

Consistent with the portfolio ethos and the research roadmap's own "Validate with real
users" section, these must not be "completed" synthetically:

| Item | Gate | What must actually happen |
|---|---|---|
| ROADMAP §4 labeled session (pre-existing, still open) | Real data | Detection + ZCR tag validated against genuinely labeled real-world audio sessions; `tests/test_eval.py` is 440 Hz-sine synthetic today. Metrics reported as-measured, including bad ones. |
| FIX-13 budget numbers | Privacy SME | The information-ceiling analysis reviewed by someone qualified in audio privacy/re-identification, not just self-certified. |
| EXP-03 sensitivity copy | Acoustics SME | Wording review so the approximation cannot be over-read (same review-gate posture the research roadmap applies to R3 copy). |
| EXP-04 drift tolerances | Real data | Default thresholds set from real long-running deployments, not guessed. |
| EXP-06 PDF/UA claim | Human (AT user) | A real screen-reader walkthrough of the PDF, committed like `docs/audits/accessibility-2026-06-05.md`. |
| EXP-09 Spanish honesty text | Human (native reviewer) | The limitations/cover translations sign-off-gated; no silent machine translation of legally-flavored text. |
| EXP-10 letter templates | Legal review | Legal-aid review of templates (UPL risk); until then ship structure with blanks only. |
| EXP-12 first-boot UX | Real users | Observed non-technical users; synthetic personas explicitly don't count (their own warning label says so). |
| EXP-15 entire idea | Ethics review | A committed decision artifact on whether confidence-scored labels cross the no-source-attribution "Won't (ever)" line — "no" is an acceptable and reportable outcome. |
| EXP-16 entire idea | Ethics + legal + governance | Consent/governance design reviewed externally before any code; re-identification analysis by a qualified reviewer. |
| Admissibility premise (all evidence features) | Human (attorney / animal control / PM) | The research roadmap already flags this: whether any nearby adjudicator accepts a levels-only record is unknown. Interview before investing in EXP-07/10/12/13 at scale. |

Where a gate cannot be passed yet, the honest output is a dated deferral note in the
relevant doc — exactly as the research branch did for its human-gated items.
