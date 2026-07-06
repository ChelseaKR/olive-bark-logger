## What & why

<!-- What changed, and why. Link an issue/GAP-LEDGER entry if this closes one. -->

## Definition of Done
See `DEFINITION_OF_DONE.md` for the full checklist. At minimum:
- [ ] `make verify` passes locally.
- [ ] `tests/test_no_audio.py` / `test_no_egress.py` / `test_report_content.py` still
      pass; if this PR touches them, I've explained why above, not just what.
- [ ] `CHANGELOG.md` updated under `[Unreleased]`.
- [ ] Regenerated dated artifacts if I changed the report template, the PWA, or
      anything a `docs/audits/*` file describes (QM-13, RTF-08).
- [ ] Added an ADR under `docs/adr/` if this is an expensive-to-reverse decision.
- [ ] N/A declarations (i18n, AI evaluation) re-checked honest, not just left as-is,
      if this PR touches anything they cover (DOC-14).

## Standards impact
<!-- Does this PR change conformance state for any /STANDARDS row? If so, update
     README.md's Standards Conformance table and, if a gap closes or opens,
     docs/GAP-LEDGER.md in the same PR. -->
