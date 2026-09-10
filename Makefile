# Olive's Bark Logger — developer entrypoints.
# `make verify` runs the full merge-blocking gate set locally, mirroring CI.

PY ?= .venv/bin/python
RUFF ?= .venv/bin/ruff
MYPY ?= .venv/bin/mypy
PRECOMMIT ?= .venv/bin/pre-commit
UV ?= uv
UVX ?= uvx
# Pinned, like every action SHA in .github/workflows/: a static-analysis gate that
# floats to the newest release changes its verdict without a commit, which is the
# failure mode `scripts/check_nightly_macos.py` was just rewritten to avoid.
ZIZMOR_VERSION ?= 1.29.0
ZIZMOR ?= $(UVX) --from zizmor==$(ZIZMOR_VERSION) zizmor

.PHONY: help venv dev fmt lint hooks workflows workflows-auditor type test cov security a11y snapshot doc-figures report pdf pdf-a11y pwa-test i18n ruleset-check nightly-check verify clean

help:
	@echo "Targets: dev fmt lint hooks workflows type test cov security a11y snapshot doc-figures report pdf pdf-a11y pwa-test ruleset-check nightly-check verify clean"

venv:
	@command -v $(UV) >/dev/null 2>&1 || { echo "uv not installed — see CONTRIBUTING.md#prerequisites"; exit 1; }
	$(UV) sync --locked --group dev

dev: venv
	@echo "Dev environment ready. Run 'make verify' to check all gates."

fmt:
	$(RUFF) format monitor store report tests scripts

lint:
	$(RUFF) check monitor store report tests scripts
	$(RUFF) format --check monitor store report tests scripts

# The committed pre-commit hook set (.pre-commit-config.yaml, CQ-12) run over every
# tracked file, not just the staged ones. That file has existed since 2026-07-14 and
# enforced nothing: the hooks fired only for a developer who had run `pre-commit
# install`, so end-of-file, trailing-whitespace, YAML-syntax, line-ending and
# large-file breakage could merge untouched. CI's `verify` job runs this same target,
# so local and CI cannot drift (CICD-27); see CONTRIBUTING.md's "Local/CI parity".
#
# SKIP names exactly one hook and is set here, in the single place both callers read,
# so neither can claim more than it runs. gitleaks' upstream hook entry is `gitleaks
# protect --staged`: it reads the staged diff, which is empty under `--all-files` and
# empty in a CI checkout, so it would report success without scanning a byte -- the
# always-green-check defect this repo has already removed twice (see
# .github/rulesets/README.md). Secrets are scanned for real by the `security` target's
# `gitleaks detect` here and by gitleaks-action in CI, over the whole commit range.
#
# The config's mypy hook is `stages: [pre-push]`, so it does not run at this stage
# either. It is bare `mypy` against this repo's own configuration -- exactly what
# the `type` target below runs, from the locked mypy rather than a second, unpinned copy.
hooks:
	@$(PY) -m pip show pre-commit >/dev/null 2>&1 || { echo "pre-commit not installed — run 'make dev' (dependency-groups: dev)"; exit 1; }
	SKIP=gitleaks $(PRECOMMIT) run --all-files --show-diff-on-failure

type:
	$(MYPY)

test:
	$(PY) -m pytest

cov:
	$(PY) -m pytest --cov --cov-report=term-missing --cov-fail-under=85

# Dated waiver (2026-07-05, recheck per SEC-40 cadence in docs/RESPONSIBLE-TECH-AUDITS.md
# §F): these CVEs are in pip-audit's own dev-toolchain dependencies (filelock/msgpack
# via CacheControl, pip, pytest, requests, urllib3) — never shipped in the runtime,
# which has zero dependencies (pyproject.toml). Every fix version requires Python
# >=3.10 (verified 2026-07-05 against the live index); this repo's dev venv targets
# the documented >=3.9 floor (pyproject.toml, CQ-01), so no fix is installable here
# yet. Re-audit when P1-5's Python-floor decision resolves, or drop entries as fixes
# ship for 3.9. Harmless no-op on hosts (e.g. CI's Python 3.12) where these IDs don't
# occur.
#
# 2026-08-21 additions, same shape: PYSEC-2026-3721 (pip <26.2) and PYSEC-2026-3447
# (setuptools <83.0.0). Both fixes require Python >=3.10 (verified with
# `uv pip install --dry-run --python .venv/bin/python` on the 3.9 venv: unsatisfiable).
# uv.lock carries pip 26.2.1 for >=3.10, so CI (3.12) is fixed, not waived; setuptools is
# a venv seed package, not a locked dependency, and does not occur on CI at all.
#
# 2026-09-10: that last sentence is the one the whole arrangement rests on -- "we cannot fix
# this on our floor interpreter" and "we have turned off an alert" differ only by it -- and
# nothing re-derived it. tests/test_pip_audit_waivers.py now does, offline, from uv.lock:
# every id below has a registry entry naming its package and first fixed version (neither
# list may grow alone), every waived package's >=3.10 resolution is at or above that version
# so CI is fixed rather than waived, and every <3.10 resolution is still below it so no
# waiver here is suppressing nothing. Prompted by three HIGH Dependabot alerts (urllib3
# CVE-2026-44431/44432, msgpack CVE-2026-57585) which the platform reports at `runtime`
# scope: measured, all three reach this tree only through pip-audit's own dependency chain
# (pip-audit -> requests -> urllib3, pip-audit -> CacheControl -> msgpack), no tracked file
# imports any of them, and the shipped runtime still has zero dependencies. Re-derived by
# hand the same day with the dry-run command above: no fix for filelock, msgpack, pip,
# pytest, requests, setuptools or urllib3 is installable on 3.9 -- every one of the seven is
# unsatisfiable because the fix depends on Python>=3.10.
PIP_AUDIT_WAIVERS := \
	--ignore-vuln PYSEC-2026-3721 \
	--ignore-vuln PYSEC-2026-3447 \
	--ignore-vuln GHSA-w853-jp5j-5j7f \
	--ignore-vuln GHSA-qmgc-5h2g-mvrw \
	--ignore-vuln GHSA-6v7p-g79w-8964 \
	--ignore-vuln PYSEC-2026-196 \
	--ignore-vuln GHSA-58qw-9mgm-455v \
	--ignore-vuln GHSA-jp4c-xjxw-mgf9 \
	--ignore-vuln GHSA-6w46-j5rx-g56g \
	--ignore-vuln GHSA-gc5v-m9x4-r6x2 \
	--ignore-vuln PYSEC-2026-142 \
	--ignore-vuln PYSEC-2026-141

