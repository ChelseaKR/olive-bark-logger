# Contributing

This is a personal, single-maintainer project, but the process below is the same one a
new contributor would follow, and it's what CI enforces.

## Ground rules
- Read `docs/ROADMAP.md` first — it's the build spec and the source of the project's
  hard guardrails (never persist or transmit audio; the report must state its
  methodology and limitations honestly; local-only operation).
- This repo inherits [`/STANDARDS`](../STANDARDS/); see the README's
  [Standards Conformance table](./README.md#standards-conformance) for what applies and
  what's still a tracked gap (`docs/GAP-LEDGER.md`).
- Never weaken `tests/test_no_audio.py`, `tests/test_no_egress.py`, or
  `tests/test_report_content.py` — these are the project's merge-blocking safety
  guarantees. A PR that touches them needs an explicit callout in its description of
  why, not just a diff.

## Prerequisites
`make dev` creates `.venv` from the committed `uv.lock` and installs the `dev` dependency
group (pytest, ruff, mypy, bandit, pip-audit, hypothesis). Install
[uv](https://docs.astral.sh/uv/getting-started/installation/) first; the lock is the
single dependency snapshot used by local, CI, and release verification. One tool is
**not** on PyPI and needs a separate install:

- **gitleaks** (secret scanning): `brew install gitleaks` (macOS) or see
  <https://github.com/gitleaks/gitleaks#installing>. Required for `make security` /
  `make verify` to pass locally — CI runs it either way via `gitleaks-action`, but the
  local gate hard-fails without it (no more silent skipping, see `Makefile`).
- **Node.js 20+**: needed for `make pwa-test` and the pa11y/axe pass in `make a11y`.
- **uvx** (workflow static analysis): ships with `uv`, so installing uv covers it.
  `make workflows` runs `uvx --from zizmor==<pinned> zizmor` over `.github/workflows/`,
  which fetches zizmor on first use and then serves it from uv's cache. The version is
  pinned in the `Makefile` (`ZIZMOR_VERSION`) so the verdict cannot change without a
  commit. Offline mode is the default and is what CI runs, so no token is needed.
- **Docker**: only needed for `docker build .` / the container smoke test; not required
  for the Python test suite.
- **veraPDF** (optional, PDF/A-3a conformance validation): a Java tool, not a
  PyPI package — <https://verapdf.org/software/>. Only used by the best-effort,
  non-merge-blocking `make pdf-a11y` target; `tests/test_pdf_export.py`'s structural
  pytest gate is the enforced floor for the tagged-PDF export (EXP-06). See
  `docs/adr/0004-weasyprint-for-tagged-pdf-a-export.md`.

### Git hooks (`.pre-commit-config.yaml`)
`pre-commit` itself comes from the `dev` group, so `make dev` installs it. Installing the
hooks into your clone is optional and recommended, not the enforcement mechanism:

```bash
.venv/bin/pre-commit install                      # fast commit-time checks
.venv/bin/pre-commit install --hook-type pre-push # strict mypy before push
```

The enforcement mechanism is `make hooks`, which runs the same committed config over
**every tracked file** and is a prerequisite of `make verify` and a step in CI. Until
2026-09-05 nothing ran that config anywhere, so the whitespace, end-of-file, YAML-syntax,
line-ending and large-file hooks gated only the clones that had opted in
([GAP-CQ-1](./docs/GAP-LEDGER.md#gap-cq-1--code-quality-python-floor-pre-commit-hook-wiring-src-layout-hatchling)).

Two of the config's hooks do **not** run under `make hooks`, and the `hooks` recipe in
the `Makefile` is the single place that says so:

- **gitleaks** is skipped (`SKIP=gitleaks`). Its upstream entry is `gitleaks protect
  --staged`, which reads the *staged* diff — empty under `--all-files` and empty in a CI
  checkout, so it would report success without scanning anything. Secrets are scanned for
  real by `make security` (`gitleaks detect`) locally and by `gitleaks-action` over the
  PR's whole commit range in CI. Installing the commit-time hook is still worth doing: at
  commit time there *is* a staged diff for it to read.
- **mypy** is `stages: [pre-push]`, so it does not run at the commit stage `make hooks`
  uses. It is bare `mypy` against this repo's own configuration — exactly what `make type`
  runs, from the locked mypy rather than a second, unpinned copy.

### The optional `pdf` extra (tagged PDF/A export, EXP-06)
`pip install -e '.[pdf]'` adds `weasyprint` (and `pypdf`, used only by
`tests/test_pdf_export.py` to read the generated structure tree back out). This
extra needs a **Python >=3.10** host interpreter — a further, deliberate, scoped
divergence from the project's >=3.9 core floor (ADR-0002), documented in
`pyproject.toml` and `docs/adr/0004-weasyprint-for-tagged-pdf-a-export.md`. It is
never installed by `make dev` / `make verify`, mirroring the `live` extra: nothing
on the core monitoring/report path depends on it. `tests/test_pdf_export.py` skips
itself cleanly (`pytest.importorskip`) when the extra isn't installed.

## Workflow
```bash
make dev        # one-time setup
make verify     # lint, pre-commit hooks, workflow static analysis, type-check, coverage (>=85%), security, a11y, PWA tests, i18n gate
```
### Local/CI parity

This is the authoritative statement of how `make verify` and CI differ; `.github/workflows/ci.yml`
and the rest of this file point here rather than restating it.

`make verify` runs nine targets: `lint hooks workflows type cov security a11y pwa-test i18n`.
CI invokes
**six** of them as the Makefile target itself, so those cannot drift: `make lint`,
`make hooks`, `make workflows`, `make type`, `make i18n`, `make pwa-test`. The other
**three** run as separate CI steps:

| Target | How CI runs it instead | Why |
| --- | --- | --- |
| `cov` | `pytest --cov --cov-fail-under=85` in the `test-matrix` job | Same flags and the same 85% floor, run once per supported Python (3.9–3.13) rather than once locally. |
| `security` | `bandit` and `pip-audit` as steps, plus `gitleaks-action` | The Makefile's `security` expects a `gitleaks` CLI on `PATH`; CI runs gitleaks as a container action, so the target cannot be called as-is. |
| `a11y` | `scripts/demo_report.py`, then `pa11y` on `report.html` and again on `pwa/index.html` | CI additionally scans the PWA page, and excludes axe's `color-contrast` rule on the report (axe cannot resolve SVG `<text>` backgrounds; `tests/test_svg_contrast.py` is the merge-blocking replacement). `ci.yml`'s own comments carry the detail. |

Beyond `verify`, CI also runs things no local target does at all: the OS × Python
compatibility matrix, the container build and Trivy scan, the tagged-PDF structural tests,
and the two self-checks (`scripts/check_ruleset.py`, `scripts/check_nightly_macos.py`) that
`make ruleset-check` / `make nightly-check` run locally only on demand, because they need
network and `gh` auth.

`.github/workflows/codeql.yml` is outside `verify` in the other direction: it analyses the
same workflow surface `make workflows` does, but it uploads its result to code scanning
instead of failing a job, so it reports rather than gates. `make workflows` is the enforced
floor there. Making CodeQL blocking is a required-check decision recorded in
`docs/GAP-LEDGER.md`.

`tests/test_doc_figures.py` derives that six/three split from `ci.yml` and the `Makefile`,
so this table fails a build if either side changes. It previously said there was "the one
place" the two disagree and pointed at `docs/GAP-LEDGER.md#gap-cicd-1`, an entry about the
branch ruleset that never mentions parity.

1. Open a PR against `main` (direct pushes bypass every gate below — see
   `.github/rulesets/main.json` for the intended enforcement, and
   `docs/adr/0001-single-maintainer-review-posture.md` for why a solo maintainer still
   opens PRs instead of pushing straight to `main`).
2. Fill in `.github/PULL_REQUEST_TEMPLATE.md`, including the "regenerated dated
   artifacts if template/threshold changed" line if you touched the report template,
   the a11y walkthrough's subject matter, or anything in `docs/audits/`.
3. `make verify` must pass locally before you open the PR; CI re-runs the equivalent
   gates plus the extras listed under [Local/CI parity](#localci-parity) above.
4. Update `CHANGELOG.md` under `[Unreleased]`.
5. If your change is an expensive-to-reverse decision (a new dependency, a schema
   change, declaring something N/A, changing the Python floor), write an ADR under
   `docs/adr/` — see `docs/adr/0000-record-architecture-decisions.md`.

## Code style
- Formatting/linting: `ruff format` + `ruff check` (`make fmt` / `make lint`); the
  select set is `E, W, F, I, UP, B, SIM, S, C90, RUF` — see `pyproject.toml`.
- Types: `mypy --strict` (`make type`); the only opt-out is `monitor/capture_live.py`
  (hardware-dependent, documented in `pyproject.toml`).
- Tests: `pytest` with `--strict-markers --strict-config` (`make test` / `make cov`);
  coverage floor is 85% branch coverage.
