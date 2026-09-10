# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project uses
[SemVer](https://semver.org/) once it makes its first tagged release.

**No version of this project has been tagged or released yet.** `pyproject.toml` and
`monitor/__init__.py` (via `importlib.metadata`) carry an in-development version number
(`0.1.0.dev0`) — that is a development milestone, not a release claim, and the PEP 440
`.dev0` suffix says so in a form a tool reads rather than only a reader. Everything below lives
under `[Unreleased]` until a `git tag` actually exists; see `docs/GAP-LEDGER.md#gap-rel-1`
for the release-pipeline gap and `CITATION.cff` for the corrected (un-dated) citation
metadata. Do not add a dated `## [0.1.0] - YYYY-MM-DD` heading here until `v0.1.0` (or
whatever version supersedes it) is actually tagged — that was the exact "phantom
release" defect this file's absence let stand.

## [Unreleased]

### Added
- **`olive-bundle`: a tamper-evident evidence bundle, and a verifier that can fail.** The
  research roadmap's E1 is the item every adjudicator persona raised -- a property manager
  or a board will not weigh a log the other party could have edited -- and
  `docs/audits/residual-risk.md` row 1 accepts tampering as unmitigated. A manifest turns
  "trust me" into "check it", offline and with no network step anywhere.

  `olive-bundle build --db olive.db --out bundle/` writes a consistent SQLite snapshot
  (through SQLite's own backup API, not a byte copy of a database being written to), the
  report, both CSV exports, the quiet-hours HTML, the session ledger, the calibration
  history, and `manifest.json`: tool version, schema version, the config in force, the
  SHA-256 and byte count of every other file, and a plain-language block. That block
  carries verbatim the sentence the roadmap flags as the over-promise to avoid -- a hash
  proves the files have not been edited since the bundle was made, and proves nothing
  about how the device was placed or tuned before it.

  `olive-bundle verify bundle/` gives three answers and only three, and **unverifiable is
  a real answer**: a bundle whose manifest is gone has not been shown to be intact and has
  not been shown to be modified, and a verifier that resolves that ambiguity in either
  direction is worse than no verifier. Exit codes follow `scripts/check_ruleset.py` -- 0
  intact, 1 modified, 2 "I could not tell". **The inventory is closed**, so a file *added*
  to a bundle is a finding and not only one that changed; an open inventory lets anything
  be dropped into a bundle that still reads as intact, which is most of the point of
  having one.

  Three smaller decisions, each with its reason in the source:
  - **The artifacts are produced by `report.render.main`, not re-rendered.** A bundle
    containing a second implementation's idea of the report would be evidence of nothing.
  - **`--created-at` is both the manifest's timestamp and the report's "generated at"
    line**, so it is the only value that moves between two builds over one database. Two
    bundles made with the same `--created-at` are byte-identical, and a test asserts it.
  - **The no-audio guarantee is checked at the inventory level**, by extension *and* by
    magic bytes, because a bundle is the one artifact that packages files by inventory
    rather than one at a time.

  `sessions.csv` and `calibration.csv` carry the same R1 cover block as every other
  export. They are discovered by `tests/test_export_caveats.py`'s behavioural half and
  added to its checked set, so they are under the existing gate rather than beside it --
  and an empty calibration history is written as a header with no rows, because "this
  device was never calibrated" is a fact the recipient needs and a missing file states
  nothing.

  **Signing is not here, and the reason is recorded rather than left as an omission.**
  Every candidate (`ssh-keygen -Y`, minisign) is a subprocess; `tests/gates.py` forbids
  importing `subprocess` anywhere in `monitor/`, `store/` or `report/`, and `make
  security` runs bandit over the same tree, which reports it at LOW severity and fails.
  This repository carries no `# nosec` suppression anywhere, and adding the first one
  inside a feature is how a security gate erodes. So the format reserves
  `manifest.json.sig` and the verifier *detects* a signature it cannot check, answering
  **unverifiable** -- never intact, and never treating it as though the bundle had no
  signature at all, which would let a forgery read as an honest unsigned bundle.

- **`olive-forget`: erase a time range, and disclose the erasure as a gap.** A
  privacy-first tool needs a privacy verb. A guest's visit, a family argument, a medical
  episode -- an operator may reasonably not want any trace of a window in a file they are
  about to hand to a landlord, and until now the only two options were to keep it or to
  edit the SQLite file by hand. The second is the worse one, because it destroys the
  record's honesty in silence: the hours come back as an ordinary quiet night with nothing
  saying otherwise.

  So erasure is an operation and what it leaves behind is a `gaps` row with reason
  `erased`, carrying the operator's words. That is the whole design: every reader that
  already understands "the device was not listening here" understands it with no new
  arithmetic. The coverage sentence subtracts it, the calendar hatches those hours as not
  monitored, the CSV's `monitored` column reads `no`, and the report gains a *Windows
  erased by the operator* section naming the window and the reason -- or "no reason given",
  which is not the same as saying nothing. An erased night can never read as quiet.

  `EventStore.forget` removes events, ambient minutes, clock anomalies, drift advisories
  and any gap lying wholly inside the window, by **overlap** rather than containment, since
  a row straddling the boundary still carries measurement from inside. Capture sessions and
  calibration history are kept and the reason is written down: they are lineage for the rows
  that remain, not measurements of any moment. `--dry-run` counts without deleting; without
  `--yes` the command prints the counts and requires the word `erase`.

  Two things are load-bearing rather than incidental. The erasure row is written **in the
  same transaction as the deletes**, because a crash between them produces exactly the
  hole-with-nothing-disclosing-it that hand-editing produces; a test drives that with a real
  SQLite abort and requires every deleted row to come back. And a `--from`/`--to` value with
  no time of day in it is refused by name, even though `datetime.fromisoformat` reads it
  happily as midnight -- accepting it would round the operator's window outward to a whole
  day and erase more than they asked for.

  Schema 9 to 10. Admitting a fourth gap reason meant a **table rebuild**: the permitted
  values live in a column `CHECK` and SQLite has no statement that adds one, so the twelve-step
  procedure is followed inside an explicit `BEGIN`/`COMMIT`. That pair is not decoration:
  `executescript` runs its statements in autocommit mode, so without it an interruption
  between `DROP TABLE` and `RENAME` would leave a database with no `gaps` table at all --
  the ledger that discloses missing time, itself missing.

- **The browser edition can erase a window too, and discloses it the same way.** The PWA
  half of the verb above. Until now the page's only removal control was **Clear events**,
  which emptied the whole IndexedDB store -- events, gaps and session records together --
  and left nothing at all behind. That is the silent hand-edit `olive-forget` exists so
  that nobody has to make, in the implementation with the lowest barrier to reaching for
  it: the record loses the hours *and* loses the fact that it ever had them, and what gets
  handed to a landlord afterwards reads as a device that was simply never running then.

  **Erase a window** takes a start, an end and an optional reason, states what it is about
  to destroy before it destroys it, and leaves behind a gap record with `reason: "erased"`.
  Everything downstream already understood that shape: coverage subtracts the window, the
  calendar hatches its hours as *not monitored*, the quiet-hours CSV names it in the gap
  list, and the report gains the same *Windows erased by the operator* section the Python
  report has -- or `no reason given`, which is not the same as saying nothing. The delete
  and the disclosure share one IndexedDB transaction, so a tab closed between them cannot
  leave the hole without the row that discloses it.

  **Erase everything recorded** replaces *Clear events* and is the same operation over the
  whole observed window. Session records survive it, deliberately and for the Python side's
  reason: they are what keeps the erased hours in the coverage denominator instead of
  removing them from the record's own idea of what it covered. The page says plainly that
  clearing the site's data in the browser is the way to leave no record at all, including
  the disclosure -- the browser's equivalent of deleting the `.db` file.

  `pwa/report.js`'s selection rule (`willForget`) is ported predicate-for-predicate from
  `EventStore.forget`: events by overlap, a gap only if it lies wholly inside, sessions
  kept, and an earlier erasure row never erased -- removing the disclosure of an erasure is
  the one deletion this design exists to prevent. The heading is shared with the Python
  report and pinned across the two; the note is deliberately *not* verbatim, because the
  Python wording names `olive-forget` and "the device", and copying it into a browser tab
  would make the disclosure a false statement about how the erasure happened. The two
  sentences that are the claim itself are pinned in both directions.

### Fixed
- **The file that lists the two ports' deliberate divergences was missing two of them, and
  one of them moves a number.** `spec/SEMANTICS.md` has an "Intentional Python ↔ PWA
  differences" section precisely so a divergence is a decision rather than a thing that
  happened. Its detector half is held by golden vectors both suites replay and its cover
  half by `spec/report/cover.json`. Its **report-structure** half was held by nothing:

  - **`monitor.config.QuietSchedule` holds a tuple of windows with minute granularity and a
    per-weekday `days` set; `pwa/report.js`'s `summarize` takes one wrapping whole-hour pair
    and `pwa/index.html` offers two whole-hour inputs and no weekday control.** A
    Tuesdays-only rule, a 22:30 start, or a second window in one day are questions the Pi
    report answers and the browser cannot be asked — so over identical events the two ports
    give different quiet-hours counts. This is the one divergence on the list that changes a
    figure rather than a layout.
  - **The `Quiet-hours duration rollup` exists only in Python.** The browser report has
    quiet-hours *counts* and no per-day accumulated-duration figure anywhere. PR #117's own
    body calls that table "the exhibit an ordinance's per-day duration figure is actually
    read from".

  Both are now written down, along with the four other port-only sections that had never
  been stated (`Measurement conditions`, `Ambient baseline`, `Threshold sensitivity`, `Why
  there is deliberately no audio`, and the `Distributions` ↔ `Events by hour of day` /
  `Events by day` rename).

  `tests/test_port_divergence.py` keeps it that way: it extracts every `<h2>` each port can
  emit — resolving `{CONSTANT}` on the Python side and `${esc(CONST)}` on the browser side —
  and compares both against a declared map, so a section added to one port and not the other
  fails until somebody says which it is. Every declared port-only heading is separately
  asserted to be genuinely absent from the other port, so an entry cannot outlive the
  divergence it names; and a floor asserts both extractors still find at least eight
  sections, because two extractors that have stopped matching look exactly like two ports in
  perfect agreement.

  **Porting either divergence is an owner call, and neither is done here.** The rollup rests
  on the schedule model — its fourth cell state exists only because a schedule can leave a
  weekday out.
- **The browser report's calendar had a row only for the days that had an event, so a day
  the app was never opened and a genuinely quiet day were both simply absent from it.**
  Issue #59 fixed exactly this on the Python side, on the reasoning that "a quiet
  monitored day and a day the monitor was switched off both simply vanished from the
  calendar". `pwa/report.js` is the browser twin of that same report and never learned:
  `summarize` built `byDayHour` from `partsInTz(ev.start)` as it walked the events, so
  the grid's rows *were* the event days. On this side the outage it hides is the
  commonest one there is, because a gap row is written by a *running* app catching its
  own coverage hole: a closed tab, a locked device, an app never opened that day leaves
  no gap behind at all, and only the hole between two session records can find it.
  - The calendar now has a row for every day the reporting window covers, and the
    calendar's three states are rendered: a count, a `0` (a monitored hour with no event
    is a measurement), and `not monitored` for an hour nothing was listening for. An
    unmonitored cell prints no count at all, not even a zero, and is in neither the row
    total nor the shading scale.
  - The third state does not depend on colour: a text dash in the cell, the label spelled
    out in the cell's title, and each day's count of unmonitored hours as a real column
    with its own header. Same rule `report/charts.py` follows for the same cell.
  - `UNMONITORED_LABEL` is exported and a test holds it equal to `report/charts.py`'s
    `_UNMON_LABEL`, so the two halves of one report cannot describe one absence with two
    different words.
  - `offAirSpans` returns `null`, not an empty list and not the whole window, for a
    record with no session rows: "the record cannot say" is neither "fully covered" nor
    "entirely off air", and the calendar marks nothing rather than inventing an outage.
  - `windowDays` walks calendar dates rather than adding 86400 seconds, so a
    daylight-saving transition inside the window cannot skip a day or emit one twice.
  - An empty record now says there is no window to draw a calendar over, rather than
    "no events have been logged yet", which was a claim about events in a place the
    absence might equally be of monitoring.
- **The quiet-hours duration rollup listed only the days that had loud time in it, so a
  night with no monitor running vanished from the table an ordinance's per-day figure is
  read from.** Issue #59 gave the calendar heatmap a row for every day the reporting
  window covers, because "a quiet monitored day and a day the monitor was switched off
  both simply vanished from the calendar". The per-day duration rollup, rendered ten
  lines away in `build_report` over the same days, kept iterating
  `quiet_hours_loud_seconds_by_day` — the days that *had* a number. Measured on a
  three-night log with 2026-03-11 entirely off air: the calendar showed four day rows
  with 03-11 hatched `not monitored`, and the rollup listed two days, 03-11 not among
  them. With no quiet-hours event anywhere in that log the table did not render at all
  and the section read "No events fell within the quiet-hours window, so there is
  nothing to roll up" — a statement about what was observed, from a report that observed
  none of that night.
  - The rollup now has a row for every day the window covers, with the calendar's three
    states: a measured duration (`0 s` included — a monitored night with no loud time is
    a finding), `not monitored` where the record shows no monitor running for the whole
    of that day's quiet hours, and a duration plus how many of the day's quiet hours are
    missing from it where the night was only partly covered.
  - `report/charts.py`'s `_UNMON_LABEL` is now the public `UNMONITORED_LABEL` and both
    per-day surfaces render that one string, so the two cannot describe the same absence
    differently. The PWA's cross-implementation check reads that constant out of
    `report/charts.py` by name; it now accepts either name and still fails if the two
    sides render different *text*, because the binding is to the string and a rename is
    not the two halves of one report disagreeing.
  - A fourth cell state, reachable from any weekday-restricted schedule
    (`QuietWindow.days` — a Tuesdays-only HOA rule is an ordinary one): a day the
    schedule gives no quiet window at all says so. `0 s` there would measure nothing and
    `not monitored` would be false, since the device may well have been listening.
  - The prose fallback is narrowed, not removed: a record showing full coverage and no
    quiet-hours loud time still says there is nothing to roll up, because there is not.
  - `tests/test_absence_as_value.py` gains the case as item 4 and pins all four states;
    the golden snapshot carries the new note.
- **The tagged-PDF negative control was pinned to one report length, and the rollup fix
  above turned it into a no-op.** The control in `tests/test_pdf_export.py` named
  `test_the_caption_keep_together_rule_is_the_one_doing_the_work` removed
  `caption { break-after: avoid }` from `_PDF_LAYOUT_STYLE` and required WeasyPrint's
  "Table wrapper without a table" crash to come back on the report at exactly its own
  length. Which lengths crash is a fact about where a table lands on a page, not about
  the rule: `report/pdf_export.py`'s own measurement has the unfixed code crashing at 0,
  1, 5 and 20 filler paragraphs and *passing* at 60. Measured on CI, adding one table to
  the report moved 0, 1, 5, 20 **and** 60 out of the crashing shape together — the
  control reported `DID NOT RAISE`, and a five-length version of it would have gone
  quietly green instead. It now searches every whole-paragraph offset up to a full extra
  page (`CONTROL_SWEEP`) for a length where removing the rule brings the crash back,
  stops at the first hit, and then asserts that same length converts with the rule
  restored — which is the only positive assertion at a length where the rule is
  demonstrably doing work. Its failure message says that widening the sweep, not
  deleting the control, is the response if no length crashes.
  `make verify` cannot see any of this: the `pdf` extra needs a >=3.10 host and
  `weasyprint` needs system Pango, so the whole file `importorskip`s on a 3.9 dev venv
  and only CI's "Install pdf extra" step runs it — which is why the rollup commit's local
  gate was green and CI's was not.
- **`docs/GAP-LEDGER.md` listed two supply-chain items as absent that had been in the
  tree for eight weeks.** GAP-SEC-1 said "no SBOM/signing (no release pipeline exists to
  attach them to)". The parenthesis was the error: `.github/workflows/release.yml` landed
  in the 2026-07-10 conformance pass and GAP-REL-1 in the same file records it. Its
  `build` job generates a CycloneDX SBOM from the installed wheel (SEC-27) and attests
  build provenance for the wheel, the sdist and the SBOM through keyless OIDC (SEC-29).
  Neither has fired, because no `v*` tag exists — "built but never run" is a weaker claim
  than "shipped" and a much stronger one than "absent", and the entry was making the
  wrong one of the three. Corrected in place with the superseded sentence quoted beside
  it, and the still-open list rewritten to what is actually missing: `egress-policy:
  block`, CodeQL over the Python code, a TruffleHog history scan (with a note that
  `--only-verified` cannot fail on an already-revoked credential), and OpenSSF Scorecard.