# Hard-fail, not soft-skip: this target used to fall back to "not installed —
# skipping (CI enforces it)" for each tool, which is exactly the silent-gate
# pattern this standard forbids (CICD-27) — a developer running `make verify`
# got a false "all gates passed" locally. Install the dev group (`make dev`)
# to get all three tools; see CONTRIBUTING.md#prerequisites for gitleaks (not
# a PyPI package, install via your OS package manager).
security:
	@command -v gitleaks >/dev/null 2>&1 || { echo "gitleaks not installed — see CONTRIBUTING.md#prerequisites"; exit 1; }
	@$(PY) -m pip show bandit >/dev/null 2>&1 || { echo "bandit not installed — run 'make dev' (dependency-groups: dev)"; exit 1; }
	@$(PY) -m pip show pip-audit >/dev/null 2>&1 || { echo "pip-audit not installed — run 'make dev' (dependency-groups: dev)"; exit 1; }
	gitleaks detect --no-banner --redact
	$(PY) -m bandit -q -r monitor store report
	$(PY) -m pip_audit $(PIP_AUDIT_WAIVERS)

# Structural a11y checks run in the pytest suite; this adds the pa11y/axe pass when
# Node is available, against a freshly rendered report.
#
# Written as if/then/else, not `command -v npx && npx pa11y-ci ... || echo ...`: in
# `A && B || C` the fallback runs whenever B *fails*, so a genuine accessibility finding
# exited 0 and printed "npx/pa11y not available" — a green gate plus a false reason for
# it, on a machine where pa11y was installed and had just reported errors. Same
# silent-gate defect the `security` target's comment describes (CICD-27), in its nastier
# shape, because this one fires when the tool is present. tests/test_gate_selftest.py
# now holds every recipe in this file to the if/then/else form. Only a genuinely absent
# npx is soft: pytest's structural gate is the documented enforced floor there.
a11y:
	@$(PY) -m pytest tests/test_a11y.py -q
	@$(MAKE) report >/dev/null
	@if command -v npx >/dev/null 2>&1; then \
		npx --yes pa11y-ci --json report.html; \
	else \
		echo "npx/pa11y not available — structural a11y gate (pytest) is the enforced floor"; \
	fi

snapshot:
	$(PY) scripts/gen_snapshot.py

# Writes the figures the documents state about this repo -- waived CVEs, ADRs, and the
# validation surface stated in two places -- from the tree itself, so that adding a test
# file costs a command rather than an edit to a number in two documents.
# tests/test_doc_figures.py fails when they disagree; this is the half that fixes it, and
# like `snapshot` it is deliberately not a prerequisite of `verify`: a gate that repairs
# what it checks cannot fail.
doc-figures:
	$(PY) scripts/doc_figures.py

# Render a sample report from a demo event log so `make report` always produces output.
report:
	$(PY) scripts/demo_report.py

# Render a sample tagged PDF/A-3a from the demo event log (EXP-06). Needs the
# optional 'pdf' extra: `pip install -e '.[pdf]'` (weasyprint>=67, itself needs a
# >=3.10 host interpreter — see docs/adr/0004-weasyprint-for-tagged-pdf-a-export.md).
# Not part of `verify`: like `live`, this extra is opt-in and diverges further from
# the >=3.9 core floor, so it cannot be a default gate on every host.
pdf:
	$(PY) scripts/demo_pdf.py

