# User Research — Synthetic Personas & Simulated Interviews

> [!WARNING]
> **These personas and interviews are synthetic.** They were generated as a
> structured brainstorming device — *not* conducted with real people. No real
> neighbor, property manager, judge, or acoustician said any of this. The panel
> exists to pressure-test the product from every side of a noise dispute at once;
> it is **not** evidence of demand, and it does **not** substitute for talking to
> real users in a real dispute. Treat every "quote" as a hypothesis to validate,
> not a finding. This is consistent with how the project labels its synthetic test
> sessions (see [`audits/methodology-and-limitations.md`](./audits/methodology-and-limitations.md)).
>
> Where a persona "values" something, it is mapped to a **feature that actually
> exists in the repo today** — no invented capabilities. Legal and acoustics claims
> below are summarized from cited public sources and are **jurisdiction-dependent**;
> nothing here is legal advice.
>
> **Last assembled: 2026-06-30.**

## Why do this at all

A noise dispute is unusual among software problems: the people on every side of it
are *adversaries by default*. The dog owner, the complaining neighbor, the property
manager who has to choose between two tenants, the board, the skeptic who knows
dBFS isn't SPL — each wants something different from the same six numbers per event.
Role-playing the full cast forces the question this tool lives or dies on: **does a
levels-only, no-audio record actually help, given what ordinances and adjudicators
say they will accept?** The synthesis is tagged so it stays honest and doesn't
become a wishlist.

## How to read a persona

Each card compresses a simulated interview to five lines: **Goal · Values today
(real features) · Gets stuck · Wants next · Adopts / walks.** "Values today" points
only at shipped behavior — the no-audio gate, the methodology/limitations section,
the quiet-hours violations export, calibration honesty, the day×hour heatmap, the
PWA, the accessible report. Frictions feed **Remediations (R)** and wishes feed
**Expansions (E)** in [`RESEARCH-ROADMAP.md`](./RESEARCH-ROADMAP.md).

---

## Method

- **Sampling frame.** Everyone a real barking/noise dispute pulls in: the person
  *building a record* (the dog owner defending against vague complaints; a renter
  accused of noise more broadly); the people who *adjudicate* (the complaining
  neighbor, the property manager/landlord, the HOA board / mediator); the people who
  *decide whether to trust the number* (an acoustics skeptic, an accessibility user
  who has to read the report at all); the people who *vet the posture* (a privacy
  advocate, a tenant-rights attorney); and the people who *operate and build it* (a
  Raspberry-Pi self-hoster, the owner/maintainer).
- **Protocol.** For each persona: a goal, a walkthrough of the surfaces they'd touch
  (the report, the violations export, the live meter, the PWA, the Pi service), what
  worked against the **current** implementation, where they'd stall, what they'd want
  next, and the one thing that makes them adopt or walk.
- **Synthesis.** Frictions → Remediations; wishes → Expansions. Each carries the
  personas who raised it, a rough priority, and an effort estimate, with a
  traceability matrix in the roadmap.
- **Effort scale.** S ≈ an afternoon · M ≈ a day or two · L ≈ a week+.

### Research basis (what grounds the personas; cited, access date 2026-06-30)

The cast's incentives, frustrations, and "is this even admissible" worries are
modeled on public sources, not imagination. High-stakes legal/acoustics claims are
cross-checked against ≥2 sources. Full evidence-to-item mapping is in the roadmap.

