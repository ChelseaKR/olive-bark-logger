# Research-Backed Roadmap — Olive's Bark Logger

> **This complements [`ROADMAP.md`](./ROADMAP.md); it does not replace it.**
> `ROADMAP.md` is the canonical implementation plan (M0–M6 shipped, plus the P0–P2
> productionization ADRs) and the source of truth for scope and the MoSCoW gates.
> This document is a *research-driven backlog*: gaps and opportunities surfaced by
> the synthetic persona panel in [`USER-RESEARCH.md`](./USER-RESEARCH.md), each
> mapped to a real feature and to cited public evidence. Every item is tagged
> **[corroborates …]** when it sharpens something `ROADMAP.md` already names, or
> **[NET-NEW]** when the panel surfaced it independently. Nothing here overturns the
> core strategy — it deepens the project's two pillars: **the no-audio gate** and
> **calibration / measurement honesty.**
>
> **Last assembled: 2026-06-30.** Legal/acoustics claims are summarized from cited
> sources and are **jurisdiction-dependent**; not legal advice.

## Framing — what changed and what didn't

`ROADMAP.md` already commits to the right things: level-only + no-audio, a mandatory
methodology/limitations section, configurable quiet hours, calibration honesty, an
accessible report, and an honest violations export. The panel does not contradict any
of it. What it adds is a consistent message from *every* side of a real dispute:
**the honesty is correct but under-surfaced**, and **the output needs to be legible
and trustworthy to non-engineers — the neighbor, the property manager, the board, the
attorney, the skeptic — who never read the audit docs.** The backlog below is almost
entirely "make the existing honesty visible and tamper-evident," not "add capability."

## Research basis / evidence (cited, access date 2026-06-30)

Each backlog row references one of these by short tag. High-stakes legal/acoustics
claims are corroborated by ≥2 sources; legal claims are jurisdiction-dependent.