# Best-effort PDF/A-3a conformance check against the demo PDF, when veraPDF is
# installed (a Java tool, not a PyPI package — same "install separately" situation as
# gitleaks; see CONTRIBUTING.md#prerequisites and the ADR). Advisory, not
# merge-blocking: tests/test_pdf_export.py's structural pytest gate is the enforced
# floor; full veraPDF CI wiring plus the still-outstanding human assistive-technology
# walkthrough are tracked as follow-up, not done in this pass.
pdf-a11y:
	@$(MAKE) pdf
	@if command -v verapdf >/dev/null 2>&1; then \
		verapdf --flavour 3a report.pdf; \
	else \
		echo "verapdf not installed — see docs/adr/0004-weasyprint-for-tagged-pdf-a-export.md; tests/test_pdf_export.py's structural gate is the enforced floor"; \
	fi

# Browser (PWA) variant tests — needs Node.
pwa-test:
	node --test pwa/*.test.mjs

# i18n status is N/A for this single-user, operator-only tool (see docs/I18N.md).
# Enforcing gate per INTERNATIONALIZATION-STANDARD §1: the N/A declaration must
# exist with the required marker and a non-empty Reason; absence fails the build.
i18n:
	@grep -q 'i18n status: N/A' docs/I18N.md || { echo "docs/I18N.md missing 'i18n status: N/A' declaration"; exit 1; }
	@grep -Eq '^Reason: .+' docs/I18N.md || { echo "docs/I18N.md missing a non-empty 'Reason:' line"; exit 1; }
	@echo "i18n: N/A declaration present."

# Static analysis of the workflows themselves (GAP-CICD-1, CICD-19). zizmor reads
# .github/workflows/ for the mistakes a linter can see and a reviewer stops seeing: an
# expression interpolated into a `run:` block, a token wider than the job needs, an
# action pinned to a tag rather than a commit. Offline mode is the default and is what
# CI runs, so the local and remote answers match without a token.
#
# Part of `verify`, and deliberately NOT a new required status check. Five required
# checks that could not fail were removed from this repository on 2026-08-26, and the
# lesson recorded then was that adding a context name is how such a check gets in. This
# one runs inside the gate that already exists.
#
# The second half is a disclosure, not a gate, and is marked as such. zizmor's default
# persona shows only what it considers actionable and prints "(N suppressed)" for the
# rest, so a bare "No findings to report" is a smaller claim than it reads as -- the
# same shape as a status page reporting 100% coverage before a frame was read (#61).
# The `-` prefix means make ignores this line's exit status: the enforced verdict is
# the unguarded command above it, and only that one. Run
# `make workflows-auditor` to see the hidden findings in full.
workflows:
	@command -v $(UVX) >/dev/null 2>&1 || { echo "uvx not installed — see CONTRIBUTING.md#prerequisites"; exit 1; }
	$(ZIZMOR) --format=plain .github/workflows/
	@echo "--- not enforced by the run above ---"
	@echo "zizmor's default persona hides informational findings. Under --persona=auditor:"
	-@$(ZIZMOR) --format=plain --persona=auditor .github/workflows/ | tail -n 1
	@echo "Those are recorded in docs/GAP-LEDGER.md#gap-cicd-1, not silently dropped."

# The hidden half of `make workflows`, in full. Not part of `verify`: it reports
# informational findings this repository has a stated reason not to act on (naming the
# `verify` and `test-matrix` jobs would rename the required status-check contexts and
# lock `main`), so gating on it would be gating on a decision, not on a defect.
workflows-auditor:
	@command -v $(UVX) >/dev/null 2>&1 || { echo "uvx not installed — see CONTRIBUTING.md#prerequisites"; exit 1; }
	$(ZIZMOR) --format=plain --persona=auditor .github/workflows/

# Diff the LIVE branch ruleset on main against .github/rulesets/main.json. Exits 1 on any
# difference and 2 ("CANNOT VERIFY") when gh is missing, unauthenticated, or the API
# errors — never 0 without having read the live configuration. Deliberately NOT part of
# `verify`: it needs network access and a `gh` token that can read repository
# administration, neither of which a local gate may assume. The check it replaces
# selected the ruleset by a name the live one does not have, so it printed nothing and
# exited 0 forever; see .github/rulesets/README.md.
ruleset-check:
	$(PY) scripts/check_ruleset.py

# Fail unless the nightly macOS sweep (nightly.yml) actually ran on macOS runners,
# recently, and passed. CI runs this inside the `verify` job, where it is merge-blocking;
# this target is the local twin. Same network/auth caveat as ruleset-check, so it is not
# part of `verify` either. It replaced five required status checks that an `echo` on an
# ubuntu runner satisfied -- see .github/rulesets/README.md.
nightly-check:
	$(PY) scripts/check_nightly_macos.py

verify: lint hooks workflows type cov security a11y pwa-test i18n
	@echo "All local gates passed."
	@echo "Note: 'make ruleset-check' and 'make nightly-check' are separate (they need"
	@echo "network + gh auth). CI runs both inside the required 'verify' job; locally"
	@echo "they are the only things that can tell you whether the live branch ruleset"
	@echo "still matches the repo and whether the nightly macOS sweep is actually green."

clean:
	rm -rf .pytest_cache .ruff_cache .coverage htmlcov report.html demo.db
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
