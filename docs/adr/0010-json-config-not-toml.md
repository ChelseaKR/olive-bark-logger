# 0010. Configuration is JSON, not TOML

**Status:** Accepted · **Date:** 2026-06-05 · **Migrated:** 2026-09-05 from `docs/ROADMAP.md` §6 (GAP-DOC-1)

## Context
TOML is the ordinary choice for Python project configuration. Reading it on this
project's runtime floor is not free: `tomllib` entered the standard library in Python
3.11, and this project's floor is 3.9 ([ADR-0002](./0002-python-39-floor.md)), so TOML
means a third-party parser on the always-run path — exactly what
[ADR-0009](./0009-zero-dependency-pure-python-core.md) exists to prevent. The config
file here is a flat set of scalars: thresholds, durations, paths, a zone, quiet hours.

## Decision
Config is **JSON**, read with the standard library's `json` module
(`monitor/config.py`). Missing fields fall back to the dataclass defaults, so a partial
file is valid and an absent file is valid.

**Rejected: a third-party TOML parser** — a dependency, on the always-run path, for
config.

## Consequences
- **Easier:** the zero-dependency core holds, and the config format is readable by
  everything.
- **Harder / accepted:** JSON has no comments, so the explanation of what each field
  means lives in `monitor/config.py` and the README rather than beside the value.
- **Revisit trigger:** if the runtime floor ever rises to 3.11, `tomllib` becomes
  stdlib and this decision loses its premise. Supersede this ADR then rather than
  editing it — and note that changing the format is a migration for every deployed
  config, not a free swap.