- **What barking-nuisance ordinances actually ask for.** Many jurisdictions require
  the complainant to keep a **dated, timed log of barking and its duration**, and
  several require a **second household** to corroborate before enforcement; common
  thresholds are framed as "incessant" (≈30 continuous minutes) or "intermittent"
  (≈60 minutes on-and-off in 24 h). See
  [Contra Costa County Noisy Animal Ordinance](https://www.contracosta.ca.gov/6839/Noisy-Animal-Ordinance),
  [OC Animal Care barking-dog complaint process](https://ocpetinfo.com/page/barking-dog-animal-nuisance-complaint-process),
  [LA Animal Services — Nuisance Barking](https://www.laanimalservices.com/nuisance-barking),
  and [Justia — Barking Dogs and Neighbors' Legal Rights](https://www.justia.com/animal-dog-law/barking-dogs-and-neighbor-rights/).
  *Critically for this tool: these sources weight a credible timed **log**, and some
  contemplate audio/video, but evidence rules are jurisdiction-specific.*
- **How tenants/PMs are told to document noise.** Guidance converges on a clinical,
  timestamped log (date, exact start/end, duration, source description, impact) and a
  written paper trail; a decibel reading "adds objective weight." See
  [Flex — apartment noise-complaint template](https://getflex.com/blog/apartment-noise-complaint-letter-email-template),
  [Local Noise Laws — documenting a noise complaint](https://www.localnoiselaws.com/blog/documenting-noise-complaints/),
  and [LawInfo — handling tenant noise complaints](https://www.lawinfo.com/resources/landlord-tenant/handling-noise-complaints-from-tenants.html).
- **How HOAs adjudicate.** Boards enforce CC&R nuisance/quiet-hours provisions through
  a notice-and-hearing process (in CA, Davis-Stirling internal dispute resolution),
  and want precise, timestamped incidents. See
  [MBK Chapman — California HOAs and noise complaints](https://mbkchapman.com/california-hoa-noise-complaints-fact-sheet/)
  and [Manning & Meyers — managing noise complaints in condominiums](https://www.hoalegal.com/blog/managing-noise-complaints-in-condominiums-legal-perspectives/).
- **Quiet enjoyment.** The implied covenant gives tenants peaceful possession; a
  *substantial* interference (not a minor annoyance) can breach it and obligates the
  landlord to act. See
  [Cornell LII — covenant of quiet enjoyment](https://www.law.cornell.edu/wex/covenant_of_quiet_enjoyment)
  and [Texas State Law Library — noise (landlord/tenant)](https://guides.sll.texas.gov/landlord-tenant-law/noise).
- **Why no-audio is the whole design (recording law).** Roughly a dozen states require
  **all-party consent** to record a private conversation, and an illegally captured
  recording is often inadmissible and can carry criminal penalties; a device left
  running in a home that captured audio could implicate household members, guests, or
  sound carrying from a neighbor. See
  [RCFP Reporter's Recording Guide](https://www.rcfp.org/introduction-to-reporters-recording-guide/),
  [Recording Law — two-party-consent states (2026)](https://www.recordinglaw.com/party-two-party-consent-states/),
  and [Justia — recording phone calls & conversations, 50-state survey](https://www.justia.com/50-state-surveys/recording-phone-calls-and-conversations/).
  *(State counts/lists differ between sources — e.g., whether Delaware/Oregon are
  counted — which is exactly why the tool claims no jurisdiction-specific compliance.)*
- **Why dBFS ≠ SPL, and why uncalibrated readings are relative only.** dBFS is
  referenced to digital full scale (always ≤ 0) and is *not* sound pressure level
  (dB SPL, referenced to 20 µPa); dB(A) is A-weighted SPL and is what noise
  regulations use. Uncalibrated phone/browser/Pi mics measure *relative* level and
  can be off by 5–15 dB or more. See
  [Wikipedia — dBFS](https://en.wikipedia.org/wiki/DBFS) and
  [AudioMasterclass — 0 dB vs 0 dBFS](https://www.audiomasterclass.com/blog/what-is-the-difference-between-0-db-and-0-dbfs).
- **What a "real" meter is (IEC 61672).** Sound level meters are graded Class 1
  (precision) vs Class 2 (general purpose) with defined tolerances and frequency
  ranges; environmental-noise regulations often specify Class 1, occupational rules
  accept Class 2. See
  [SoftdB — Class 1 vs Class 2](https://www.softdb.com/blog/class-1-vs-class-2-sound-level-meter/),
  [IEC 61672-1:2013](https://webstore.iec.ch/en/publication/5708), and
  [NoiseMeters — type/class definitions](https://www.noisemeters.com/help/faq/type-class/).
- **Phone/app accuracy in practice.** NIOSH found that of 192 evaluated apps, only a
  handful met a ±2 dB(A) criterion vs a Type-1 reference; its own app is "accurate
  within ±2 dB(A)" tested in a reverberant chamber and **only meets IEC 61672 Type 2
  with a calibrated external microphone**, and NIOSH does not position it for
  compliance. See
  [NIOSH/CDC — Sound Level Meter App](https://www.cdc.gov/niosh/noise/about/app.html)
  and [Kardous & Shaw 2014 — evaluation of smartphone sound apps (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC4659422/).

---

## Persona roster

| # | Persona | Group | Primary goal | Top friction |
|---|---|---|---|---|
| P1 | **Chelsea** — dog owner, primary user | Log & Defend | Show the *real* pattern when a neighbor complains about Olive | Worries the report reads as "she built a case" not "here's the truth" |
| P2 | **Marcus** — renter accused of general noise | Log & Defend | Push back on a vague "you're too loud" with data | His noise isn't a dog; wants the same record for footfall/music |
| P3 | **Diane** — downstairs complaining neighbor | Adjudicate | Be believed that it's genuinely disruptive at night | A device run by the accused looks self-serving to her |
| P4 | **Raymond** — property manager / landlord | Adjudicate | Decide fairly between two tenants without picking sides | Can't tell if a tenant's log is honest or cherry-picked |
| P5 | **Yolanda** — HOA board member & mediator | Adjudicate | Apply the CC&R quiet-hours rule defensibly | Needs timestamped incidents she can take to a hearing |
| P6 | **Dr. Petra Voss** — acoustical consultant / skeptic | Trust the Measurement | Refuse to let dBFS masquerade as SPL | "This isn't a Class-1 meter; the number is relative" |
| P7 | **Greg** — accessibility user of the report (screen reader) | Trust the Measurement | Actually read the report the PM forwarded him | Charts are useless to him if there's no text equivalent |
| P8 | **Nadia** — privacy & digital-rights advocate | Assure & Audit | Confirm nothing is recording her or the neighbors | Most "noise apps" quietly record audio |
| P9 | **Tom** — tenant-rights / legal-aid attorney | Assure & Audit | Know whether this helps or hurts a client's case | Worries clients over-read a chart as proof of source |
| P10 | **Sam** — Raspberry-Pi maker / self-hoster | Operate / Build | Run it unattended and trust it's local-only | Wants proof it never phones home |
| P11 | **Chelsea (maintainer hat)** — owner/maintainer | Operate / Build | Keep the no-audio gate un-breakable across changes | One careless commit could add an audio path |

---

## Group A — Log & Defend (the person building a record)

### P1 — Chelsea, dog owner & primary user (defending Olive)
- **Goal:** when the downstairs neighbor complains about Olive, replace "she's always
  barking" with an honest, time-stamped picture of when sound actually crossed a
  threshold and for how long.
- **Values today:** the **no-audio guarantee** (she can run it in her own apartment
  without recording herself, guests, or anyone next door); the **quiet-hours
  violations export** that lists **every** event with a within/outside flag so it
  can't be a cherry-picked subset; the **day×hour calendar heatmap** that shows the
  real pattern; the **methodology + limitations** section that makes it read as
  honest, not adversarial.
- **Gets stuck:** the limitations are present but *buried* — she worries a stressed
  neighbor or PM skims the charts and misses "this can't prove Olive made the sound."
  She's not sure what threshold/quiet-hours to set for *her* building's rule.
- **Wants next:** a plain-language "what this can and cannot prove" cover page on the
  export; a way to map quiet-hours to her actual lease/ordinance; one-tap "send to
  property manager" from her phone.
- **Adopts if:** the report visibly protects her *and* the neighbor from being
  over-read. **Walks if:** it ever looks like a tool for building a case against
  someone — that's the opposite of why she made it.

### P2 — Marcus, renter accused of general noise (not a dog)
- **Goal:** his upstairs neighbor reported "constant stomping and bass." He wants the
  same honest record — was it actually loud, when, for how long — to discuss calmly
  with management.
- **Values today:** the tool measures **levels and event metadata only**, so it works
  for footfall/music exactly as it does for barking; the **PWA** means he doesn't need
  a Raspberry Pi; **local-only / no egress** means his data isn't going anywhere.
- **Gets stuck:** defaults are tuned for barking-ish events (threshold −35 dBFS,
  min-duration 0.4 s, 1.0 s debounce); he's unsure how to tune for sustained music vs
  short thumps. No guidance for "my noise is different from a dog."
- **Wants next:** tuning presets for a few noise types; a clearer live meter read on
  the PWA while he adjusts; a neutral framing so management doesn't read it as him
  building a counter-case.
- **Adopts if:** he can produce something that makes the conversation factual.
  **Walks if:** tuning is guesswork and the numbers feel arbitrary.

---

## Group B — Adjudicate (the other side and the deciders)

### P3 — Diane, downstairs neighbor who complained
- **Goal:** be taken seriously that the barking genuinely wakes her — she's not
  exaggerating, and she resents being framed as the unreasonable one.
- **Values today:** that the export is **honest by construction** — it shows *all*
  events, not a flattering subset; that it **explicitly disclaims source
  attribution**, which (counterintuitively) makes her trust it *more*, because it
  isn't pretending to be something it's not.
- **Gets stuck:** a record produced by the *accused party's own device* reads as
  self-serving to her; she has no way to corroborate with her own experience, and the
  ordinance she looked up seems to want *her* log too.
- **Wants next:** a way to align her own dated log against the device's timeline; an
  explanation, in language she'd accept, of why there's no audio (right now it looks
  like the data is conveniently incomplete).
- **Adopts if:** the framing acknowledges her side and lets her corroborate. **Walks
  if:** it's presented as "proof the neighbor is fine," which would harden the dispute.

### P4 — Raymond, property manager / landlord
- **Goal:** adjudicate between two tenants without becoming the bad guy to either, and
  without exposing himself to a quiet-enjoyment complaint from the side he doesn't side
  with.
- **Values today:** a **timestamped, reproducible** record beats "he-said-she-said";
  the **violations CSV/HTML** is exactly the format his documentation guidance asks for
  (date, start/end, duration); the **measurement-conditions / lineage** section tells
  him *where and how* it was measured.
- **Gets stuck:** he can't tell whether a tenant edited the SQLite file or moved the
  device to a louder spot; "within quiet hours" sounds like a verdict but is only "a
  level crossed a threshold here." He needs to defend his decision if challenged.
- **Wants next:** a tamper-evident/signed export he can trust; a one-line "what this
  does and doesn't establish" he can paste into a notice; the ability to weigh it
  alongside the complaining household's own log.
- **Adopts if:** it makes his decision *more* defensible, not less. **Walks if:** a
  tenant can quietly fake it, or it invites a tenant to over-claim.

### P5 — Yolanda, HOA board member & volunteer mediator
- **Goal:** apply the community's quiet-hours covenant consistently and survive a
  hearing or internal dispute-resolution step.
- **Values today:** **configurable quiet-hours** she can set to the CC&R window
  (default 22:00–08:00, wraps midnight); the **honest export** that won't get torn
  apart for cherry-picking; the **methodology section** that pre-empts "your evidence
  is junk."
- **Gets stuck:** she needs incident *counts and durations* mapped to how the covenant
  is written (e.g., "X minutes during quiet hours over N nights"), and a neutral tone
  so a board action doesn't look like harassment of one homeowner.
- **Wants next:** an ordinance/CC&R-style rollup (duration-in-window per day) that
  stops short of declaring a violation; a mediator-friendly "for both parties" framing;
  guidance that the device's number is *informational*, not a regulatory measurement.
- **Adopts if:** it helps her be fair and defensible. **Walks if:** it pushes a verdict
  the board can't actually stand behind.

---

## Group C — Trust the Measurement

### P6 — Dr. Petra Voss, acoustical consultant (the skeptic)
- **Goal:** stop a relative number from being paraded as an absolute one. If it's not a
  calibrated Class-1 (or at least Class-2) measurement, it must not read like dB(A).
- **Values today:** that the project **already says this out loud** — uncalibrated
  **dBFS is relative, not SPL**; calibration offset defaults to 0.0 and the report
  states so; the **limitations** list "relative, not absolute," "no source
  attribution," and "placement-dependent" verbatim; the **calibration helper**
  (`olive-calibrate`) exists and the **session lineage** records placement/offset.
- **Gets stuck:** a non-expert reader still sees a chart of "dB-ish" numbers and infers
  loudness in the regulatory sense; the calibration path needs a *reference meter* most
  users don't own, and even a NIOSH-grade phone app is only ±2 dB(A) and only Type 2
  with an external calibrated mic — she wants that uncertainty shown, not implied.
- **Wants next:** an unmissable "uncalibrated → relative only" banner; calibration that
  records the reference instrument's make/class in the session; an honest uncertainty
  band rather than point values; the coarse bark/ambient "hint" kept clearly hedged or
  hidden in adjudication exports.
- **Adopts if:** the tool never lets a relative number impersonate SPL. **Walks if:** a
  single screen implies courtroom-grade measurement.

### P7 — Greg, accessibility user of the report (screen-reader, low vision)
- **Goal:** read the report the property manager forwarded — he's a tenant in the
  building too, and the charts are meaningless to him without text.
- **Values today:** the report is built to **WCAG 2.2 AA**: every chart `<figure>` has
  a **data-table equivalent** with a caption, every `<svg>` carries `role="img"` + an
  `aria-label`, the heatmap prints the **count as text in each cell** (meaning never
  depends on color), there's a **skip link**, one `<h1>`, logical headings, visible
  focus, and a structural a11y gate plus pa11y/axe in CI.
- **Gets stuck:** the strong a11y story is documented for the **HTML** report; if the
  PM exports/prints a **PDF** and forwards that, he's not sure the table equivalents and
  tags survive. The violations export specifically hasn't been walked with a screen
  reader in the audit.
- **Wants next:** confirmed a11y parity for the PDF/print path and the violations
  export; a screen-reader walkthrough artifact for the export, not just the main report.
- **Adopts if:** he can extract every number without sighted help. **Walks if:** the
  forwarded artifact is an untagged image of a chart.

---

## Group D — Assure & Audit (privacy and legal posture)

### P8 — Nadia, privacy & digital-rights advocate
- **Goal:** verify that a device marketed as "listens in your home" genuinely cannot
  record anyone — the bar most "noise monitor" products fail.
- **Values today:** the **no-audio guarantee proven by construction** — frames are
  reduced to a dBFS number in memory and discarded, there is **deliberately no API that
  writes a frame**, the SQLite schema has **no column that can hold audio**, and
  **merge-blocking tests** (static `wave`/`soundfile`/`.tobytes` scan, `"wb"` AST scan,
  schema introspection) fail the build if that changes; plus **no-egress** proof (import
  scan + a `socket` booby-trap) and a `systemd` unit with `PrivateNetwork`.
- **Gets stuck:** all of this is real but lives in audit docs; the *reader* of a report
  (a neighbor, a PM, a judge) has no idea the no-audio choice is a deliberate
  privacy/recording-law posture rather than a missing feature.
- **Wants next:** a short, reader-facing "why there is no audio" note embedded in the
  report itself; the no-audio/no-egress guarantees surfaced where a layperson sees them.
- **Adopts if:** the privacy posture is legible to non-engineers, not just provable in
  tests. **Walks if:** marketing ever softens "never records" into "doesn't usually."

### P9 — Tom, tenant-rights / legal-aid attorney
- **Goal:** advise a client whether running this helps or hurts — and make sure nobody
  over-reads a chart in a way that backfires.
- **Values today:** the relentless **"informational, not adversarial"** framing; the
  **recording-law rationale** (level-only sidesteps two-party-consent / eavesdropping
  exposure because there is no captured conversation to consent to, subpoena, or leak);
  the explicit **"no source attribution"** and **"not legal compliance in any
  jurisdiction"** disclaimers.
- **Gets stuck:** ordinances and adjudicators vary wildly — some want a corroborating
  second household, some contemplate audio/video, all are local; a client could wave a
  heatmap and say "this proves it," which is exactly what the tool says it does *not* do.
- **Wants next:** the jurisdiction-dependence stated plainly *in the export*; a
  reader-facing limits/recording-law note; an option to suppress the bark/ambient "hint"
  in anything shown to an adjudicator; clarity that "within quiet hours" ≠ "violation."
- **Adopts if:** it lowers the chance a client overclaims. **Walks if:** the output
  invites someone to treat a relative level as legal proof of who did what.

---

## Group E — Operate / Build

### P10 — Sam, Raspberry-Pi maker / self-hoster
- **Goal:** run it headless on a Pi in his own unit, unattended, and *know* it's
  local-only and resilient.
- **Values today:** **`scripts/setup-pi.sh`** + the hardened **`systemd` unit**
  (`PrivateNetwork`, `ProtectSystem`, auto-restart); **`resilient_source`** reconnect
  with capped backoff; the **atomic heartbeat JSON** for a watchdog; **WAL** durability,
  `user_version` schema migrations, and config-driven **retention pruning**; a
  **zero-runtime-dependency pure-Python core** (only the optional `live` extra needs
  PortAudio).
- **Gets stuck:** calibrating without a reference meter; knowing the device hasn't
  silently drifted or been bumped to a louder spot; reading the report on a headless box.
- **Wants next:** a guided calibration flow (ideally recording the reference
  instrument used); a placement/coverage health check surfaced from the existing
  **frame-coverage accounting**; an easy way to ship the HTML report off the Pi for
  viewing without adding network surface.
- **Adopts if:** it's boring and trustworthy and provably offline. **Walks if:** it
  needs cloud anything, or coverage problems hide silently.

### P11 — Chelsea, owner & maintainer (operating the project)
- **Goal:** keep the central design gate — **no audio, ever** — unbreakable as the
  code evolves, and keep the honesty (limitations, calibration) non-optional.
- **Values today:** the gate is enforced **by construction and by CI**: no-audio static
  + schema tests, no-egress tests, a **report-content test** that asserts the
  methodology + limitations text is present, **deterministic SVG** reports with
  **snapshot tests**, a **structural a11y gate**, and coverage thresholds — all
  merge-blocking. The **PWA is a parallel implementation** with its own Node tests
  sharing the same guarantees.
- **Gets stuck:** keeping Python and the PWA semantically in sync; making sure new
  surfaces (exports, the heatmap, future features) inherit the limitations text and the
  a11y/data-table rules rather than re-deriving them; the limitations are canonical in
  one doc but rendered in several places.
- **Wants next:** a single canonical source for the limitations/recording-law text
  that every surface (report, violations export, PWA, a future cover page) pulls from;
  parity tests across Python/PWA; a contributor note that any new export must carry the
  limitations and pass the a11y gate.
- **Adopts if:** it stays impossible to ship an audio path or a limitations-free
  artifact. **Walks if:** the guarantees become promises in a README instead of tests.

---

## Cross-cutting themes (what the cast agrees on)

1. **The limitations are correct but *buried*.** The single most-repeated friction —
   from the owner (P1), both adjudicators (P4, P5), the skeptic (P6), the advocate
   (P8), and the attorney (P9) — is that the honest caveats live in a methodology
   section a stressed layperson skims past. The fix is to **lift "what this can and
   cannot prove" to a cover page on every export.** Cheap; highest-leverage.
2. **"Relative, not SPL" must be unmissable.** P6 is the loudest, but P4 and P9 also
   risk reading a dBFS chart as regulatory loudness. The repo already says it; the gap
   is *prominence* and an honest uncertainty story, plus calibration that records the
   reference instrument. ([dBFS vs SPL](https://en.wikipedia.org/wiki/DBFS);
   [NIOSH app ±2 dB / Type 2 only with external mic](https://www.cdc.gov/niosh/noise/about/app.html).)
3. **No-audio is a *feature to advertise to readers*, not just a test.** P8 and P9
   note the privacy/recording-law rationale is invisible to the neighbor/PM/judge who
   reads the report. Surfacing a plain-language "why there's no audio" turns the
   constraint into a trust signal. ([RCFP](https://www.rcfp.org/introduction-to-reporters-recording-guide/);
   [Recording Law](https://www.recordinglaw.com/party-two-party-consent-states/).)
4. **Adjudicators need it to be tamper-evident and corroborable.** P4 and P5 can't act
   on a record the accused could have edited; P3 and the ordinances want a *second*
   household's log to count. A signed/hashed export and a "bring your own log to align"
   affordance address both. ([ordinance two-household practice](https://ocpetinfo.com/page/barking-dog-animal-nuisance-complaint-process).)
5. **Map to the rule, but never declare the verdict.** Everyone in Group B wants the
   numbers expressed against *their* rule (a duration-in-quiet-hours rollup), and
   everyone in Groups C/D insists "within quiet hours" must stay "a level crossed a
   threshold here," not "a violation occurred." The roadmap must do both at once.
6. **Accessibility can't stop at the HTML.** P7 reminds us the strong a11y story is
   audited for the main HTML report; the *forwarded* artifact (PDF/print, violations
   export) is what an adjudicator actually shares, and it needs the same parity.

## Honest limits of this exercise

This is simulated. It can surface plausible needs and obvious gaps from many sides of
a dispute, but it **cannot** tell you which are real, how many people would actually
use this, or whether any ordinance/PM/board near you would accept the output. It
over-represents the author's mental model and the public sources cited, and it will
miss what only real disputants surprise you with. Several findings hinge on
**jurisdiction-specific** law (recording consent, what evidence is admissible, how a
board must give notice) — the cited sources illustrate the *shape* of these rules, not
the rule where any given user lives. **Do not prioritize a roadmap off this panel
alone.** Use it to design questions for, and lower the cost of, real conversations
with a tenant in a dispute, a property manager, an animal-control officer, and an
acoustician. Triaged, evidence-tagged backlog: [`RESEARCH-ROADMAP.md`](./RESEARCH-ROADMAP.md).
