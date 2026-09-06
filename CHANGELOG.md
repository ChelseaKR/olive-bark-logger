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

### Fixed
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

### Added
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