- **`make verify` and CI ran different `pip-audit` commands, and the document that exists
  to list every such difference did not mention it.** `make security` passes
  `PIP_AUDIT_WAIVERS` (twelve `--ignore-vuln` flags); `ci.yml`'s "Dependency audit" step
  passes none. Measured on the committed dev venv: bare `pip-audit` reports **12 known
  vulnerabilities in 7 packages**, and the same run with the waivers reports **none, 12
  ignored**. Neither command is wrong — the waivers are an accommodation for the
  documented `>=3.9` floor (CQ-01), under which no fix version installs, while CI runs
  3.12 where `uv.lock` resolves the fixed versions, so CI is *fixed, not waived* and is
  deliberately the stricter side. The defect was that `CONTRIBUTING.md`, which calls
  itself "the authoritative statement of how `make verify` and CI differ", explained only
  the gitleaks difference in its `security` row — so a contributor reading it was told
  the two gates otherwise agree, and a green `make verify` looked like a prediction of a
  green CI. The row now names the divergence and gives the command that reproduces CI's
  run locally (`make security PIP_AUDIT_WAIVERS=`), `ci.yml` says why the waivers are
  kept out of it, and `tests/test_doc_figures.py` compares the two argument lists and
  fails if they differ while the parity section is silent — including if they are ever
  made to agree and the sentence is left behind.
