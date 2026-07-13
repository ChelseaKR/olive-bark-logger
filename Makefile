# Olive's Bark Logger — developer entrypoints.
# `make verify` runs the full merge-blocking gate set locally, mirroring CI.

PY ?= .venv/bin/python
PIP ?= .venv/bin/pip
RUFF ?= ruff
MYPY ?= mypy

.PHONY: help venv dev fmt lint type test cov security a11y snapshot report pdf pdf-a11y pwa-test i18n verify clean

help:
	@echo "Targets: dev fmt lint type test cov security a11y snapshot report pdf pdf-a11y pwa-test verify clean"

venv:
	python3 -m venv .venv
	$(PIP) install --upgrade pip
	$(PIP) install -e . --group dev

dev: venv
	@echo "Dev environment ready. Run 'make verify' to check all gates."

fmt:
	$(RUFF) format monitor store report tests scripts

lint:
	$(RUFF) check monitor store report tests scripts
	$(RUFF) format --check monitor store report tests scripts

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
PIP_AUDIT_WAIVERS := \
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
a11y:
	@$(PY) -m pytest tests/test_a11y.py -q
	@$(MAKE) report >/dev/null
	@command -v npx >/dev/null 2>&1 && npx --yes pa11y-ci --json report.html || echo "npx/pa11y not available — structural a11y gate (pytest) is the enforced floor"

snapshot:
	$(PY) scripts/gen_snapshot.py

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

verify: lint type cov security a11y pwa-test i18n
	@echo "All local gates passed."

clean:
	rm -rf .pytest_cache .ruff_cache .coverage htmlcov report.html demo.db
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
