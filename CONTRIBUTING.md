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
`make dev` creates `.venv` and installs the `dev` dependency group (pytest, ruff, mypy,
bandit, pip-audit, hypothesis — all pinned with floors in `pyproject.toml`'s
`[dependency-groups]`). One tool is **not** on PyPI and needs a separate install:

- **gitleaks** (secret scanning): `brew install gitleaks` (macOS) or see
  <https://github.com/gitleaks/gitleaks#installing>. Required for `make security` /
  `make verify` to pass locally — CI runs it either way via `gitleaks-action`, but the
  local gate hard-fails without it (no more silent skipping, see `Makefile`).
- **Node.js 20+**: needed for `make pwa-test` and the pa11y/axe pass in `make a11y`.
- **Docker**: only needed for `docker build .` / the container smoke test; not required
  for the Python test suite.
- **veraPDF** (optional, PDF/A-3a conformance validation): a Java tool, not a
  PyPI package — <https://verapdf.org/software/>. Only used by the best-effort,
  non-merge-blocking `make pdf-a11y` target; `tests/test_pdf_export.py`'s structural
  pytest gate is the enforced floor for the tagged-PDF export (EXP-06). See
  `docs/adr/0003-weasyprint-for-tagged-pdf-a-export.md`.

### The optional `pdf` extra (tagged PDF/A export, EXP-06)
`pip install -e '.[pdf]'` adds `weasyprint` (and `pypdf`, used only by
`tests/test_pdf_export.py` to read the generated structure tree back out). This
extra needs a **Python >=3.10** host interpreter — a further, deliberate, scoped
divergence from the project's >=3.9 core floor (ADR-0002), documented in
`pyproject.toml` and `docs/adr/0003-weasyprint-for-tagged-pdf-a-export.md`. It is
never installed by `make dev` / `make verify`, mirroring the `live` extra: nothing
on the core monitoring/report path depends on it. `tests/test_pdf_export.py` skips
itself cleanly (`pytest.importorskip`) when the extra isn't installed.

## Workflow
```bash
make dev        # one-time setup
make verify     # lint, type-check, coverage (>=85%), security, a11y, PWA tests, i18n gate
```
`make verify` is the same gate set CI enforces (see the README's Quickstart section and
`docs/GAP-LEDGER.md#gap-cicd-1` for the one place CI and the Makefile still don't call
identical commands, and why).

1. Open a PR against `main` (direct pushes bypass every gate below — see
   `.github/rulesets/main.json` for the intended enforcement, and
   `docs/adr/0001-single-maintainer-review-posture.md` for why a solo maintainer still
   opens PRs instead of pushing straight to `main`).
2. Fill in `.github/PULL_REQUEST_TEMPLATE.md`, including the "regenerated dated
   artifacts if template/threshold changed" line if you touched the report template,
   the a11y walkthrough's subject matter, or anything in `docs/audits/`.
3. `make verify` must pass locally before you open the PR; CI re-runs the equivalent
   gates plus the full OS × Python compatibility matrix, container build + Trivy scan,
   and secret scanning.
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
