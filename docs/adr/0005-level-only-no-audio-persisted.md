# 0005. Level-only monitoring: audio is never persisted or transmitted

**Status:** Accepted · **Date:** 2026-05-31 · **Migrated:** 2026-09-05 from `docs/ROADMAP.md` §6 (GAP-DOC-1)

## Context
The problem this project exists for is a neighbour noise dispute: there is no objective
record of when it was actually loud. The obvious instrument — a recorder — creates
legal and ethical problems it does not need to create. This is a home, in a
two-party-consent jurisdiction, and the people whose voices a recorder would capture
have not consented to anything.

The evidence the dispute actually needs is *when* and *how loud*, not *what was said*.
Those are separable: an RMS level is derivable from a frame of audio without keeping
the frame.

## Decision
The monitor computes sound **levels only**. No audio is captured to storage, and none
is transmitted anywhere. The data model has no audio field —
`Event(start, end, duration, peak_level, avg_level, [coarse_tag])` and the calibration
history — so there is no API through which audio *could* be written, rather than a
policy that it must not be.

**Rejected: recording audio.** Legal and ethical exposure the project has no need to
take on, for evidence it does not need.

## Consequences
- **Easier:** the compliance posture is structural rather than procedural, and the
  report can say so plainly (`docs/audits/recording-law-notes.md`,
  `docs/audits/no-audio-guarantee.md`).
- **Harder / accepted:** the log can never establish what made a sound. The report
  says so and never claims source attribution; the opt-in coarse tag
  ([ADR-0024](./0024-opt-in-coarse-event-tagging.md)) is a hedged hint, not evidence.
- **Enforced:** `tests/test_no_audio.py` is merge-blocking, and any new persisted field
  has to be added to its list deliberately.
- **Revisit trigger:** none contemplated. This is the project's premise; a change here
  is a different project, not a new version of this one.