- **[ord]** Barking-nuisance ordinances commonly require a **dated/timed log with
  durations**, sometimes a **second household**, with thresholds like ≈30 min
  continuous / ≈60 min intermittent per 24 h —
  [Contra Costa Noisy Animal Ordinance](https://www.contracosta.ca.gov/6839/Noisy-Animal-Ordinance),
  [OC Animal Care](https://ocpetinfo.com/page/barking-dog-animal-nuisance-complaint-process),
  [LA Animal Services](https://www.laanimalservices.com/nuisance-barking),
  [Justia — barking dogs & neighbor rights](https://www.justia.com/animal-dog-law/barking-dogs-and-neighbor-rights/).
- **[doc]** Tenant/PM noise-documentation guidance: clinical, timestamped log + written
  paper trail; a decibel reading "adds objective weight" —
  [Flex](https://getflex.com/blog/apartment-noise-complaint-letter-email-template),
  [Local Noise Laws](https://www.localnoiselaws.com/blog/documenting-noise-complaints/),
  [LawInfo](https://www.lawinfo.com/resources/landlord-tenant/handling-noise-complaints-from-tenants.html).
- **[hoa]** HOA/condo adjudication via CC&R nuisance/quiet-hours rules, notice-and-hearing
  (CA Davis-Stirling IDR) —
  [MBK Chapman](https://mbkchapman.com/california-hoa-noise-complaints-fact-sheet/),
  [Manning & Meyers](https://www.hoalegal.com/blog/managing-noise-complaints-in-condominiums-legal-perspectives/).
- **[qe]** Covenant of quiet enjoyment: substantial (not trivial) interference can breach;
  landlord must act —
  [Cornell LII](https://www.law.cornell.edu/wex/covenant_of_quiet_enjoyment),
  [Texas State Law Library](https://guides.sll.texas.gov/landlord-tenant-law/noise).
- **[rec]** All-party-consent / wiretap exposure for in-home audio; illegal recordings
  often inadmissible and penal —
  [RCFP](https://www.rcfp.org/introduction-to-reporters-recording-guide/),
  [Recording Law (2026)](https://www.recordinglaw.com/party-two-party-consent-states/),
  [Justia 50-state survey](https://www.justia.com/50-state-surveys/recording-phone-calls-and-conversations/).
- **[spl]** dBFS (≤0, digital full-scale) ≠ dB SPL (ref 20 µPa); dB(A) is the regulatory
  unit; uncalibrated mics are relative and can be off 5–15 dB —
  [Wikipedia dBFS](https://en.wikipedia.org/wiki/DBFS),
  [AudioMasterclass](https://www.audiomasterclass.com/blog/what-is-the-difference-between-0-db-and-0-dbfs).
- **[iec]** IEC 61672 Class 1 (precision) vs Class 2 (general) tolerances/ranges;
  regulations often require Class 1 —
  [SoftdB](https://www.softdb.com/blog/class-1-vs-class-2-sound-level-meter/),
  [IEC 61672-1:2013](https://webstore.iec.ch/en/publication/5708),
  [NoiseMeters](https://www.noisemeters.com/help/faq/type-class/).
- **[app]** Phone/app accuracy: of 192 apps only a few met ±2 dB(A) vs Type-1; NIOSH app
  ±2 dB(A) and Type 2 *only with a calibrated external mic*, not for compliance —
  [NIOSH/CDC app](https://www.cdc.gov/niosh/noise/about/app.html),
  [Kardous & Shaw 2014 (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC4659422/).

---

## Remediation backlog (close gaps in what already exists)

Priority: **P0** now · **P1** next · **P2** soon. Effort: S/M/L per the panel scale.

| ID | Remediation | Personas | Pri | Effort | Evidence & notes |
|---|---|---|---|---|---|
| R1 | **Plain-language "What this can & cannot prove" cover page** auto-prepended to the report *and every export* (violations CSV/HTML). Lifts the existing limitations to the top in lay terms: relative-not-SPL, no source attribution, placement-dependent, not legal compliance. | P1,P4,P5,P6,P9 | **P0** | S | The text already exists in `methodology-and-limitations.md` and the report; this is **prominence + reuse**, not new claims. [doc][ord] **[corroborates ROADMAP §5/§12 honest framing — elevate to cover page]** ✅ Implemented 2026-06-30 (working tree, uncommitted) |
| R2 | **Calibration honesty surfacing** — an unmissable "Uncalibrated → readings are *relative*, not dB(A)" banner whenever `calibration_offset == 0.0`, and a guided `olive-calibrate` flow that records the reference instrument used. | P6,P1,P10 | **P0** | S–M | dBFS≠SPL; even a NIOSH-grade phone is ±2 dB and Type 2 only with an external calibrated mic. [spl][app][iec] **[corroborates calibration ADR — make prominence + provenance explicit]** ✅ Implemented 2026-06-30 (working tree, uncommitted) |
| R3 | **Ordinance/CC&R duration rollup** — a "minutes above threshold *during the configured window*, per day" summary that maps to how rules are written (e.g. ≈30 min continuous / ≈60 min intermittent), **without declaring a violation**. | P1,P4,P5,P9 | **P1** | M | Ordinances key on accumulated duration in a window; the tool has quiet-hours + events but not the rollup. [ord][hoa] **[NET-NEW vs ROADMAP quiet-hours summary]** ✅ Implemented 2026-06-30 (working tree, uncommitted) |
| R4 | **Corroboration affordance** — make the report state plainly "this is one device's record" and support attaching/aligning a *second household's* dated log onto the same timeline. | P3,P4,P9 | **P1** | M | Many ordinances weight a second complaining household; adjudicators distrust a one-sided record. [ord][doc] **[NET-NEW]** |
| R5 | **Reader-facing recording-law / no-audio note** embedded in the report — a short "why there is deliberately no audio" so a neighbor/PM/board reads the absence as a privacy choice, not missing data. | P8,P9,P3 | **P1** | S | The rationale exists in `recording-law-notes.md`; readers never see it. [rec] **[corroborates ROADMAP §10 — surface to the reader]** ✅ Implemented 2026-06-30 (working tree, uncommitted) |
| R6 | **Measurement-conditions & placement prominence** — promote the existing session lineage (placement, calibration, tz) and **frame-coverage** numbers into the report header, with a short "move the device → re-validate" caution. | P6,P4,P10 | **P1** | S | Counters miscalibration/placement bias (residual-risk row 7); lineage + coverage already captured. [spl][iec] **[corroborates productionization ADRs — surface, don't bury]** |
| R7 | **Accessibility parity for the *exported/forwarded* artifact** — confirm the PDF/print path and the violations export keep table-equivalents, headings, and `aria-label`s; add a screen-reader walkthrough of the violations export to the audit. | P7 | **P1** | S–M | Current a11y audit scopes the **HTML** report; the forwarded artifact is what adjudicators share. **[NET-NEW / extends accessibility audit]** |
| R8 | **Noise-type tuning presets** for the PWA + CLI (short-thump / sustained / barking) with a clearer live-meter read while tuning, so non-dog users (and non-experts) aren't guessing thresholds. | P2,P1,P10 | **P2** | S | Detector params (threshold/min-dur/debounce) exist; only barking defaults are documented. [doc] **[NET-NEW]** |
| R9 | **"Hint" honesty controls** — keep the coarse bark/ambient tag clearly hedged, and offer to **omit it from adjudication exports** so it can't be read as source attribution. | P6,P8,P9 | **P2** | S | Coarse tag is already a hedged opt-in "hint"; risk is over-reading in front of a board. [ord] **[corroborates coarse-tagging ADR — add suppression in exports]** |

## Expansion backlog (new capability)

| ID | Expansion | Personas | Pri | Effort | Evidence & notes |
|---|---|---|---|---|---|
| E1 | **Tamper-evident / signed report bundle** — hash the SQLite log + report (and optionally sign), so an adjudicator can verify the record wasn't edited or the device relocated after the fact. | P4,P5,P6,P9 | **P1** | M | Converts residual-risk row 1 (tampering "accepted") into adjudicator trust; PMs/boards need defensible evidence. [doc][hoa] **[NET-NEW]** |
| E2 | **Paired / comparative view** — overlay two devices or two rooms, or before/after a mitigation, on one timeline (supports R4 corroboration and mediation). | P3,P4,P5 | **P2** | M | Deterministic charts already support a data-table-paired figure. **[NET-NEW]** |
| E3 | **Guided calibration with reference handoff** — walk the user through comparing against a reference meter (or a clearly-hedged NIOSH-grade app), storing the instrument's make/class in the session and showing an uncertainty band. | P6,P10 | **P2** | M | Session table already holds calibration offset/note; add instrument provenance + uncertainty. [iec][app] **[extends calibration ADR]** |
| E4 | **PWA "share to property manager"** — one-tap export of the honest violations HTML/CSV (with the R1 cover page) from a phone, no Pi required. | P1,P2 | **P2** | S | PWA already produces the same exports offline; this is packaging + the cover page. **[extends PWA parity]** |
| E5 | **Jurisdiction-aware quiet-hours / rule template library** — pick a city ordinance or paste a lease/CC&R clause → preset quiet-hours window + an explicit "verify your local rule; this is not legal compliance" disclaimer. | P1,P5,P9 | **P2** | M | Ordinances/CC&Rs vary; tool must template *and* disclaim. [ord][hoa][rec] **[NET-NEW]** |
| E6 | **"For both parties" / mediation framing mode** — a neutral report variant whose language acknowledges both sides, for a PM or mediator to share without it reading as an attack. | P3,P4,P5 | **P2** | S | Directly serves the "informational, not adversarial" principle the ethics audit commits to. [qe][hoa] **[NET-NEW]** |
| E7 | **Coverage / drift health check** — surface from existing frame-coverage accounting a "this run measured X% of the time; device hasn't moved" health line, so silent undercount or a bumped mic is visible. | P10,P4,P6 | **P2** | S | Frame-coverage is already counted; this exposes it as an integrity signal. **[corroborates frame-coverage ADR — surface as health check]** |

---

## Sequenced roadmap

**Now (sharpen honesty & legibility — mostly reuse of shipped text):**
R1 cover page · R2 calibration banner + provenance · R5 reader-facing no-audio note ·
R6 measurement-conditions prominence.

**Next (make it trustworthy to adjudicators):**
E1 tamper-evident bundle · R3 ordinance duration rollup · R4 corroboration / second-log
alignment · R7 export a11y parity.

**Soon (broaden fit & reduce overclaim):**
E5 jurisdiction template library · E6 mediation framing · E3 guided calibration +
uncertainty · R8 tuning presets · R9 hint suppression in exports · E2 paired view ·
E4 PWA share-to-PM · E7 coverage health check.

## Recommended first sprint (highest-leverage, mostly already-built)

The panel and the existing strategy converge: the cheapest, highest-trust wins are
about **surfacing honesty that already exists** and **making the record hard to
dispute.** Ship these five:

1. **R1 — "What this can & cannot prove" cover page on every export.** One reusable
   block, prepended to the report and the violations CSV/HTML. Answers the single
   most-repeated friction (P1, P4, P5, P6, P9) and costs an afternoon. **[corroborates]**
2. **R2 — calibration honesty banner + record the reference instrument.** Makes the
   skeptic's core objection structurally impossible to miss: an uncalibrated reading
   never gets to look like dB(A). [spl][app][iec] **[corroborates]**
3. **R5 — reader-facing no-audio / recording-law note.** Turns the levels-only
   constraint into a visible trust signal for the neighbor/PM/board. [rec] **[corroborates]**
4. **R3 — ordinance/CC&R duration rollup (no verdict).** Expresses the numbers against
   the rule the way adjudicators actually read it, while holding the "within quiet
   hours ≠ violation" line. [ord][hoa] **[NET-NEW]**
5. **E1 — tamper-evident report bundle.** Closes the gap every adjudicator (P4, P5) and
   the attorney (P9) raised: an honest record the *other side* can trust wasn't edited.
   **[NET-NEW]**

All five lean on shipped infrastructure (the report renderer, the violations export,
the session lineage, the calibration store) and each carries the no-audio guarantee
unchanged. Bundle the afternoon-sized **R6** and **R9** alongside.

## Traceability matrix (persona → items)

| Persona | Remediations | Expansions |
|---|---|---|
| P1 Dog owner (user) | R1, R2, R3, R8 | E4, E5 |
| P2 Accused renter | R8 | E4 |
| P3 Complaining neighbor | R4, R5 | E2, E6 |
| P4 Property manager | R1, R3, R4, R6 | E1, E2, E7 |
| P5 HOA / mediator | R1, R3 | E1, E2, E5, E6 |
| P6 Acoustics skeptic | R1, R2, R6, R9 | E1, E3, E7 |
| P7 Accessibility user | R7 | — |
| P8 Privacy advocate | R5, R9 | — |
| P9 Legal-aid attorney | R1, R3, R4, R5, R9 | E1, E5 |
| P10 Pi self-hoster | R2, R6 | E3, E7 |
| P11 Owner / maintainer | R1, R5 (single-source the limits text) | E1 |

## Validate with real users / risks

This backlog is derived from a **synthetic** panel plus public sources, so before
building, pressure-test the assumptions that carry the most risk:

- **Does any nearby adjudicator actually accept this?** The premise that a credible,
  honest *log* helps is well-supported [ord][doc][hoa], but several ordinances also
  contemplate **audio/video** or a **second household**, and admissibility is
  **local**. Talk to an animal-control officer and a property manager before assuming
  a levels-only export carries weight. *Risk: the format is honest but not what a
  given jurisdiction will act on.* → de-risked partly by **R3, R4, E5**.
- **Will the cover page actually be read?** R1/R5 assume a prominent caveat changes
  behavior; it might be skimmed too. Test the framing with a non-expert reader. *Risk:
  honesty theater.*
- **Does "ordinance rollup" (R3) invite overclaiming** despite the no-verdict rule?
  The skeptic (P6) and attorney (P9) flag exactly this. Keep "within quiet hours ≠
  violation" verbatim and consider review-gating R3's copy.
- **Tamper-evidence scope (E1).** A hash proves the file wasn't edited *after* signing;
  it cannot prove the device wasn't misplaced or mis-tuned *before*. Pair it with **R6/E7**
  and say so, or it over-promises.
- **Calibration reality (R2/E3).** Most users won't own a reference meter; a phone-app
  reference is itself ±2 dB and uncalibrated [app]. Frame calibration as "less wrong,
  still an estimate," never "now it's SPL."

## Honest limits of this roadmap

Every item traces to a synthetic interview and/or a cited source — **not** to a real
user, a real dispute outcome, or a count of people who'd use this. The panel
over-represents the author's mental model and the public sources cited, and the
legal/acoustics findings are **jurisdiction-dependent** illustrations, not the rule
where any user lives. Priorities here are a demand×leverage *guess*, not a commitment;
they intentionally stay inside the project's existing pillars (no-audio gate,
measurement honesty) rather than inventing new scope. **Treat this as the agenda for
real discovery** — a tenant in a dispute, a property manager, an HOA board member, an
animal-control officer, and an acoustician — not as a substitute for it. Source panel:
[`USER-RESEARCH.md`](./USER-RESEARCH.md); canonical plan: [`ROADMAP.md`](./ROADMAP.md).
