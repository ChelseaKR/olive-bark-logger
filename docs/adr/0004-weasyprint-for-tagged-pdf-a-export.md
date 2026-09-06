# 0004. WeasyPrint for tagged PDF/A export (EXP-06)

**Status:** Accepted · **Date:** 2026-07-09

## Context
`docs/ideation/03-expansions.md`'s EXP-06 ("Accessible tagged PDF/A export") flags that
the README promises "PDF/HTML" but only an accessible HTML report
(`report/render.py`) exists today; what actually reaches a property manager is whatever
a browser's print dialog produces from the `@media print` styles — untagged, with no
structure tree, unsuitable as an archival or assistive-technology-usable artifact.
This ADR is the "needs an ADR on the PDF dependency" half of that item's deferral note
(`docs/ideation/04-impact-and-sequencing.md`'s human-gate table); the other half — a
real screen-reader validation of the PDF/UA claim — stays deferred to a human
assistive-technology (AT) reviewer and is **not** resolved by this ADR or its
implementation (see Consequences).

Adding any PDF library is an expensive-to-reverse dependency decision under this
project's zero-dependency-core design goal (`docs/ROADMAP.md`'s "Zero-dependency,
pure-Python core"; ADR-0002 documents how seriously that goal is held). It must be an
*optional* extra like `live` (`pyproject.toml`), not a core dependency, and it must
produce real tagged-PDF structure, not merely "a PDF that looks right" — a screen
reader gets nothing from an untagged PDF regardless of visual fidelity.

### Requirement
A Python-importable path from the existing report data model
(`report.aggregate.Summary`, `monitor.config.Config`, `store.Session`) to a PDF that:
1. Can declare **PDF/A** conformance (archival: fonts embedded, no external
   dependencies, restricted feature set) — required by the item's own name and the
   "suitable for filing" use case in `docs/ideation/03-expansions.md`.
2. Carries a real **tag tree** (structure elements for headings, paragraphs, tables,
   figures; an explicit reading order) — not just visual layout — because that is the
   only part of "accessible" a screen reader can act on.
3. Is verifiable, as far as automation can verify it: tag presence, heading nesting,
   table structure, reading order. Full **PDF/UA conformance is not something a test
   suite can certify** — conformance testing programs like veraPDF check machine-
   checkable structural rules, and even those explicitly do not certify the *semantic
   correctness* of tags (e.g., whether alt text is actually a good description) or
   real screen-reader usability. That last mile is why this stays human-gated.

## Options considered

### 1. WeasyPrint (chosen)
Docs verified against the current stable release line as of this pass (checked
2026-07-09 against `doc.courtbouillon.org/weasyprint/stable/` and the project
changelog, both current as of WeasyPrint 69.0 / 2026-06-02):

- `HTML(...).write_pdf(pdf_variant=..., pdf_tags=True, ...)` is a real, documented
  API. `pdf_variant` accepts an explicit, enumerated set of ISO conformance strings
  including `pdf/a-1a`, `pdf/a-2a`, `pdf/a-3a` (PDF/A's own "Accessible" level, which
  the standard defines as level B plus a required tagged structure tree — i.e. PDF/A
  level A *is* "PDF/A + tagged PDF" as one ISO 19005 conformance claim) and
  `pdf/ua-1` / `pdf/ua-2` (pure PDF/UA, ISO 14289) as separate variant choices.
  `pdf_tags` (default `False`) is a distinct boolean that turns on structure-tree
  generation.
- This is not a token feature: the changelog shows PDF/A support landing in `56.0b1`
  (2022-06-17, funded by Blueshoe), PDF/UA in `57.0b1` (2022-09-22, funded by
  Novareto), a *substantial* PDF/UA rework in `66.0` (2025-07-24, funded by NLnet,
  spanning 18 linked issues/PRs) that rebuilt tagging to derive the structure tree
  from "the semantic HTML tree" (headings, paragraphs, table headers, list items)
  instead of the old drawing-order heuristic, and PDF/A level-A (`pdf/a-1a`,
  `pdf/a-2a`, `pdf/a-3a`) support arriving in `67.0` (2025-12-02). This is active,
  externally-funded, accessibility-specific engineering investment, not a checkbox.
- Because WeasyPrint renders HTML+CSS, its structure tree is derived from the
  *existing* semantic HTML this project already produces and already tests
  (`tests/test_a11y.py`: one `<h1>`, `<h2>` structure, `scope="col"`/`scope="row"`
  table headers, `role="img"` + `aria-label` on every chart SVG, a data-table
  equivalent for every chart). No parallel tagging code has to be hand-written and
  kept in sync with the HTML report — the same markup is the source of truth for both
  the on-screen report and the PDF's structure tree.
- This also matches the roadmap item's own prescribed test strategy verbatim:
  "snapshot-test the intermediate deterministic HTML, not the binary" — only
  coherent if the PDF path's input *is* deterministic HTML, which is WeasyPrint's
  model and is not true of an imperative document-building API.
- Documented limitation, quoted directly: "the generated documents are not
  guaranteed to be valid, and users have the responsibility to check that they
  follow the rules listed by the related specifications." WeasyPrint requesting tags
  is not proof of conformance — see Consequences.

### 2. ReportLab (rejected)
ReportLab's open-source `reportlab` package is the incumbent, well-maintained pure-
Python PDF library and was seriously considered. Its "accessibility branch" merged
into the open-source package at `4.0.0` (2023-05-04; `CHANGES.md` confirms tagging
primitives — e.g. list/table cell tagging support — landed in the open-source
package, not only in a commercial fork). However:
- ReportLab's own published accessibility guidance
  (`docs.reportlab.com/pdf-accessibility/`, reportlab.substack.com "Accessible
  PDFs") frames the practical "one flag gets you 95% of tagging" workflow
  (`tagged="1"` on the document element) in terms of **RML**, ReportLab's XML
  templating layer that ships as part of the commercial **ReportLab PLUS** product —
  not the open-source `reportlab` Platypus/canvas API this project would actually
  import. The open-source package exposes lower-level primitives
  (`canvas.beginTag`/`endTag`, Platypus flowable tagging attributes), but there is no
  confirmed open-source equivalent of a single automatic-tagging switch.
- Building a correct structure tree with the open-source primitives means hand-
  authoring `beginTag`/`endTag` (or flowable-level tag attributes) around every
  heading, table, and figure — i.e., re-encoding the same semantic structure that
  `report/render.py` already expresses once in HTML, as a second, parallel,
  imperative document-building program with no intermediate artifact to snapshot-
  test. That doubles the report's maintenance surface for every future template
  change (this project already has one dated staleness incident from exactly this
  kind of drift — `docs/audits/accessibility-2026-06-05.md` notes the manual a11y
  walkthrough going stale after a template change) and is a materially larger,
  riskier implementation for no clearer accessibility payoff than option 1.

### 3. fpdf2 (rejected, quickly)
`py-pdf/fpdf2` supports verifying/producing several PDF/A conformance levels, but its
own documentation and open issue tracker (`py-pdf/fpdf2#792`, still open as of
`2.8.7`, 2026-02-28) state that the **accessible** PDF/A levels — `PDF/A-1A`,
`2A`, `3A` — are explicitly **not yet supported**, and that real-content-vs-artifact
tagging (the prerequisite for any tagged PDF, accessible or not) is still an open
feature request, not a shipped capability. Ruled out on documented capability alone.

### 4. Post-process an untagged PDF (e.g. `pikepdf`/`pypdf` + hand-built structure)
Rejected without deep evaluation: these libraries manipulate existing PDF objects but
do not generate a tag tree from a document description, so they would still require
the same hand-authored, per-element tagging problem as option 2, with even less
built-in tooling. Not pursued further given options 1–3 already gave a clear answer.

## Decision
**Option 1: WeasyPrint**, as an optional `pdf` extra (`pyproject.toml`,
`weasyprint>=67,<70` — 67 is the floor for PDF/A level-A support, while the upper
bound forces a deliberate rendering review before adopting a new browser-style major
release). `report/pdf_export.py` renders the existing `report.render.build_report()`
HTML through `HTML(string=...).write_pdf(pdf_variant="pdf/a-3a", pdf_tags=True, ...)`
— PDF/A-3a because it is the single ISO 19005 conformance claim that means "archival
*and* tagged" in one variant string, matching this roadmap item's name directly, and
because level 3 (over 1/2) allows attaching the source event data as documented in
the WeasyPrint PDF/A guidance ("PDF/A-3u should be preferred: it allows... arbitrary
formats for attached files that are forbidden in A-2" — the same reasoning applies to
the -3 level generally, kept available for a future CSV-attachment enhancement even
though this pass does not use it).

### Amendment, 2026-09-06: the workaround was passing by coincidence

The mitigation recorded above (drop the chart SVG, flatten the chart `<figure>`,
let large tables paginate) was verified against the fixture set as it stood, and
that turned out to be the whole extent of its guarantee. Appending filler
paragraphs to the report before conversion, and changing nothing else, moved the
gate's verdict around at random:

| extra `<p>` | failures in `tests/test_pdf_export.py` |
|---:|---:|
| 0 | 7 |
| 1 | 7 |
| 5 | 1 |
| 20 | 6 |
| 60 | **0** |

Every failure was the same `ValueError: Table wrapper without a table`. The suite
was green at exactly the report's own length, so the next person to add a sentence
to the report would have been handed a red gate and a stack trace pointing into
WeasyPrint.

The mechanism is narrower than the original bisection concluded. WeasyPrint wraps a
`<table>` together with its `<caption>` in one table-wrapper box. When the caption
fits at the foot of a page and the table body does not, the fragment left behind is
a wrapper holding a caption and no table — the state `get_wrapped_table` refuses.
Nothing in the earlier mitigation stopped a caption being separated from its table;
it only removed the *other* ways of arriving at a bad layout.

The fix is one rule in `_PDF_LAYOUT_STYLE`:

```css
caption { break-after: avoid; page-break-after: avoid; }
```

With it, the same sweep passes at 0, 1, 5, 20 and 60 extra paragraphs. The property
is now pinned by `test_the_tagged_pdf_survives_a_longer_report`, which parametrizes
over those lengths, and by `test_the_caption_keep_together_rule_is_the_one_doing_the_work`,
which removes the rule in-process and asserts the crash comes back — without that
control a future edit could drop the rule and every other test here would stay green
until someone added a paragraph. Issue #116 records the measurement.

## Consequences
- **Easier:** an archival + structurally-tagged PDF generation path exists,
  generated from the same semantic HTML already covered by `tests/test_a11y.py` — no
  new hand-maintained tagging code, no divergence between what the HTML report says
  and what the PDF's structure tree says, because they are the same input.
- **Easier:** the zero-dependency core is untouched; `weasyprint` is an opt-in extra
  exactly like `live` (`sounddevice`), and `monitor/`, `store/`, and the existing
  HTML-only `report/render.py` path still require nothing beyond the standard
  library.
- **Harder / accepted risk:** WeasyPrint is a much heavier dependency than anything
  else in this project (a CSS2/3 layout engine plus native Pango/cairo/GDK-Pixbuf
  bindings via `cffi`) — appropriate only because it is strictly optional and
  export-side, never on the always-run monitoring path.
- **Harder / accepted risk — the honesty-critical one:** *requesting* `pdf_tags=True`
  and `pdf_variant="pdf/a-3a"` is not proof of conformance. WeasyPrint's own docs say
  so explicitly, and no automated test in this repo (or any automated tool,
  including veraPDF) can certify that alt text is *semantically correct*, that
  reading order is *actually* sensible to a real assistive-technology user, or that
  the document is genuinely usable — only that the mechanical, structural rules a
  machine can check are satisfied. This PR's tests assert **structural** properties
  only (tag/marker presence, heading nesting order, a `<title>` and `lang` attribute,
  table header association, an alt-text hook on every chart) and say so in their
  docstrings. **The PDF/UA conformance claim itself remains unverified until a real
  screen-reader walkthrough is performed and committed**, the same human gate
  `docs/ideation/04-impact-and-sequencing.md` already named for this item ("A real
  screen-reader walkthrough of the PDF, committed like
  `docs/audits/accessibility-2026-06-05.md`"). Until that pass exists, any public
  claim of PDF/UA or "fully accessible PDF/A" conformance would be false advertising
  — this repo's own honesty posture (`report/violations.py`'s "never fake" ethos)
  applies here too.
- **Deferred, not solved:** automated conformance validation via **veraPDF** (the
  roadmap's own stated "excellence bar") is not wired into CI in this pass. veraPDF
  is a Java tool, not a PyPI package — the same "not on PyPI, install separately"
  situation this repo already has for `gitleaks` (`CONTRIBUTING.md#prerequisites`).
  A best-effort, non-merge-blocking `make pdf-a11y` target is added
  (mirrors the existing `pa11y`-when-Node-is-available pattern in `make a11y`) so a
  developer with veraPDF installed gets real signal locally; making it a hard CI gate
  is future work, tracked the same way as the human walkthrough itself.
- **Revisit trigger:** if a real AT walkthrough surfaces structural defects that
  WeasyPrint cannot fix (e.g. persistent incorrect reading order for the calendar
  heatmap's SVG), or if veraPDF's `ua1`/`pdfa` profiles fail once actually run against
  real output, re-open this ADR rather than silently loosening the conformance claim.