- **`check_ruleset.py` compared `bypass_actors` by equality, which is the one comparison
  that cannot see a lockout.** Recording the owner's standing bypass in
  `.github/rulesets/main.json` (2026-08-27) fixed the claim but not the check. Two wrong
  values that agree still passed: a later "tidy" of the committed file back to `[]`, on a
  day the owner had also lost the bypass live, would have reported a match on precisely
  the incident that field protects. `bypass_findings` now holds the live ruleset and the
  committed file **independently** against the owner's bypass and compares only *other*
  actors between them, so a second bypass granted to a team, an app or another role is
  still a finding in either direction. The committed file is checked as something that
  will be *applied*, not only as a description of what is live, because
  `.github/rulesets/README.md` publishes `gh api --method PUT ... --input
  .github/rulesets/main.json` as the drift-correction step — following that while the
  file said `[]` is how the owner gets locked out of her own repository, which has
  happened before and took a sweep across eighteen repositories to undo. That command now
  carries a warning to check the field first, and
  `tests/test_ruleset_check.py::test_both_sides_emptied_is_still_a_failure` pins the case
  equality got wrong: two findings, not zero.
- **The service worker's precache was all-or-nothing, and silently so** (issue #68).
  `caches.open(CACHE).then((c) => c.addAll(ASSETS))` stores nothing at all if any single
  one of the eight asset fetches fails, per the Cache API spec, and surfaced no error
  anywhere. Everything #65/#66/#67 established about *which* files belong in `ASSETS`
  rested on an install path that could quietly store none of them, so a client hitting a
  transient hiccup on the exact visit meant to fix its offline reload stayed broken until
  some later visit where all eight happened to succeed at once. Assets are now cached
  individually via `Promise.allSettled`, which keeps whatever succeeded (Cache Storage
  outlives a discarded worker, so the next attempt only fetches what is still missing),
  and the install is **rejected** if any failed, so the browser retries later instead of
  activating a worker whose cache cannot serve an offline reload. A partial precache
  reporting success is the same defect class as a green check that cannot fail.
