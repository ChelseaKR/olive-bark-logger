# Expansions (EXP-01 … EXP-16) — 2026-07-01

Three horizons. Every item is net-new relative to `ROADMAP.md` and
`RESEARCH-ROADMAP.md`; where one builds on an R#/E# or a ROADMAP section it says so and
goes beyond it. Effort tiers as in `02-large-scale-fixes.md`.

---

## H1 — Deepen the core

### EXP-01 · Ambient baseline ledger (per-minute level aggregates)
**Pitch:** Persist a tiny per-minute summary of ambient level (min/median/max/L90 dBFS)
alongside events — numbers, never audio.
**Impact:** Transforms the evidence quality. Today the DB records *only* threshold
crossings (`store/db.py`); there is no record of what the room's baseline was, so a
skeptic can claim the threshold was tuned to manufacture events, and a quiet night is
indistinguishable from a dead mic (see FIX-03). A baseline ledger shows event-to-ambient
contrast ("events peaked 22 dB above that hour's median"), supports post-hoc threshold
audits, and gives the R2 calibration story context.
**Shape:** a `minute_levels` table (session_id, minute_start, min/median/max/L90,
frames); computed streaming in `run_pipeline` from the same per-frame levels the
detector already sees — zero extra audio exposure; rendered as a background band in
the day charts (`report/charts.py`) with its data-table equivalent.
**Effort:** M–L. **Risks/deps:** MUST pass FIX-13's privacy budget first (4 scalars/min
is well under any speech-reconstruction floor, but the analysis must be written, not
assumed); storage growth is trivial (~2 MB/year). **Excellence bar:** report shows
ambient context for every event day; a written budget analysis; determinism preserved
(snapshot-stable).

