# Security Policy

## Supported versions
This project is pre-1.0 (`Status: Beta`, see `README.md`). Only the latest `0.y` release
line receives security fixes; there is no LTS branch. Once a `v1.0.0` is tagged, this
section will name the supported major-version window per REL-24.

## Reporting a vulnerability
Please report vulnerabilities privately via
[GitHub's private vulnerability reporting](https://github.com/ChelseaKR/olive-bark-logger/security/advisories/new)
("Security" tab → "Report a vulnerability") rather than a public issue. If that isn't
available, email the maintainer listed in `CITATION.cff`.

- **Response SLA:** an initial acknowledgment within **7 days**, a fix or documented
  mitigation within **90 days** of confirmation, whichever is faster for the severity.
- **Scope:** this is a local-only, single-user, zero-network tool with no server
  component and no accounts; the realistic attack surface is (1) a malicious dependency,
  (2) a bug that reintroduces audio persistence or network egress (both guarded by
  merge-blocking tests: `tests/test_no_audio.py`, `tests/test_no_egress.py`), and (3) the
  container image / CI supply chain. Reports about any of these are welcome.
- **Out of scope:** the device's dBFS measurement is explicitly uncalibrated/relative
  by design (see `docs/audits/methodology-and-limitations.md`) — that is documented
  behavior, not a vulnerability.

## What we do about known issues
- Dependencies: `pip-audit` runs merge-blocking in CI on every push/PR (`ci.yml`);
  Renovate (`renovate.json`) opens PRs for updates with a 72-hour cooldown.
- Secrets: `gitleaks` runs merge-blocking in CI; there are no secrets in this repo by
  design (local-only tool, no API keys or cloud credentials — see
  `docs/RESPONSIBLE-TECH-AUDITS.md` §F).
- Static analysis: `bandit` runs merge-blocking in CI.
- Any accepted, currently-unfixable dependency CVE is recorded as a dated waiver in
  `Makefile` (`PIP_AUDIT_WAIVERS`) with rationale, not silently ignored — see
  `docs/RESPONSIBLE-TECH-AUDITS.md` §F "VEX".
