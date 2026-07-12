"""Tagged PDF/A export of the report HTML (EXP-06).

Optional: needs the `pdf` extra (``pip install -e '.[pdf]'``; ``weasyprint>=67``,
which itself requires a >=3.10 host interpreter -- see
``docs/adr/0003-weasyprint-for-tagged-pdf-a-export.md``). The core report pipeline
(``report/render.py``, ``report/violations.py``) is completely unaffected: this
module is only imported when a PDF is actually requested, and nothing here runs on
the always-on monitoring path or the zero-dependency core.

What this can and cannot claim
-------------------------------
This renders the exact same deterministic HTML ``report.render.build_report()`` /
``report.violations.build_violation_report_html()`` already produce (so nothing
here re-encodes the report's structure) through WeasyPrint's
``pdf_variant="pdf/a-3a"`` + ``pdf_tags=True``, which *requests* PDF/A-3a --
archival plus a required tag tree, ISO 19005's own "Accessible" conformance level.
See the ADR for why this variant and why WeasyPrint.

Requesting tags is not the same as PDF/UA *conformance*. ``tests/test_pdf_export.py``
verifies the STRUCTURAL properties a test suite can actually verify: a tag tree
exists, ``<html lang>`` carries through as the PDF's ``/Lang``, the document is
marked (``/MarkInfo``), headings appear in document order, tables have header cells
that carry ID/associated-header data, and every chart's descriptive summary survives
as tagged text. It explicitly does NOT and CANNOT verify that the PDF is usable by
a real screen reader, that reading order is *sensible* rather than merely present,
or that any alt text is a semantically good description --
``docs/ideation/04-impact-and-sequencing.md``'s human-gate table already names the
real fix: a committed assistive-technology walkthrough. That has not happened, and
this module does not claim PDF/UA conformance.

A verified WeasyPrint limitation, and this module's mitigation
----------------------------------------------------------------
As tested against WeasyPrint 66.0 through 69.0 (checked 2026-07-09), requesting
``pdf_tags=True`` against this project's actual multi-chart report HTML crashes
with ``ValueError: Table wrapper without a table`` inside WeasyPrint's own tagging
code (``weasyprint/formatting_structure/boxes.py``'s ``get_wrapped_table``, a branch
WeasyPrint's own source marks ``# pragma: no cover`` -- i.e. their own test suite
does not exercise it). This reproduces even with a minimal, CSS-free HTML document
built only from this project's real inline-SVG bar/heatmap charts
(``report/charts.py``) next to more than one ``<table>``; it is independent of the
requested ``pdf_variant`` and is not fixed as of the latest release checked (69.0).
Bisection traced it to the combination of inline chart SVGs, chart ``<figure>``
wrappers, and the browser-print rule that forbids tables from splitting across pages.
The tagged-PDF preparation removes the SVG, flattens only chart figures into neutral
``<div>`` containers, lets large PDF tables paginate, and renders the summary definition
list as normal block flow instead of CSS grid. This avoids the crash across the real demo,
empty, single-event, and 1-4 day fixtures, including the formerly failing two-day case.

Since ``report/charts.py``'s own design already treats each chart's SVG as a
supplementary visual only -- "every chart is followed by a real ``<table>`` ... so
screen readers and keyboard users get the data without the graphic" -- and a
separate check (see the ADR) found that WeasyPrint does not currently carry an
SVG's ``role="img"``/``aria-label`` into the PDF structure tree's ``/Alt``
attribute *anyway* (only a real ``<img alt="...">`` propagates), dropping the SVG
for the tagged-PDF path loses no accessible information that was reaching the PDF
in the first place: :func:`charts_to_text_summaries` replaces each chart's
``<svg aria-label="...">`` with a plain tagged ``<p>`` carrying that same summary
text, and the already-tagged data table that follows every chart is untouched. The
visual-only figure wrapper is flattened because WeasyPrint's tagger mishandles it when
the enclosed table crosses particular page layouts; its caption becomes a tagged
paragraph, preserving reading order and content.
This is a narrow, tested workaround for a verified upstream defect, not a general
design change -- the on-screen HTML report (``report/render.py``) keeps its SVG
charts exactly as before; only the bytes handed to WeasyPrint are adjusted.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, cast

#: PDF/A level "a" (Accessible): ISO 19005's own definition of level A is level B
#: (archival) plus a required Tagged-PDF structure tree -- i.e. this single variant
#: string is "PDF/A + tagged" as one conformance claim. See the ADR for the full
#: comparison against PDF/UA-only and lower PDF/A levels.
PDF_VARIANT = "pdf/a-3a"

# Matches this project's chart <svg ... aria-label="...">...</svg> markup
# (report/charts.py). Non-greedy body match with DOTALL since chart SVGs are emitted
# as one long line with no nested <svg>. A no-op on HTML with no chart SVGs (e.g.
# report/violations.py's output, which has none).
_CHART_SVG_RE = re.compile(r'<svg\b[^>]*\baria-label="([^"]*)"[^>]*>.*?</svg>', re.DOTALL)
_CHART_FIGURE_RE = re.compile(r'<figure class="chart">(.*?)</figure>', re.DOTALL)

_PDF_LAYOUT_STYLE = """<style>
/* PDF-only pagination and wide-table constraints. */
#calendar-table { font-size: 5pt; table-layout: fixed; width: 100%; }
#calendar-table th, #calendar-table td { padding: 0.5pt; }
#calendar-table th:first-child { width: 54pt; }
.note { break-inside: avoid; page-break-inside: avoid; }
</style>"""


class PdfExportUnavailable(RuntimeError):
    """The optional `pdf` extra (weasyprint) is not installed."""


class TaggedPdfGenerationError(RuntimeError):
    """WeasyPrint failed to build a tagged structure tree for otherwise-valid HTML."""


def _weasyprint() -> Any:
    try:
        import weasyprint
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise PdfExportUnavailable(
            "Tagged PDF/A export needs the optional 'pdf' extra: "
            "pip install -e '.[pdf]' (weasyprint>=67, which itself needs a Python "
            ">=3.10 host interpreter). See "
            "docs/adr/0003-weasyprint-for-tagged-pdf-a-export.md."
        ) from exc
    return weasyprint


def charts_to_text_summaries(html: str) -> str:
    """Replace each chart's ``<svg aria-label="...">`` with a tagged ``<p>`` of that text.

    Narrow, tested mitigation for a verified WeasyPrint tagging crash -- see the
    module docstring. A no-op (returns `html` unchanged) when no chart SVG is
    present, so it is safe to call unconditionally on any report HTML.
    """
    prepared = _CHART_SVG_RE.sub(lambda m: f'<p class="chart-summary">{m.group(1)}</p>', html)

    def flatten_chart(match: re.Match[str]) -> str:
        body = match.group(1).replace("<figcaption>", '<p class="chart-title">')
        body = body.replace("</figcaption>", "</p>")
        return f'<div class="pdf-chart">{body}</div>'

    prepared = _CHART_FIGURE_RE.sub(flatten_chart, prepared)
    # Browser printing tries to keep every table on one page. Large report tables cannot
    # satisfy that constraint, and WeasyPrint 66-69's tagger can create an orphan wrapper
    # while retrying the layout. Tagged PDFs must allow tables to paginate instead.
    prepared = prepared.replace("page-break-inside: avoid;", "")
    prepared = prepared.replace("break-inside: avoid;", "")
    prepared = prepared.replace("display: grid;", "display: block;")
    # Inject after removing the broad browser rules above: keeping compact notes
    # together is safe, while the 26-column calendar needs explicit sizing to fit A4.
    return prepared.replace("</head>", f"{_PDF_LAYOUT_STYLE}</head>", 1)


def html_to_tagged_pdf_bytes(html: str) -> bytes:
    """Render report HTML to tagged PDF/A-3a bytes.

    Requests PDF/A-3a (archival) plus a real structure tree (`pdf_tags=True`) from
    WeasyPrint -- a *request*, not a conformance guarantee. See the module and ADR
    docstrings for exactly what is, and is not, verified.
    """
    weasyprint = _weasyprint()
    safe_html = charts_to_text_summaries(html)
    blocked_urls: list[str] = []

    def block_external_resource(url: str, *_args: object, **_kwargs: object) -> None:
        # HTML(string=...) otherwise uses WeasyPrint's default fetcher, which supports
        # HTTP, FTP, and file URLs. Reports are local-only: record and reject every
        # attempted resource load before the library can touch the network or filesystem.
        blocked_urls.append(url)
        raise OSError("external resources are disabled for local-only PDF export")

    try:
        pdf_bytes = weasyprint.HTML(
            string=safe_html,
            url_fetcher=block_external_resource,
        ).write_pdf(
            pdf_variant=PDF_VARIANT,
            pdf_tags=True,
        )
        if blocked_urls:
            raise TaggedPdfGenerationError(
                "PDF export blocked external resource references to preserve the "
                f"local-only guarantee: {', '.join(blocked_urls)}"
            )
        return cast(bytes, pdf_bytes)
    except OSError as exc:
        if blocked_urls:
            raise TaggedPdfGenerationError(
                "PDF export blocked external resource references to preserve the "
                f"local-only guarantee: {', '.join(blocked_urls)}"
            ) from exc
        raise TaggedPdfGenerationError(f"WeasyPrint could not write the PDF ({exc}).") from exc
    except ValueError as exc:
        if blocked_urls:
            raise TaggedPdfGenerationError(
                "PDF export blocked external resource references to preserve the "
                f"local-only guarantee: {', '.join(blocked_urls)}"
            ) from exc
        # WeasyPrint's own tagging code can raise a bare ValueError on content
        # shapes it doesn't handle yet (see module docstring). Translate it into a
        # named, actionable error rather than let a library-internal traceback (or,
        # worse, a silently-produced *untagged* file mislabeled as accessible) reach
        # the caller.
        raise TaggedPdfGenerationError(
            "WeasyPrint could not build a tagged structure tree for this report "
            f"({exc}). This is a known WeasyPrint limitation reproduced against "
            "this project's report HTML, not a defect in the report data -- see "
            "docs/adr/0003-weasyprint-for-tagged-pdf-a-export.md."
        ) from exc


def write_tagged_pdf(html: str, path: str | Path) -> int:
    """Write a tagged PDF/A-3a rendering of `html` to `path`. Returns bytes written."""
    data = html_to_tagged_pdf_bytes(html)
    Path(path).write_bytes(data)
    return len(data)