### EXP-02 · Event anatomy (bounded per-event envelope stats) — ✅ DONE (2026-07-12)
**Status:** Implemented in the Python pipeline and exports. SQLite v7 adds nullable
`rise_time_s`, `loud6_s`, and `longest_run_s` fields; the streaming detector computes
them with O(1) counters, legacy rows remain readable, and CSV/quiet-hours HTML expose
the values. The no-audio schema allowlist and data card were updated deliberately.
**Pitch:** Store a few shape descriptors per event — rise time, seconds above
threshold+6 dB, longest continuous loud run — so a report reader can distinguish "one
90-minute drone" from "300 sharp barks."
**Impact:** The six current numbers flatten very different phenomena; adjudicators (per
the panel's P4/P5) reason about character, not just duration. Improves the honesty of
the coarse tag by grounding it in disclosed features rather than one hidden ZCR value
(`monitor/features.py`).
**Shape:** extend `Detector` to accumulate envelope stats it already implicitly walks
past; new nullable columns (migration with FIX-01/FIX-02); render in the violations
table; feed R9's export-suppression logic so anatomy can be included while tags are
omitted.
**Effort:** M. **Risks/deps:** FIX-13 budget; Event dataclass gate
(`test_event_has_no_audio_field`) updated deliberately, in the same diff as the budget
doc. **Excellence bar:** each stored field has a one-line justification in the data
card (`docs/audits/data-card.md`); anatomy is explainable in one sentence to a
layperson.

### EXP-03 · Threshold sensitivity view ("would this hold at ±6 dB?")
**Pitch:** A report section recomputing event counts under alternative thresholds from
the ambient ledger, published *pre-emptively*.
**Impact:** Directly answers the strongest attack on the record ("you picked the
threshold that flatters you") — the acoustics-skeptic objection the research pass
(P6) documents but doesn't structurally solve. Publishing your own sensitivity analysis
before being asked is honesty-as-a-feature at its best.
**Shape:** given `minute_levels` (EXP-01) plus per-event peaks, estimate counts at
threshold ±3/±6 dB; render as a small table with the caveat that re-detection from
levels is approximate; never lets the *headline* numbers move.
**Effort:** M. **Risks/deps:** EXP-01; approximation must be honestly labeled or it
backfires. **Excellence bar:** the section survives review by an acoustics SME
(review gate); wording review-gated like R3's copy.

### EXP-04 · Advisory recalibration & drift watch
**Pitch:** A nightly, *advisory-only* check comparing recent ambient percentiles to the
calibration epoch's, flagging probable mic drift or placement change — never silently
adapting detection.
**Impact:** Goes beyond R8 (static presets) and E3 (guided calibration): long
deployments drift, and today nothing notices until numbers look odd. Detection
parameters stay fixed per session (evidence stability); the tool just tells the
operator "your baseline moved 5 dB since calibration — re-run olive-calibrate."
**Shape:** compare `minute_levels` distributions across sessions; write a
`drift` advisory into the heartbeat and Measurement conditions; pairs with FIX-10's
clock anomalies as a general "integrity notices" block.
**Effort:** S–M. **Risks/deps:** EXP-01; false-positive tuning needs real deployments
(real-data gate for the default tolerance). **Excellence bar:** zero silent behavior
changes; a documented decision log of why adaptive *detection* was rejected.

### EXP-05 · Local ops console (gap-aware "last night" view) — ✅ DONE (2026-07-12)
**Status:** Implemented as a static, atomically replaced `status.html` snapshot. It
shows heartbeat freshness, the retained latest level, frame coverage, recorded gaps,
and recent/quiet-hours summaries without a server or network surface. It can derive its
path from `health_path` or run independently through an explicit `status_path`.
**Pitch:** A read-only, on-device status page — live level, heartbeat freshness,
coverage, gaps, last night's quiet-hours summary.
**Impact:** ROADMAP §3 lists "a small local dashboard" as a *Should* that was never
built (no dashboard code exists in the repo). This goes beyond that line item by
specifying an egress-compatible design: the monitor already writes an atomic heartbeat
JSON (`monitor/health.py`); extend the same pattern to write a static
`status.html` snapshot periodically — no server, no sockets, no violation of the
no-egress gate or `PrivateNetwork=true` in `deploy/olive-monitor.service`.
**Shape:** a `report/status.py` renderer reusing `_STYLE` and the chart primitives;
written by the FIX-04 periodic tick; documented "open this file" workflow (and the PWA
gets its equivalent screen in-app).
**Effort:** M. **Risks/deps:** FIX-03/FIX-04 provide the data; a11y gates apply to the
new surface. **Excellence bar:** an operator can answer "is it alive, is it covering,
what happened last night" in under 10 seconds without a terminal.

### EXP-06 · Accessible tagged PDF/A export
**Pitch:** A first-class, archival, screen-reader-usable PDF of the report and the
violations export, with the E1 bundle hash printed on it.
**Impact:** README promises "PDF/HTML" but only HTML with print CSS exists
(`report/render.py:_STYLE @media print`); what actually gets emailed to a property
manager is whatever a browser's print dialog produces — untagged, a11y-lossy. R7 audits
the print path; this replaces it with a real artifact suitable for filing.
**Shape:** evaluate a tagged-PDF generation path (e.g., WeasyPrint) as an *optional*
extra like `[live]` — the zero-dependency core ADR (ROADMAP §6) stays intact because
PDF generation is an export-side opt-in; embed document-level metadata, PDF/UA tags,
and the bundle hash; snapshot-test the intermediate deterministic HTML, not the binary.
**Effort:** M–L. **Risks/deps:** dependency decision needs an ADR; true PDF/UA
verification needs an assistive-tech reviewer (human gate). **Excellence bar:** veraPDF
PDF/A validation in CI; a committed screen-reader walkthrough of the PDF.

---

## H2 — Adjacent capabilities, audiences, integrations

### EXP-07 · Evidence interchange format + merge tool
**Pitch:** A versioned, signed JSON export ("this device, these sessions, these events,
these gaps, this hash chain") plus a CLI to merge/align two devices' exports on one
timeline.
**Impact:** Goes beyond R4 (corroboration affordance), E1 (bundle hashing), and E2
(paired view) by defining the *format and semantics* that all three need: many
ordinances weight a second household; today there is no defined way to combine two
olive DBs, handle clock skew, or verify the other party's file.
**Shape:** `report/interchange.py`: schema-versioned export of sessions + events +
gaps + calibration epochs with per-record hashes; `olive-merge` producing a two-source
comparative report (chart primitives already support paired tables); explicit
clock-skew disclosure using FIX-10 data.
**Effort:** M–L. **Risks/deps:** FIX-01/02/03 give it clean data to export; signature
scheme choice (age/minisign vs bare SHA-256 manifest) needs an ADR. **Excellence bar:**
a third party can verify an export with one documented command; merging two exports is
lossless and order-independent (property-tested).

### EXP-08 · Extract the privacy-gate kit to /STANDARDS (share with self-osint-monitor)
**Pitch:** Package the no-audio/no-egress enforcement pattern — forbidden-API AST
scans, schema introspection, runtime booby-traps, canary self-tests (FIX-11) — as a
reusable, vendorable test kit in `/STANDARDS`.
**Impact:** This repo and `self-osint-monitor` share the same threat-model DNA; today
the pattern lives only in `tests/test_no_audio.py`/`test_no_egress.py` here. Extracting
it makes "the guarantee is a merge-blocking test" a portfolio capability instead of a
repo trick, and strengthens the portfolio's public story about privacy engineering.
**Shape:** a parametrizable `privacy_gates` module (declare forbidden imports, forbidden
call patterns, schema rules) + docs page in `/STANDARDS`; both repos consume it via the
existing vendored-distribution mechanism; each repo keeps its domain-specific rules
(audio APIs here; whatever self-osint-monitor bans there).
**Effort:** M. **Risks/deps:** cross-repo change; STANDARDS review; must not weaken
this repo's stricter local rules. **Excellence bar:** both repos' gate suites are
one import + a declaration; a new portfolio repo can adopt the kit in under an hour.

### EXP-09 · Bilingual report output (reader-facing i18n)
**Pitch:** Let the operator generate the report/violations export in Spanish (first)
as well as English.
**Impact:** `docs/I18N.md` declares i18n N/A because output is "operator-only" — but
the research pass reframed the report as an artifact *for third parties* (neighbor, PM,
board), which quietly invalidates that rationale for the exported surfaces. In
mixed-language buildings, an honest record the recipient can't read isn't legible
evidence. Aligns with the portfolio's phased i18n migration (Phase 1 gettext pending
elsewhere).
**Shape:** wrap the reader-facing strings in `report/render.py`, `violations.py`, and
the branch's cover/banner constants with gettext; `--lang es` flag; the honesty
constants (`RELATIVE_DBFS_NOTE` etc.) become message IDs whose translations are
review-gated; update `docs/I18N.md` from N/A to scoped-applicable (export surfaces
only).
**Effort:** M. **Risks/deps:** translation of legally-flavored honesty copy REQUIRES a
qualified human reviewer (native-speaker + plain-language) — defer and say so, never
machine-translate the limitations text silently; report-content gates must assert the
notes in whichever language is rendered. **Excellence bar:** the Spanish limitations
text is sign-off-gated and byte-stable; the i18n declaration honestly reflects the new
scope.

### EXP-10 · Submission packet builder ("renter's noise-defense workflow")
**Pitch:** One command/tap that assembles everything a submission needs: cover page,
report, violations export, methodology, calibration provenance, bundle hash, and a
fill-in-the-blanks cover letter — as a single zip/folder.
**Impact:** Goes beyond E4 (PWA share button) and R1 (cover page): the artifacts exist
separately; real users assemble them badly under stress. Packaging is where honest
framing is most easily lost (people forward the CSV alone) — a packet keeps the
caveats attached to the numbers.
**Shape:** `olive-packet --out packet/` orchestrating existing renderers + E1 bundle;
letter templates deliberately neutral (E6's framing) with blanks, not generated claims;
PWA equivalent as a multi-file download.
**Effort:** M. **Risks/deps:** letter template language needs legal-aid review (human
gate — templates can drift into unauthorized-practice territory); depends on E1.
**Excellence bar:** the packet is coherent when any single file is separated from it
(every artifact self-carries the cover text — R1's rule, enforced by test).

### EXP-11 · Local automation hooks (Home Assistant et al., AF_UNIX only)
**Pitch:** An opt-in local event/heartbeat feed over a Unix domain socket or watched
file, so home-automation setups can, e.g., log "HVAC was running" alongside noise
events.
**Impact:** Confounder context is real evidentiary value — "events correlate with the
neighbor's schedule, not my dog's" needs other local signals. The hardened unit already
anticipates exactly this boundary: `RestrictAddressFamilies=AF_UNIX` with
`PrivateNetwork=true` (`deploy/olive-monitor.service`) permits local IPC while making
network egress impossible at the OS layer.
**Shape:** optional `--ipc-socket` emitting the same JSON as the heartbeat plus event
notifications; a documented HA config example; the no-egress AST gate gains an
explicit, tested carve-out for `socket.AF_UNIX` only (or the feature ships as a
separate opt-in module outside the gated core — decide by ADR).
**Effort:** S–M. **Risks/deps:** gate carve-out must be surgical (FIX-11's canary tests
prove AF_INET still banned); scope-creep risk toward a daemon platform — keep it
one-way, emit-only. **Excellence bar:** a test proving the IPC path cannot open an
INET socket; feature fully off by default.

### EXP-12 · "Olive-in-a-box" appliance image
**Pitch:** A flashable Raspberry Pi image: read-only rootfs, preinstalled service,
first-boot setup via a local captive page, reports retrievable by USB or the PWA.
**Impact:** Audience expansion from "senior engineer" to "person in a dispute."
`scripts/setup-pi.sh` is competent but assumes a terminal user; the people the research
personas describe (P1/P2) largely aren't that. This is the biggest single lever on
real-world use of the honest-evidence pattern.
**Shape:** pi-gen based image build in CI (artifact, not hosted service); read-only
root + overlayfs (also improves SD-card longevity and tamper posture); documented
"flash, plug in, calibrate with your phone as rough reference (E3), collect."
**Effort:** L–XL. **Risks/deps:** hardware test matrix is real-world work; first-boot
UX needs actual non-technical testers (human gate); support burden must be honestly
scoped as "no support, documented recipes." **Excellence bar:** a non-technical tester
goes from blank SD card to a rendered report without opening a terminal.

### EXP-13 · Recipient-side verifier ("trust this file" mode)
**Pitch:** A standalone, offline verifier for the *other side* — a property manager
drops in a received packet/bundle and gets: hash valid?, gaps disclosed?, calibration
state?, what the format can and cannot prove.
**Impact:** Goes beyond E1 (which creates tamper-evidence) by building the audience
that consumes it. Evidence formats succeed when *recipients* prefer them; a verifier
turns the honest format into the easy format for adjudicators, and is the seed of any
future "honest noise log" convention (EXP-16 adjacent).
**Shape:** a static, offline HTML page (Web Crypto for hashing, no network — same PWA
gate rules from FIX-07) + `olive-verify` CLI; renders R1's cover semantics from the
recipient's perspective ("what this file proves to *you*").
**Effort:** M. **Risks/deps:** EXP-07 format; must be brutally clear that hash-valid ≠
placement-valid (the E1 over-promise risk the research roadmap flags). **Excellence
bar:** verification is one drag-and-drop with three plain-language outcomes; the
verifier itself passes the browser privacy gates.

---

## H3 — Transformative bets

### EXP-14 · Multi-sensor honest-evidence platform (vibration first)
**Pitch:** Generalize the architecture — derived-scalar pipeline, no-raw-data gate,
honest report — into a sensor framework, starting with an accelerometer for structural
noise (upstairs stomping, bass transmission) that microphones fundamentally
mis-measure.
**Impact:** Airborne dBFS is the wrong instrument for the most common apartment
complaint class (impact noise travels structurally). A second sensor would also prove
the architecture *is* a pattern, not a one-off: `run_pipeline`'s
frame → scalar → detector → store shape (`monitor/service.py`) is already
sensor-agnostic in everything but naming.
**Shape:** extract a `Reading` abstraction over `(t, level)`; per-sensor detector
configs and per-sensor no-raw-data budgets (FIX-13 per channel); report renders
channels side-by-side with per-channel limitations. Hardware: any cheap I²C
accelerometer.
**Effort:** XL. **Risks/deps:** real hardware validation (real-data gate); vibration
metrics have their own standards rabbit hole (honestly present as relative, exactly
like uncalibrated dBFS); do not start before FIX-01/02/03 stabilize the data model.
**Excellence bar:** adding a third sensor type touches no core pipeline code; each
channel's report section states its own can/cannot-prove list.

### EXP-15 · Optional on-device ML acoustic tagging (ethics-gated, out of core)
**Pitch:** An opt-in `[ml]` extra using a small on-device audio classifier (YAMNet-
class) to replace the single-feature ZCR tag with a hedged label+confidence — computed
in memory, only the label persisted.
**Impact:** The current tag (`monitor/features.py`, one ZCR threshold, never validated
against a real bark) is the weakest honest component. A real classifier would make the
hint useful — but it also sharpens the core ethical tension: a "bark 0.93" label reads
like source attribution, which ROADMAP §3 lists under *Won't (ever)* as a claim the
tool must not make. This idea might be **correctly rejected**; the work includes
finding that out.
**Shape:** ethics review *first* (does a confidence-scored label cross the
no-source-attribution line even with hedging? does it change how adjudicators read the
record?); if it proceeds: isolated extra (like `[live]`), embeddings never persisted
(FIX-13 budget), R9's export-suppression on by default for adjudication artifacts,
labeled-session eval with real audio (real-data gate) before any default-on.
**Effort:** L–XL. **Risks/deps:** ethics gate is genuinely blocking; adds the first
heavyweight dependency anywhere in the project; misuse risk (over-reading) is the
worst-misuse scenario in `docs/RESPONSIBLE-TECH-AUDITS.md` §A. **Excellence bar:** a
committed ethics-review artifact with a real decision — including, possibly, "no."

### EXP-16 · Consent-based civic noise aggregation (separate tool, heavily gated)
**Pitch:** A *separate* opt-in tool that consumes exported bundles from many
households (airport/freeway/venue noise campaigns) and produces aggregate,
privacy-preserving neighborhood evidence — the civic-scale version of "evidence, not
vibes."
**Impact:** Connects this personal tool to the portfolio's civic-tech spine: community
noise disputes suffer the same he-said-she-said dynamic at 1000× scale, and honest,
level-only, locally-owned records are a genuinely novel input to that fight.
**Shape:** never the monitor egressing — the monitor's no-egress gate is untouchable;
a distinct aggregator repo ingesting EXP-07 interchange files that residents export
deliberately; aggregation with disclosed methodology (and a no-verdict rollup at
neighborhood scale); governance/consent design *before* code.
**Effort:** XL. **Risks/deps:** ethics + legal + community-governance review (human
gates, all blocking); temporal noise data can be re-identifying — DP or coarse
aggregation analysis required (SME gate); realistically a new repo, not a feature.
**Excellence bar:** a published governance doc a privacy advocate (persona P8) would
endorse; individual households provably non-recoverable from any published aggregate.
