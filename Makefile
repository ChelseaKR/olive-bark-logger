# Olive's Bark Logger — developer entrypoints.
# `make verify` runs the full merge-blocking gate set locally, mirroring CI.

PY ?= .venv/bin/python
PIP ?= .venv/bin/pip
RUFF ?= ruff
MYPY ?= mypy

.PHONY: help venv dev fmt lint type test cov security a11y snapshot report pwa-test i18n verify clean

help:
	@echo "Targets: dev fmt lint type test cov security a11y snapshot report pwa-test verify clean"

venv:
	python3 -m venv .venv
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"

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

security:
	@command -v gitleaks >/dev/null 2>&1 && gitleaks detect --no-banner --redact || echo "gitleaks not installed — skipping secret scan (CI enforces it)"
	@$(PY) -m pip show bandit >/dev/null 2>&1 && $(PY) -m bandit -q -r monitor store report || echo "bandit not installed — skipping SAST (CI enforces it)"
	@$(PY) -m pip show pip-audit >/dev/null 2>&1 && $(PY) -m pip_audit || echo "pip-audit not installed — skipping dep scan (CI enforces it)"

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

verify: lint type cov a11y pwa-test i18n
	@echo "All local gates passed."

clean:
	rm -rf .pytest_cache .ruff_cache .coverage htmlcov report.html demo.db
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