- **The precache-completeness test's import regex was not anchored to import syntax**
  (issue #68). `/from\s+["'](\.\/[^"']+)["']/g` matched the bare word `from` followed by
  a quoted relative path anywhere in `app.js`, so a comment such as
  `// ported from "./legacy.js"` would have been collected as an import and the test
  would then have demanded `sw.js` precache a module `app.js` never imports — a
  false-failure trap inside a test written to prevent false negatives. Against a
  three-line fixture with one real import, the old pattern returned three specifiers and
  the anchored one returns one. Both the binding/re-export form and the side-effect form
  (`import "./x.js";`) are recognised, multi-line import lists still match, and the
  pattern was duplicated in three places and is now one helper.
- **The markdown link gate read a code span as a link.** `tests/test_doc_links.py`
  matched `[...](...)` wherever those characters occurred, backticks included, where
  Markdown renders no link at all. The changelog entry directly above quotes the regex
  issue #68 was about; that quote contains a character class immediately followed by a
  group, and the gate demanded the repository add a file named after the fragment. A
  truthful sentence could not pass, and the cheap way out was to reword the document
  rather than fix the check -- the same false-failure shape as the unanchored import
  regex, in the gate rather than in the code. Code spans are now stripped before the
  scan; stripping rather than skipping the line keeps the target of a code-labelled
  link (``[`monitor/features.py`](../monitor/features.py)``, the house style here)
  checked, and a canary pins both halves.

- **The tagging feature buffer grew without limit through any quiet stretch**
  (issue #63). `run_pipeline` kept `(timestamp, zero-crossing-rate)` pairs so a closing
  event could be classified over its own window, and its comment claimed the buffer
  "never holds more than one event's worth of frame features". The only prune sat inside
  `if event is not None:`, so a night, a weekend away, or any span with nothing crossing
  the threshold never pruned at all: one entry per frame, forever. Traced over 5000
  quiet frames the buffer reached exactly 5000 entries; at the default 100 ms frame that
  is ~864,000 a day, on a Raspberry Pi meant to run for weeks under `Restart=always`.
  The operators it bit were the ones with the quietest installs. The buffer is now
  `monitor.features.FeatureWindow`, a deque pruned **every frame** against
  `Detector.active_since` -- the open event's start, or None when nothing is open -- so
  the bound is the detector's own state rather than a guessed retention horizon, and is
  amortized O(1) rather than a per-frame rebuild that would make a long event quadratic
  in its own length. Same 5000-frame trace now peaks at 1. Classification is unchanged:
  a tag computed after a 500-frame quiet stretch is identical to one computed without it.
- **The cover block did not lead every artifact, and the gate that promised it could not
  see the one it missed.** The README's Guardrails section said the "what this can and
  cannot prove" cover block "leads **every artifact** either implementation produces" and
  that "the gate discovers export paths from source, so a new one cannot ship without
  them", under a heading that reads "Enforced by merge-blocking tests, not just promised".
  `report/status.py`'s `render_status` is a fifth artifact path — it builds the
  `status.html` the README tells the operator to double-click open, and it prints two
  quiet-hours counts — and it carried neither the cover block nor the no-verdict line for
  as long as it existed. It could not: its only import from `report.render` was `_STYLE`
  and the span helpers. `tests/test_export_caveats.py` missed it because discovery was **by
  name**, and `render_status` matches none of `PY_EXPORT_PATTERN`'s three alternatives —
  the exact failure mode that file's own docstring names ("a gate that checks the paths
  someone remembered to name"). Fixed by closing the hole rather than softening the
  sentence: `status.html` now emits the shared `cover_html()` above its first table and the
  shared `NO_VERDICT_NOTE` beside its quiet-hours counts, and discovery is now **by
  behaviour** — a public function in `report/` that builds a whole HTML document
  (`<!DOCTYPE html` in its own body) or writes a CSV (`csv.writer`) is an export path
  whatever it is called. The old name pattern is kept as a union member, so discovery can
  only widen; `test_the_name_half_of_discovery_is_never_narrowed` pins that. Verified by
  planting `paint_ops_dashboard`, a name the old pattern demonstrably does not match: two
  gates go red on it, and both go red again if the cover or the no-verdict line is removed
  from the status page.
- **Documentation figures, links, and citations that had drifted, now derived instead of
  typed.** `docs/RESPONSIBLE-TECH-AUDITS.md` §F said "**ten** dev-toolchain-only CVEs are
  waived … **All ten** are in `pip-audit`'s own transitive dependencies"; the Makefile has
  **12**, and one of the two 2026-08-21 additions is setuptools, a venv seed package rather
  than a pip-audit dependency. The same file said "artifacts are committed and regenerated
  by `make verify`"; `verify` is `lint type cov security a11y pwa-test i18n`, `snapshot` is
  not in it, and the only artifact `a11y` writes is the gitignored `report.html` — `verify`
  *checks* the committed artifacts, it does not regenerate them, and **RTF-08 remains
  open**. Three README links into `docs/GAP-LEDGER.md` carried anchors left behind when two
  headings were shortened, and `.github/workflows/ci.yml` cited the WeasyPrint ADR under
  its pre-rename `0003-` filename for a month after `7fe55bb` moved it to
  `docs/adr/0004-weasyprint-for-tagged-pdf-a-export.md`, which every other reference in the
  tree already used. `CONTRIBUTING.md` pointed at `GAP-CICD-1` for "the one place CI and the
  Makefile still don't call identical commands" — an entry about the branch ruleset that
  never mentions parity, and there are three such places, not one; `ci.yml` cited two
  documents for "the exact local/CI parity statement" in which the word parity does not
  appear. `docs/GAP-LEDGER.md`'s own "Last verified" stamp said 2026-08-15 over entries
  dated through 2026-08-27. `docs/DOCUMENTATION-AUDIT.md` said "3 ADRs" (four existed at its
  own commit, five now) and "33 Python/Node test files; 1 workflow file" (48 and 3).
  Two new merge-blocking gates close the hole these all sat in: `tests/test_doc_links.py`
  resolves every markdown link, anchor, and in-repo path citation in every tracked file,
  and `tests/test_doc_figures.py` derives every stated count from the tree. `PROJECT-SCOPE`'s
  "37 hand-authored doc or metadata files" is deliberately left ungated and labelled as a
  point-in-time figure: its own definition has no mechanical equivalent here, so any number
  asserted for it would be invented.
- **The README's supported-versions line presupposed a release that does not exist.** It
  read "only the latest `0.y` release receives fixes" while `CHANGELOG.md`, `CITATION.cff`
  (no `date-released`) and `GAP-REL-1` all record that no `v*` tag has ever been cut — the
  "phantom release" defect this file exists to prevent. It now states that no version has
  been tagged, then gives the policy for when one is.
- **`bypass_actors: []` was false: an administrator can bypass every rule, always.** A
  `RepositoryRole:5 / always` bypass actor was added to this repository (and every
  repository in this portfolio) so the owner can always recover a wedged gate.
  `.github/rulesets/main.json` still recorded `bypass_actors: []`,
  `.github/rulesets/README.md` said "**No bypass actors.** No one — including the
  repository owner — merges past these rules", and the README's Standards Conformance
  table said "no bypass actors". All three described a stricter gate than the one in
  force. `make ruleset-check` named it in one line
  (`bypass_actors: committed [] (no one bypasses), live ['RepositoryRole:5 (always)']`)
  and the same API read returned `"current_user_can_bypass": "always"`.
  **The file was amended to reality; the live ruleset was not touched and the owner's
  bypass stays.** `tests/test_ruleset_check.py` now fails if the committed definition
  stops recording the actor, if the live ruleset loses it, if a second bypass actor
  appears, or if any document goes back to claiming nobody can bypass. Worth carrying
  forward: the one field that turned out wrong is the one field CI structurally cannot
  read — `verify` runs `--scope public` and the public ruleset payload omits
  `bypass_actors` entirely, so `make ruleset-check` with a maintainer token is the only
  check on it.
- **`nightly.yml`'s header described a job that was deleted.** It said "ci.yml's
  same-named twin job keeps the ruleset-required macos contexts green on PRs" — that
  twin was `test-matrix-macos-nightly-notice`, removed on 2026-08-26 along with the five
  contexts it faked. Replaced with what is actually true: the sweep is merge-blocking
  indirectly and with a lag, through `verify`'s `check_nightly_macos.py` step.
- **The browser edition's quiet-hours export never said how much of the window it
  observed** (issue #64). Issue #39 established that a quiet-hours document is only
  honest with a coverage figure -- an outage during quiet hours removes events, so a
  device that dropped out for most of the night produces a low count that reads as a
  quiet night -- and `report/violations.py` has carried monitored-vs-wall-clock hours
  ever since. `pwa/` never received the equivalent, while `pwa/README.md` made the same
  "honest ... submission" claim about the same kind of file. A reader got
  `Monitoring gaps: 1 recorded, totalling 37s` with no denominator anywhere: 37 seconds
  out of a half-hour test, or out of a ten-hour night, are not the same document.
  Every browser export path -- quiet-hours CSV, event CSV and report HTML -- now leads
  with the coverage block, and the same ten-hour example now reads *"the device monitored
  2.0 of 10.0 wall-clock hours (20%); the remaining 8.0 hours are shown as not monitored
  rather than quiet."*
- **The browser's on-screen event counter counted monitoring gaps as events.**
  `refresh()` displayed `allEvents().length`, which includes gap records, so the number
  on screen disagreed with every number in every export. It now counts detected events.
- **Five of the eleven required status checks on `main` were satisfied by an `echo`.**
  The `protect-main` ruleset required `test-matrix (macos-latest, 3.9–3.13)` to merge.
  Nothing on a pull request ran macOS; what reported those five contexts was
  `test-matrix-macos-nightly-notice` in `ci.yml`, a job that renamed itself to the five
  context names and whose entire body was one `echo`. The live API for `ci.yml` run
  32648677865 on `main`: `labels: ["ubuntu-latest"]`, three steps, four seconds,
  `conclusion: success`, every time. The ruleset read as eleven checks and enforced six.
  The five contexts are removed from `.github/rulesets/main.json` **and from the live
  ruleset**, and the notice job is deleted with no stand-in — a required context whose
  job cannot fail is worse than an absent one, because it reads as coverage.
- **The nightly macOS sweep now has consequences.** CI-CD-STANDARD §11b forbids
  `macos-*` runners on PR CI, so no honest per-PR macOS gate exists here. New
  `scripts/check_nightly_macos.py` (`make nightly-check`) fails unless the nightly sweep
  ran on `main`, on runners the API labels `macos-*`, within 7 days, and passed — the
  runner-label assertion being the specific defence against a repeat. It runs as a step
  inside the already-required `verify` job, so it gained teeth without adding a required
  check name. It is a **lagging** gate and says so on every run, pass or fail: a
  macOS-only regression still merges, then blocks every merge after the next nightly
  catches it.
- **`make ruleset-check` existed, was correct, could fail, and ran nowhere.** A PR that
  rewrote `.github/rulesets/main.json` merged green, because nothing compared the file
  to the live ruleset except a human choosing to run the command. It now runs inside
  `verify` as `scripts/check_ruleset.py --scope public`.
- **`check_ruleset.py` reported a pass from a field it had never read.** The rulesets
  endpoint answers any caller on a public repository, but the reduced payload omits
  `bypass_actors` entirely; `.get("bypass_actors", [])` turned that omission into
  "[] — no one bypasses". An absent field is now `CANNOT VERIFY` under `--scope full`,
  and the new `--scope public` (what CI uses, since the Actions `GITHUB_TOKEN` cannot be
  granted `administration`) prints "NOT CHECKED in this run: bypass actors" on the
  passing path as well as the failing one. The same pass added comparison of the
  `pull_request` rule's parameters, which had never been diffed at all:
  `require_code_owner_review` flipping to `false` live was invisible.
- **PWA offline precache includes `./clock.js`** (fixes #65). `pwa/sw.js` previously
  omitted `./clock.js` from `ASSETS`, breaking full offline functionality when
  `app.js` imported `computeAnchor` and `toEpochSeconds`. Added a regression test
  in `pwa/clock.test.mjs` ensuring all local modules statically imported by
  `app.js` are present in `sw.js` precache assets.
- **The #65 regression test itself checked the whole file, not the precache list.**
  It asserted an imported module's path appeared anywhere in `sw.js`'s source text,
  so a stray comment mentioning the same string (rather than a real `ASSETS` entry)
  would have made it pass while the module stayed genuinely missing from the
  precache. It now extracts and checks membership in `ASSETS` specifically, with two
  canary tests (against a synthetic fixture, not the real files) proving it actually
  fails on both a real omission and a decoy mention outside the array.
- **The note beside the quiet-hours duration rollup explained two of the four things the
  table can say.** `ROLLUP_ABSENCE_NOTE` is the only explanation a reader gets for that
  table, and it was written for the two states the rollup had when #117 gave it a row per
  day: a measured duration and `not monitored`. Two more states landed with it and after
  it — a partly-covered night (`0 s (1 of 10 quiet hours not monitored)`) and a day the
  schedule gives no quiet window at all (`no quiet-hours window this day`) — and both are
  precisely the cells that are *not* durations, so the two hardest cells to read were the
  two the paragraph beside them did not mention. Worse, its headline sentence was wrong
  for the fourth: a day with no quiet window does not "show a measured zero".

  The note is now the concatenation of one sentence per state (`ROLLUP_STATE_SENTENCES`)
  rather than a paragraph written beside them, and `RollupCell` carries the `state` it is
  in — `measured` could not, because it collapses three different absences into one flag.
  `test_the_note_beside_the_rollup_explains_every_state_the_table_can_render` holds the
  two together in both directions: every state `_rollup_cells` reaches has a sentence, and
  every sentence belongs to a state some fixture reaches, so neither a new state with no
  explanation nor an explanation for a state that is gone can sit there quietly.

  Found alongside it: `test_rollup_names_the_unmonitored_night_instead_of_reporting_nothing`
  compared the note against the page as **raw** text. The note is written through
  `html.escape`, so the first apostrophe added to it turned that assertion into one that
  could never match. It now compares `escape(ROLLUP_ABSENCE_NOTE)`, which is the string the
  reader actually receives.

### Added
- **The tagged-PDF gate was passing on how long the report happened to be**
  (issue #116). `tests/test_pdf_export.py` was green on `main`, and that was a
  coincidence of how much prose sat above a table. Appending filler paragraphs to
  the report before conversion, changing nothing else, moved the verdict around at
  random: 0 extra paragraphs crashed, 5 crashed, 20 crashed, 60 passed. Every
  failure was the `ValueError: Table wrapper without a table` ADR 0004 already
  documents, so the next person to add a sentence to the report would have been
  handed a red gate and a stack trace pointing into WeasyPrint.

  The mechanism is narrower than the original bisection concluded. WeasyPrint wraps
  a `<table>` together with its `<caption>` in one table-wrapper box; when the
  caption fits at the foot of a page and the body does not, the fragment left
  behind is a wrapper holding a caption and no table. The existing mitigation
  removed the other routes to a bad layout but never stopped a caption being
  separated from its table. One rule fixes it — `caption { break-after: avoid }` in
  `_PDF_LAYOUT_STYLE` — and the same sweep then passes at 0, 1, 5, 20 and 60 extra
  paragraphs.

  `test_the_tagged_pdf_survives_a_longer_report` parametrizes over those lengths so
  the property is pinned rather than the fixture, and
  `test_the_caption_keep_together_rule_is_the_one_doing_the_work` removes the rule
  in-process and asserts the crash returns: without that control a future edit
  could drop the rule and every other test in the file would stay green until
  someone added a paragraph. ADR 0004 carries the measurement.
- **An advisory calibration-drift watch** (issue #100, EXP-04). A microphone in a window
  for a season does not stay where it was put, and nothing in the record said so: the
  configured threshold kept reading the same while the meaning of "loud" underneath it
  moved, so weeks of counts silently stopped being comparable. `monitor/drift.py`
  compares the recent ambient baseline (median and L90, from the opt-in EXP-01 minute
  ledger) against the window right after the current calibration epoch. Past
  `drift_tolerance_db` — 5 dB by default, and documented as an order-of-magnitude
  judgement rather than a measured distribution — it records a `drift_advisories` row,
  publishes the state in the heartbeat JSON, shows it on `status.html`, and discloses it
  in the report's *Measurement conditions* block with the check to run:
  re-run `olive-calibrate`.

  **Advisory means advisory.** No detection parameter, threshold or offset is changed by
  any of it, and a test asserts that running the watch leaves every event and every
  minute row byte-identical. `docs/adr/0030-advisory-drift-watch-never-adaptive-detection.md`
  records why adaptive re-tuning was rejected: detection is frozen per session on purpose
  (ADR 0019), and a threshold that moves on its own would make two nights incomparable
  invisibly, which is the one thing this record exists to prevent.

  The watch has three states, not two, because "the baseline has not moved" and "the
  baseline could not be compared" are different facts. A disabled ambient ledger (the
  default), no calibration epoch, an empty window, or a calibration so recent that the
  two windows would overlap each produce **unavailable**, with the reason printed, on
  every surface. With the ledger off the report says in terms `Drift watch unavailable:
  ambient ledger not enabled`, followed by the sentence that an unavailable watch is not
  a steady one. `tests/test_drift.py` asserts that distinction at the comparison, the
  heartbeat, the status page and the report, and the report recomputes the state from the
  stored minutes rather than reading the advisory table, because an empty table means
  either "checked and steady" or "never checked" and only the recomputation can tell
  them apart.

  Schema v9 adds `drift_advisories`. It is inside the derived-data budget rather than an
  increase to it: the only signal-derived numbers in a row are differences of two
  `minute_levels` aggregates that are already declared, and
  `tests/test_privacy_budget.py` now asserts exactly that, so a later edit cannot
  introduce a new per-minute quantity under cover of an advisory. Retention reaches the
  new table (`prune`, `PRUNED_TABLES`), so advisories cannot outlive the minutes that
  justify them.
- **A threshold-sensitivity section in the report** (issue #99, EXP-03). The strongest
  attack on a level-only record is "you picked the threshold that flatters you". The
  report now answers it before it is asked: `report/sensitivity.py` recounts the record at
  ±3 and ±6 dB from the configured threshold, offline and deterministically, from data
  already stored — per-event peaks and the ambient ledger's per-minute maxima (EXP-01).
  On by default; `olive-report --sensitivity off` omits the section.
  **The headline counts never move**, and `tests/test_sensitivity.py` asserts that every
  byte outside the section is unchanged when it is added.
  Three things the exhibit refuses to state as measurements, because the stored record
  cannot support them:
  - **Below the configured threshold the event column is a floor, not a count.** An event
    that never crossed the threshold was never written down, so no count of stored events
    can say how many a lower threshold would have found. The number that *is* derivable
    there — the events already recorded, every one of which clears any lower threshold —
    equals the headline exactly, on every log, and a flat column in a sensitivity table
    reads as "insensitive". It renders as "at least N (not recorded)" instead, and the
    ambient ledger, which can answer downward, carries the signal.
  - **With no ambient ledger the section says so**, rather than rendering a table of zeros
    (which claims the threshold was tested) or vanishing (which leaves a reader unable to
    tell an untested threshold from one that held).
  - **The recount runs on the raw dBFS scale detection used**, not the calibrated scale the
    report shows a reader: `threshold_dbfs` is defined against the stored scale and
    calibration is a render-time offset (ADR-0003), so adjusting one side of the comparison
    would move every row. A test plants a +12 dB calibration and fails if it leaks in.
  Shipping the code does **not** close EXP-03's acoustics-SME wording review; that human
  gate stays open in `docs/ideation/04-impact-and-sequencing.md`, and a test fails if the
  row is removed.

- **Static analysis of the workflows themselves** (issue #84, GAP-CICD-1 / CICD-19,
  CICD-20). `make workflows` runs zizmor over `.github/workflows/`, is a prerequisite of
  `make verify`, and is a step in the required `verify` CI job, so the local and CI
  verdicts are the same command; the zizmor version is pinned in the `Makefile`, because
  a linter that floats to its newest release changes its verdict with no commit to blame.
  It runs *inside* `verify` rather than as a new required context, for the reason the
  2026-08-26 required-check removal recorded. `.github/workflows/codeql.yml` adds CodeQL
  over the same surface (`language: actions`) and is recorded as **reporting, not
  gating**: `codeql-action/analyze` fails only when the analysis errors, so a finding
  becomes a code-scanning alert while the job exits 0. Making it blocking changes the
  required-check list and is left as an explicit open decision rather than implied by the
  workflow's presence. `make workflows` also echoes what zizmor's default persona hides:
  that persona prints `No findings to report (N suppressed)`, and the count of what it
  suppressed is the part worth seeing — `make workflows-auditor` prints those in full.
  Four findings that were actionable were fixed rather than suppressed: two
  `template-injection` (the matrix Python version now reaches the shell through `env:`
  instead of being expanded into the `run:` text), two `undocumented-permissions`, and
  `release.yml`'s `publish-release` job was given a `name:`. The three that remain are
  informational `anonymous-definition` findings on `verify`, `test-matrix` and
  `test-matrix-macos`, and are left alone on purpose: a job's `name:` is its status-check
  context, so naming those renames six required checks and blocks every merge until the
  ruleset is edited to match.
- **The committed pre-commit hook set is now a gate** (issue #82, GAP-CQ-1 / CQ-12).
  `.pre-commit-config.yaml` had been in the tree since 2026-07-14 and ran nowhere except
  in a clone whose owner had happened to run `pre-commit install` — so its end-of-file,
  trailing-whitespace, YAML-syntax, line-ending and large-file hooks gated nothing that
  merged, for seven weeks, while the ledger recorded the mechanism as "added". A new
  `make hooks` target runs that same file over **every tracked file**, is a prerequisite
  of `make verify`, and is a step in the required `verify` CI job, so the two cannot
  drift (CICD-27). `pre-commit` joins the `dev` dependency group and `uv.lock`, rather
  than being fetched unpinned at CI time, because the lock is this repo's single
  dependency snapshot. Two of the config's hooks are named as *not* run by the gate
  instead of being left to look covered: **gitleaks**, whose upstream entry is `gitleaks
  protect --staged` and therefore reports success without scanning a byte when nothing
  is staged — which is every `--all-files` run and every CI checkout, the exact
  always-green-check shape removed from this repo twice already; and **mypy**, which the
  config stages at pre-push and which is bare `mypy` on this repo's own configuration,
  i.e. `make type`, already blocking in both gates. `SKIP` is set in one place, the
  `hooks` recipe, so neither caller can claim more than it runs.
- **Session records in the browser store** (`{kind: "session", start, end}`), which is
  what makes the coverage figure possible at all. The store previously held events and
  gaps only, and a gap is written by the *running* app on a `visibilitychange`, so the
  most ordinary outage of all -- the tab closed, the browser restarted, the laptop shut
  -- left no trace whatsoever; there was no data to compute coverage from even if the
  report had tried. Each run's end is checkpointed every 30 s, mirroring the Python
  monitor's `checkpoint_interval_s`. The residual error is one-directional and stated on
  every export: a tab killed outright ends its run at the last checkpoint, so up to 30
  seconds of real observation goes unclaimed. Under-claiming coverage is the safe
  direction. A record with no sessions at all falls back to window-minus-recorded-gaps
  and says, in the export, that it is doing so.
- **`spec/report/cover.json` gains a `coverage` object** -- heading, the
  not-monitored-is-not-quiet note, the undeterminable-coverage note, and the sentence
  template both ports format their own numbers into. Replayed by
  `tests/test_export_caveats.py` and `pwa/report.test.mjs`, so the wording cannot drift
  the way it did. The arithmetic is ported too: `coverageWindow` / `coverageHours` in
  `pwa/report.js` mirror `report/render.py`'s `_coverage_window`, `on_air_spans` and
  `_coverage_hours`.
- `Detector.active_since` -- the open event's start timestamp, or None. The only
  interior state the detector exposes, and the exact bound a caller holding per-frame
  side data needs.
- `pwa/sw.test.mjs` — the service worker's install path **executed** rather than read,
  in a `node:vm` sandbox with a fake Cache API. The other PWA tests assert on `sw.js`
  as text, and text cannot tell you what `addAll` does on a partial failure. Includes a
  canary running the previous `addAll` implementation through the identical harness and
  showing it store zero of eight on one failure.

### Security
- **WeasyPrint 69.0 -> 70.0 for CVE-2026-55073, and the pin that was blocking it.** The
  `pdf` extra was capped at `weasyprint>=67,<70`, deliberately: ADR-0004 records the upper
  bound as a forcing function for a rendering review before a new browser-style major.
  `PYSEC-2026-3940` is fixed in **70.0 and in no earlier release**, so the cap had also
  become the thing excluding the only patched version. Widened to `<71`; the floor, and the
  reason for having a cap at all, are unchanged. `uv lock --upgrade-package weasyprint`
  moved exactly one entry -- 94 lock entries before and after, one version changed.

  **The advisory is about this project's own mechanism and does not reach it.**
  `url_fetcher` is how `report/pdf_export.py` enforces the local-only guarantee, and the
  advisory says two `write_pdf()` channels ignore it: `xmp_metadata=[url]` and
  `stylesheets=[...]`. **The call site passes neither** -- `pdf_variant` and `pdf_tags`
  only, over HTML this project generated itself, with no caller-supplied URL anywhere in
  the path. So this is hygiene and gate-correctness, not incident response, and the
  `Dependency audit` step is right to fail on the version regardless of reachability.

  Verified: full suite 625 passed / 1 skipped. `tests/test_pdf_export.py` -- the structural
  gate ADR-0004 relies on -- **could not be run on the machine this was written on**
  (WeasyPrint cannot import there: `cannot load library 'libgobject-2.0-0'`); it runs
  against 70.0 in the `verify` job, which installs the pango stack. No human
  assistive-technology or visual rendering pass was performed and none is claimed.

  **The cap did its job on the first run, and the finding is worth more than the bump.**
  With the bound widened, CI failed on
  `test_the_caption_keep_together_rule_is_the_one_doing_the_work` — the in-process negative
  control that removes `caption { break-after: avoid }` and requires the
  `Table wrapper without a table` crash to come back. On 70.0 it comes back at **none** of
  the 60 filler lengths. The control's own message named the two readings it cannot
  separate (dead code, or a sweep that stopped producing the crashing shape) and said not to
  delete it to get green; the upstream changelog separates them —
  [Kozea/WeasyPrint#2761](https://github.com/Kozea/WeasyPrint/issues/2761), titled
  `ValueError: Table wrapper without a table`, is closed and listed in 70.0 as "Handle split
  tables with captions". The workaround is inert because the bug is gone.

  The control is now version-split with **both halves assertive**: below 70 the crash must
  still return, at 70+ it must not, so a regression fails here rather than passing quietly,
  and the `>=70` branch keeps a positive conversion assertion so it cannot be satisfied by a
  fixture that stopped rendering. **The CSS rule stays** — the extra still admits `>=67`,
  where it is load-bearing; retiring it means raising the extra's lower bound, which is a
  separate decision.

- **`pypdf` 6.15.0 -> 6.16.2 in `uv.lock`** (CVE-2026-84309, CVE-2026-84310,
  CVE-2026-84311). The `pdf` extra pins `pypdf>=5,<7`, so no constraint changed; only
  the locked version moved, past the 6.16.0/6.16.1 fix versions the advisories name.
  Unlike the twelve entries in the Makefile's `PIP_AUDIT_WAIVERS`, this one is a real
  runtime dependency of a shipped code path (`report/pdf_export.py` reads the generated
  PDF's structure tree back out for `tests/test_pdf_export.py`), so it is fixed rather
  than waived. CI's `Dependency audit` step -- which runs bare `pip-audit`, without the
  Makefile's waivers -- went red on `main` and on every open branch the moment the
  advisories published; this is the whole of that failure.

### Changed
- **The coverage sentence has one definition, and the generator that publishes it is
  now checked against what it published.** The claim both editions make -- *"the device
  monitored X of Y wall-clock hours (Z%); the remaining N hours are shown as not
  monitored rather than quiet"* -- existed three times: an f-string in
  `report/violations.py`, a template literal in `pwa/report.js`, and a hand-maintained
  copy in `spec/report/cover.json`. The two suites compared the *rendered* sentence
  against the vector, which caught a reworded sentence but not the arrangement that let
  it happen. It is now `COVERAGE_SENTENCE_TEMPLATE` in `report/violations.py`;
  `scripts/gen_cover_spec.py` imports that constant and builds the whole vector from it;
  `pwa/report.js` holds the shape once, as its own `COVERAGE_SENTENCE_TEMPLATE`, and
  formats its numbers into it (an unfilled placeholder now throws rather than shipping a
  literal `{wall}` to a reader as though it were a measurement).
- **`spec/report/cover.json` is gated against its generator.** The generator wrote the
  file and nothing read it back, so the vector had drifted into a superset of what
  `scripts/gen_cover_spec.py` produced: running it would have silently deleted the entire
  `coverage` block that ten assertions across both suites replay.
  `tests/test_export_caveats.py` now fails unless the committed JSON is byte-identical to
  `render()`, in either direction -- a Python constant changed without regenerating, or
  the JSON edited by hand into something no constant says. The gate reads only; it never
  regenerates, because a gate that repairs drift is how the file stopped being reviewed.
  A second gate reads the generator's own source and requires each shared string to be an
  imported name rather than a literal, with canaries proving both bite: the planted
  violation is a literal *identical* to the real constant, which is exactly what a
  value-comparison gate cannot see.
- `_coverage_sentence` no longer defaults `unmonitored_hours` to `0.0` with `or`. The
  branch it sits on has already established that `monitored_hours` and `wall_clock_hours`
  are both set, which is the only condition under which the property returns `None`, so
  the figure is guaranteed and the invariant is now stated as a raise. The default was
  wrong in the one case it could ever have fired: it would have printed "0.0 hours not
  monitored" for hours nothing measured, and an unmeasured figure is never shown as a
  number here -- a record that cannot support one gets `COVERAGE_UNKNOWN_NOTE` instead.
- **The live branch ruleset and the committed definition now match** (maintainer
  decision, 2026-08-21). Live `protect-main` was brought up to
  `.github/rulesets/main.json` for the `pull_request` rule (approvals 0 per ADR-0001,
  stale-review dismissal, thread resolution, code-owner routing), strict required
  status checks (stale branches cannot merge), and `bypass_actors: []` (the
  maintainer's former `pull_request` bypass is gone — no one merges past the checks).
  `main.json` was amended the other way for one rule: `required_signatures` is dropped
  with a reasoned note in `.github/rulesets/README.md` — commits here are routinely
  made by delegated agents without commit signing configured, so the rule would reject
  every push; release tags are signed elsewhere in the portfolio, and commit signing
  remains a separate future decision. The file also takes the live ruleset's name.
  `make ruleset-check` exits 0 against the live API, and
  `tests/test_ruleset_check.py` pins recorded before/after fixtures so both the
  historical divergence and the reconciled state stay tested offline.
- The README standards-conformance table now declares all fifteen standards.
  Performance, Incident Response, Data Governance, and AI Development
  Measurement were absent from it, so none of the four was recorded as met, as
  exempt, or as a gap. Performance, Incident Response, and AI Development
  Measurement are declared as applying with open gaps and no committed
  artifact; Data Governance points at the existing
  `docs/audits/data-card.md`.
- Rows that pointed at `docs/GAP-LEDGER.md` said "gap tracked in GAP-NN". The
  phrase reads as a reference to an issue tracker, and this repository
  deliberately keeps gaps in a committed ledger instead (the reason is in the
  paragraph above the table). Those rows now say "open gap recorded in
  GAP-NN", which is what the link actually resolves to. No gap changed state.

### Fixed
- **The status page's "No monitoring gaps recorded" implied full coverage even when
  the monitor had not been running at all.** A monitoring-gap row (`store.Gap`) is
  written only by a *running* monitor catching its own source failure, so the
  commonest outage of all — the monitor simply not running, after a stop, a crash, or
  a power cut — leaves no gap row to find. `report/status.py`'s "Monitoring gaps"
  section only ever queried that ledger, so a status page generated after the monitor
  stopped and never restarted showed "No monitoring gaps recorded in this window"
  next to "Events: 0", reading as a fully-monitored quiet night. The main report's
  calendar heatmap and the violations export's off-air section already draw this
  distinction from the capture-session ledger (`report.render.on_air_spans`); the
  status page now does too, in its own "Time the monitor was not running" section,
  scoped to the page's own reporting window (a session that ended before the window
  began correctly reads as off-air for the whole window, not clipped away to
  nothing). Gated in `tests/test_status.py`.
- **The status page claimed 100% frame coverage before the monitor had read a single
  frame.** `CaptureStats.coverage` (monitor/health.py) returns `1.0` — a reasonable
  "nothing dropped" identity — when no frames have been seen or dropped yet, and
  `monitor/service.py` publishes the very first heartbeat before the capture loop reads
  its first frame. Every run's first `status.html` therefore showed "Frame coverage:
  100.0%" for a device that had not yet been asked for one. The main report's
  measurement-conditions paragraph already guarded this correctly (it omits the
  coverage sentence entirely when no frames have been counted); the status page's Live
  Capture table did not. It now reads "not yet started, no frames processed yet" until
  at least one frame has been seen or dropped. Gated in `tests/test_status.py`.
- **Three more places where "no data" rendered as a confident value.** (1) A log with
  no events printed "Loudest peak: 0.0 dBFS" — digital full scale, the loudest reading
  the device can produce — in both the Python report and the browser edition; those
  figures now read "no events". (2) When monitoring coverage could not be computed, the
  main report printed nothing where the coverage sentence goes, which reads as "the
  whole window was observed"; it now says coverage could not be determined, the way the
  quiet-hours export already did. (3) The calendar heatmap had rows only for days that
  had events, so a quiet monitored day and a day the monitor was switched off both
  simply vanished from the calendar; every calendar day in the reporting window now has
  a row, so a quiet day shows its zeros and an off-air day is hatched "not monitored".
  Gated in `tests/test_absence_as_value.py` and `pwa/report.test.mjs`; the snapshot
  golden gains the explicit coverage note.
- **Readings the first calibration postdates are now disclosed as such.** A
  timestamp before the first calibration epoch resolves to that epoch by design (epoch
  0 covers all historical rows, ADR-0003), so one `olive-calibrate` run on day 20 was
  applied to events from day 1 with no marker anywhere: the report said "Calibrated.",
  the multi-epoch caveat never fired (one epoch), and every export row carried the same
  offset whether or not it was in force when the row was measured. The numbers are
  unchanged; every artifact now says it. The calibration banner and the methodology line
  name how many events (and ambient-ledger minutes) were recorded before the first
  calibration and when it was taken, on the single-offset and multi-epoch paths alike;
  the violations HTML carries the same statement; and every CSV row and the violations
  table carry a `calibration_basis` of `in-force` or `back-applied` (`bootstrap-config`
  / `none` without a history; `unstated` if a caller supplies offsets without a basis,
  rather than guessing). The migration's epoch 0 at `effective_from = 0` is not reported
  this way — it genuinely covers everything and keeps its own legacy caveat. Gated in
  `tests/test_calibration_disclosure.py` on the issue's exact fixture through the real
  CLI. (#50)
- **`retention_days` now reaches every table it should, and says what it reached.**
  Retention deleted rows from `events` and nothing else, so the opt-in ambient minute
  ledger (`minute_levels`, EXP-01) — the one *continuous* dataset in the store, 1,440
  rows a day while enabled — was kept forever, along with every gap, clock anomaly,
  and session row older than the horizon, while the operator line said "pruned N
  event(s)". `EventStore.prune` now returns per-table counts and prunes events, ambient
  minutes, gaps that ended before the horizon, clock anomalies, and sessions whose last
  vouched-for moment is before it and that no retained row references.
  `calibration_history` is exempt by design (a few operator-entered offsets needed to
  interpret what is kept); `store.RETENTION_EXEMPT_TABLES` states each exemption's
  reason and `tests/test_retention.py` enumerates the live schema against the two
  lists so a new table cannot sit outside the policy unnoticed. The operator line
  names every table's count (the JSON form carries `pruned_by_table`), and the data
  card documents retention per table. `Session.last_vouched_at` is the single rule
  for a session's end, shared by retention and the coverage arithmetic.
- **The caveats now travel with every export path, in both implementations.** The
  "what this can and cannot prove" cover block leads the browser edition's report HTML
  and both of its CSV downloads (`pwa/report.js`), and the Python event CSV
  (`--csv`), none of which carried it. The browser quiet-hours report also gains the
  no-verdict line ("being within quiet hours is not the same as a violation, and only
  the relevant authority can decide whether a rule was broken") and states that its
  readings are uncalibrated; its quiet-hours CSV preamble names the recorded monitoring
  gaps. In the CSVs the block is a leading `#` comment preamble, so the data rows below
  it still parse.
- The required strings are now one shared vector, `spec/report/cover.json`, replayed
  against both implementations (`tests/test_export_caveats.py`, `pwa/report.test.mjs`) —
  the same arrangement `spec/detector/*.json` uses for the two detectors, which is why
  the detectors never drifted and the report content did. The gate also *discovers*
  export paths from source and fails when the discovered set is not the checked set, so
  a new export path cannot ship without its caveats.
- **The docs now describe the branch ruleset that is actually live.** A ruleset
  (`protect-main`, id 18752850) has been active on `main` since 2026-07-09;
  `.github/rulesets/README.md`, the README's CI/CD row, and `GAP-CICD-1` all said it had
  never been applied, and that every merge-blocking gate in `ci.yml` was therefore
  "advisory only". They now state what is enforced (deletion, non-fast-forward, and
  eleven required checks — five of which are the always-green macOS twin, so the real
  strength is six) and enumerate the four ways the live ruleset is weaker than the
  committed `main.json`: `strict_required_status_checks_policy` false,
  `required_signatures` absent, the `pull_request` rule absent, and one bypass actor
  where the file says `[]`. The earlier changelog line describing a "committed (not yet
  applied) branch ruleset" was accurate when written and is superseded by this one.
- **The documented verification step can now see the live configuration.**
  `gh api .../rulesets --jq '.[] | select(.name=="main")'` selected on a name the live
  ruleset does not have, so it printed nothing and exited 0 — permanently reporting
  "not applied" whether or not a ruleset existed. Replaced by `make ruleset-check`
  (`scripts/check_ruleset.py`), which selects the ruleset covering `refs/heads/main` by
  target rather than name, prints every difference, and exits 1 on a difference or 2
  with `CANNOT VERIFY` when `gh` is missing, unauthenticated, or erroring. No path
  exits 0 without having read the live configuration. Not part of `make verify`, which
  may not assume network access or a `gh` token.
- **Two documents described gaps the code had already closed.** `README.md` called
  opt-in `--log-format json` "not implemented yet" and "planned" in two places; it
  shipped 2026-07-14 (`9a8dd4b`, #31) and the README was edited twice afterwards
  without catching it. `GAP-A11Y-1`'s headline clause said `pwa/index.html` was never
  scanned by pa11y/axe; CI has run `npx pa11y --runner axe ./pwa/index.html` on every
  push and PR since 2026-07-11 (`8858c45`, #17), in the required `verify` job. Both
  corrected, and the rest of GAP-A11Y-1 — no Lighthouse, stale walkthrough, no manual
  PWA pass, no ACR/VPAT, no NVDA/iOS VoiceOver — deliberately left open, because an
  automated scan is not a human walkthrough.
- `docs/a11y/STATEMENT.md`, the canonical accessibility declaration, carried the same
  stale "never scanned" claim in two places and is corrected with it.
- **The ledger is now readable by a test.** `tests/test_gap_ledger.py` pairs each
  closed-gap claim with the code fact that closed it (does `monitor/log.py` implement
  the JSON emitter; does `ci.yml` scan `pwa/index.html`) and fails when any document
  still describes it as open. Each check fires only while the capability is genuinely
  present, so removing a feature relaxes the check rather than breaking it.
- **Monitoring coverage no longer counts time when no monitor was running.** The
  coverage figure was the reporting span minus the recorded gap ledger, and a gap row is
  only ever written by a *running* monitor catching its own audio-source failure
  (`resilient_source`, reason `device-error`). The most ordinary outage there is — the
  monitor simply not running, after a stop, a reboot, a crash, or a power cut — writes
  no gap row at all, so every hour of it was counted as monitored. A log of two runs
  with eight hours off air between them reported "the device monitored 9.5 of 9.5
  wall-clock hours (100%)", in green, in the document the README points at for a
  neighbor/landlord/HOA submission. Coverage is now derived from the capture-session
  ledger, which does record those hours as the hole between one session's end and the
  next one's start: the same log now reports 2.0 of 10.0 hours (20%), lists the off-air
  stretch with its bounds and length under a new "Time the monitor was not running"
  heading in both the HTML and the CSV preamble, and hatches those hours as *not
  monitored* in the calendar heatmap (a third state that was previously reachable only
  from a `device-error` gap). A log with no capture sessions at all cannot support the
  claim in either direction, so it keeps the old whole-span-minus-gaps figure and says
  in writing that it is the most generous reading the record allows. Also fixed in the
  same arithmetic: two *overlapping* recorded gaps were subtracted twice, understating
  coverage. Gated in `tests/test_report_content.py`.

- The quiet-hours violation report (`--violations-html`, `--violations-csv`, and the
  `--violations-pdf` rendered from the same HTML) now states **how much of the window
  the device actually monitored**, in the Summary block above the counts: monitored vs
  wall-clock hours, every recorded monitoring gap with its bounds and length, and the
  `monitored` flag per event row that until now only the CSV carried. Hours that were
  not monitored are reported as not monitored, not quiet. The figure is declared an
  upper bound (an interruption the monitor never recorded cannot appear in it), and a
  record that cannot support the figure at all says coverage could not be determined
  rather than omitting it. The document the README points at for a neighbor/landlord/HOA
  submission previously printed counts with nothing about the time they were counted
  over, so an outage during quiet hours read as a quiet night. Gated in
  `tests/test_report_content.py`, which now covers the violations renderer too.

- Release authorization now runs from reviewed `main` through the immutable
  portfolio authorizer, builds the exact verified commit, and hands only
  distributions, SBOM, and notes to a checkout-free publisher that rechecks
  the tag object.

### Added
- `--version` on all four CLI entrypoints (`olive-monitor`, `olive-report`,
  `olive-calibrate`, `olive-tune`), backed by the existing single-source-of-truth
  `monitor.__version__` (REL-02). Prints and exits before touching any config, device,
  or database, so it works even with no `--config` and no hardware attached.
- `--log-format json` (and a matching `log_format` config field) emits the
  monitor's operator lines as newline-delimited JSON for a log shipper, using
  only the standard library (`monitor/log.py`). `text` stays the default and is
  byte-for-byte the previous output. Implements GAP-OBS-1 / control OBS-22.

### Changed
- `--csv` and `--violations-csv` gain a `calibration_basis` column after
  `calibration_offset_db`; the violations HTML table gains the matching "Offset basis"
  column. Existing columns are unchanged and keep their order.
- `--csv` (`report/export.py`) and the browser CSV downloads now begin with the `#`
  cover preamble. Data rows are unchanged; readers that do not skip `#` comment lines
  need a one-line filter.
- Development, CI, and tag verification now install from a committed `uv.lock` with
  `uv sync --locked`; `.python-version` preserves the accepted Python 3.9 device target,
  and the PDF-only dependencies carry explicit Python 3.10+ markers so the universal
  lock remains honest about that optional feature's runtime floor.

### Added
- Tag-triggered release workflow (`.github/workflows/release.yml`, REL-14, STANDARDS
  conformance remediation 2026-07-10): re-runs `make verify` at the tagged commit, then
  builds sdist + wheel, generates a CycloneDX SBOM, attests build provenance (keyless
  OIDC, no stored signing key), and publishes a GitHub Release with the matching
  `CHANGELOG.md` section as notes. Prepared ahead of the first tag — see the workflow
  file's header for what's deliberately still out of scope (PyPI, GHCR, cosign) and
  `docs/GAP-LEDGER.md#gap-rel-1` for the remaining release-pipeline gap.
- **EXP-06: optional tagged PDF/A-3a export** (`report/pdf_export.py`,
  `docs/adr/0004-weasyprint-for-tagged-pdf-a-export.md`). New `pdf` extra
  (`weasyprint>=67,<70`, needs Python >=3.10); new `--pdf` / `--violations-pdf` CLI
  flags on `olive-report`; `tests/test_pdf_export.py` verifies structural
  properties (tag tree, `/Lang`, heading order, table header association, chart
  descriptive text). **Not** a PDF/UA conformance claim — no human
  assistive-technology walkthrough has been performed yet (tracked:
  `docs/GAP-LEDGER.md#gap-a11y-2`).
- **Append-only calibration history (schema v3, FIX-01 / ADR-0003):**
  `calibration_history` table (`effective_from`, `offset`, `note`,
  `reference_instrument`); `olive-calibrate` is the only production writer and gains
  `--reference-instrument` provenance; the v2→v3 migration preserves a legacy
  calibration row as epoch 0. Reports spanning a recalibration disclose a per-epoch
  offsets table. A `schema_migrations` table records when each migration ran — the v3
  timestamp is the boundary between rows that may carry a baked-in offset and raw rows.
- CSV exports (`--csv`, `--violations-csv`) gain a per-row `calibration_offset_db`
  column recording the offset included in that row's levels (raw = value − offset); the
  violations HTML gains the same column and an honest multi-epoch calibration statement.
- Calendar heatmap and quiet-hours violation CSV/HTML export in the report (day×hour
  grid, `--violations-csv` / `--violations-html`).
- MIT `LICENSE` and `CITATION.cff`.
- `i18n` N/A declaration and enforcement gate (`docs/I18N.md`, `make i18n`).
- Renovate-managed GitHub Actions digest pinning (`renovate.json`).
- STANDARDS conformance remediation pass (2026-07-05): README Standards Conformance
  table; `CODEOWNERS` + committed (not yet applied) branch ruleset; `make verify` now
  runs the security gate for real instead of soft-skipping; expanded ruff rule set
  (`W`, `S`, `C90`, `RUF`) and strict pytest flags; PEP 735 `[dependency-groups]`;
  derived `__version__` via `importlib.metadata`; `SECURITY.md`, `CONTRIBUTING.md`,
  `DEFINITION_OF_DONE.md`, `docs/adr/`, `docs/GAP-LEDGER.md`,
  `docs/a11y/STATEMENT.md`; digest-pinned + healthchecked `Dockerfile`; container CVE
  scan (Trivy) and `harden-runner` (audit mode) in CI.

### Fixed
- **Calibration clobber (critical, data integrity; FIX-01 / ADR-0003):**
  `olive-monitor` no longer overwrites the stored calibration with the config value on
  every start (`olive-calibrate` → `olive-monitor` with a default config used to
  silently revert the device to uncalibrated). Event levels are now stored as **raw**
  dBFS and calibration is applied at render time from the append-only history —
  identically for the HTML report and the `--csv` / `--violations-csv` /
  `--violations-html` exports (exports previously emitted unadjusted levels, and the
  violations report's calibrated/uncalibrated statement came from the deprecated config
  field instead of the store). `config.calibration_offset` / `calibration_note` are
  bootstrap-only (deprecated); `threshold_dbfs` is defined against the raw stored
  scale. Legacy-data impact and recovery arithmetic: ADR-0003.
- `on-device only, no cloud, no telemetry` guarantees unchanged and still merge-blocking
  (`tests/test_no_audio.py`, `tests/test_no_egress.py`) — this remediation pass
  deliberately did not touch those tests' assertions.
- Removed a hidden failure-swallowing bug in `Makefile`'s `security` target: the old
  `tool && run || echo "skipping"` pattern silently converted a **real** `pip-audit`
  finding into a "not installed, skipping" message whenever the tool actually was
  installed and found something. `make security` now fails loudly instead.

### Security
- Dev toolchain: `pip` 26.1.2 -> 26.2.1 in `uv.lock` for PYSEC-2026-3721 (the
  Python >=3.10 resolution CI audits). The 3.9 resolution stays on 26.0.1 because
  26.2 dropped 3.9, so that ID and PYSEC-2026-3447 (`setuptools`, a venv seed package
  that is not a locked dependency) join the dated local-only waiver list in the
  `Makefile`, under the same "fix needs 3.10+" justification as the existing entries.
  Nothing here is shipped in the runtime, which has zero dependencies.
- GitHub Actions pinned to 40-character commit SHAs with Renovate digest-freshness
  automation (72h cooldown).
- `persist-credentials: false` on all checkout steps.

## Earlier history (pre-CHANGELOG, reconstructed from commit messages)
- Zero-dependency core (`monitor/`, `store/`, `report/`); no-audio and no-egress
  merge-blocking guarantees; accessible HTML report with methodology + limitations;
  Raspberry Pi systemd deployment; browser PWA variant; calibration and live-tuning
  CLIs; SQLite event store with WAL, schema versioning, and retention pruning.
