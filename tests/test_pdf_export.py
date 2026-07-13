"""Structural tests for tagged PDF/A export (EXP-06).

What these tests verify vs. what they cannot
----------------------------------------------
These assert STRUCTURAL properties of the generated PDF that can be checked by
reading the PDF's own `/StructTreeRoot` back out with `pypdf`: a tag tree exists,
the document is marked, `/Lang` carries through, headings appear in document order,
tables carry header-cell IDs and cell-to-header associations, and each chart's
descriptive summary survives as tagged text (report/pdf_export.py drops the SVG
itself -- see that module's docstring for the verified WeasyPrint crash this works
around).

They do **not**, and structurally cannot, verify PDF/UA *conformance*: whether the
reading order is sensible to a real user, whether any text is a semantically good
description, or whether a screen reader actually works with the file. That needs a
human assistive-technology walkthrough (docs/ideation/04-impact-and-sequencing.md's
human-gate table) which has not happened -- this test file's passing is not, and
must never be read as, a PDF/UA conformance claim.

Skipped entirely (module-level `importorskip`) unless the optional `pdf` extra is
installed (`pip install -e '.[pdf]'`; needs Python >=3.10 -- see
docs/adr/0004-weasyprint-for-tagged-pdf-a-export.md). The core test suite and
`make verify` do not depend on this file passing.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

weasyprint = pytest.importorskip("weasyprint")
pypdf = pytest.importorskip("pypdf")

from monitor.config import Config, QuietHours  # noqa: E402
from monitor.detector import Event  # noqa: E402
from report.aggregate import summarize  # noqa: E402
from report.pdf_export import (  # noqa: E402
    PDF_VARIANT,
    PdfExportUnavailable,
    TaggedPdfGenerationError,
    charts_to_text_summaries,
    html_to_tagged_pdf_bytes,
    write_tagged_pdf,
)
from report.render import build_report  # noqa: E402
from report.violations import build_violation_report_html, compute_violations  # noqa: E402

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _main_report_html(with_events: bool = True, num_days: int = 3) -> str:
    config = Config(tz="UTC", tagging=True)
    events = []
    if with_events:
        base = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc).timestamp()
        spec = [(23, 6.0, -8.0), (23, 4.0, -12.0), (2, 9.0, -5.0), (14, 3.0, -20.0)]
        events = [
            Event(
                start=base + day * 86400 + hour * 3600,
                end=base + day * 86400 + hour * 3600 + dur,
                duration=dur,
                peak_level=peak,
                avg_level=peak - 4.0,
                coarse_tag="bark-like" if i % 2 == 0 else "ambient",
            )
            for day in range(num_days)
            for i, (hour, dur, peak) in enumerate(spec)
        ]
    summary = summarize(events, quiet_hours=config.quiet_hours, tz=config.tzinfo())
    return build_report(summary, config=config, generated_at="2026-01-01 12:00 UTC")


def _violations_html() -> str:
    events = [
        Event(1_767_312_000.0, 1_767_312_004.0, 4.0, -8.0, -12.0, coarse_tag="bark-like"),
        Event(1_767_315_600.0, 1_767_315_601.5, 1.5, -20.0, -24.0),
    ]
    report = compute_violations(
        events, quiet_hours=QuietHours(start_hour=22, end_hour=8), tz_name="UTC"
    )
    return build_violation_report_html(
        report,
        threshold_dbfs=-35,
        min_duration_s=0.4,
        generated_at="2026-01-01 12:00 UTC",
        calibrated=False,
    )


def _struct_tree(pdf_bytes: bytes):
    reader = pypdf.PdfReader.__new__(pypdf.PdfReader)
    import io

    reader.__init__(io.BytesIO(pdf_bytes))
    root = reader.trailer["/Root"]
    return reader, root


def _walk_tags(node) -> list[dict]:
    """Depth-first list of every structure element dict in the tree, in document order."""
    out: list[dict] = []
    obj = node.get_object() if hasattr(node, "get_object") else node
    if isinstance(obj, dict):
        if obj.get("/S") is not None:
            out.append(obj)
        kids = obj.get("/K")
        if kids is not None:
            if not isinstance(kids, list):
                kids = [kids]
            for kid in kids:
                out.extend(_walk_tags(kid))
    return out


# ---------------------------------------------------------------------------
# charts_to_text_summaries: the verified-crash mitigation
# ---------------------------------------------------------------------------


def test_charts_to_text_summaries_is_noop_without_svg():
    html = "<p>no charts here</p>"
    assert charts_to_text_summaries(html) == html


def test_charts_to_text_summaries_leaves_non_chart_figures_untouched():
    html = "<figure><figcaption>Photo</figcaption><p>content</p></figure>"
    assert charts_to_text_summaries(html) == html


def test_charts_to_text_summaries_replaces_svg_with_tagged_paragraph():
    html = (
        "<style>table { break-inside: avoid; page-break-inside: avoid; }</style>"
        '<figure class="chart"><svg viewBox="0 0 1 1" role="img" '
        'aria-label="Events by hour. 3 bars." '
        'xmlns="http://www.w3.org/2000/svg"><rect/></svg><table></table></figure>'
    )
    out = charts_to_text_summaries(html)
    assert "<svg" not in out
    assert '<p class="chart-summary">Events by hour. 3 bars.</p>' in out
    assert '<div class="pdf-chart">' in out and "<figure" not in out
    assert "<table></table>" in out  # the data table equivalent is untouched
    assert "table { break-inside: avoid" not in out
    assert "page-break-inside: avoid; }</style>" not in out


def test_pdf_preparation_constrains_calendar_and_keeps_notes_together():
    html = (
        "<html><head></head><body>"
        '<figure class="chart"><svg aria-label="chart"></svg>'
        '<table id="calendar-table"></table></figure><aside class="note">note</aside>'
        "</body></html>"
    )
    out = charts_to_text_summaries(html)
    assert "#calendar-table { font-size: 5pt; table-layout: fixed; width: 100%; }" in out
    assert ".note { break-inside: avoid; page-break-inside: avoid; }" in out


def test_pdf_preparation_uses_block_flow_instead_of_css_grid():
    html = "<style>dl.stats { display: grid; }</style><dl class='stats'><dt>x</dt><dd>y</dd></dl>"
    out = charts_to_text_summaries(html)
    assert "display: grid" not in out
    assert "display: block" in out


# ---------------------------------------------------------------------------
# Unavailable-extra handling
# ---------------------------------------------------------------------------


def test_pdf_export_unavailable_when_weasyprint_not_importable(monkeypatch):
    monkeypatch.setitem(sys.modules, "weasyprint", None)
    with pytest.raises(PdfExportUnavailable, match=r"pdf.*extra"):
        html_to_tagged_pdf_bytes("<html lang='en'><body><p>x</p></body></html>")


def test_pdf_export_blocks_all_external_resource_fetches(monkeypatch):
    class FetchingHtml:
        def __init__(self, *, string, url_fetcher):
            self.url_fetcher = url_fetcher

        def write_pdf(self, **_options):
            self.url_fetcher("https://example.invalid/tracker.png")
            return b"%PDF-fake"

    monkeypatch.setitem(sys.modules, "weasyprint", SimpleNamespace(HTML=FetchingHtml))
    with pytest.raises(TaggedPdfGenerationError, match="local-only guarantee"):
        html_to_tagged_pdf_bytes('<html lang="en"><body><img src="x"></body></html>')


# ---------------------------------------------------------------------------
# End-to-end generation: the primary report and the violations report both
# convert without raising -- this is the regression test for the verified
# WeasyPrint "Table wrapper without a table" crash (see report/pdf_export.py).
# ---------------------------------------------------------------------------


def test_main_report_with_events_converts_to_tagged_pdf():
    pdf_bytes = html_to_tagged_pdf_bytes(_main_report_html(with_events=True))
    assert pdf_bytes[:5] == b"%PDF-"


def test_empty_main_report_converts_to_tagged_pdf():
    pdf_bytes = html_to_tagged_pdf_bytes(_main_report_html(with_events=False))
    assert pdf_bytes[:5] == b"%PDF-"


def test_violations_report_converts_to_tagged_pdf():
    pdf_bytes = html_to_tagged_pdf_bytes(_violations_html())
    assert pdf_bytes[:5] == b"%PDF-"


def test_write_tagged_pdf_writes_file_and_returns_byte_count(tmp_path):
    out = tmp_path / "report.pdf"
    n = write_tagged_pdf(_violations_html(), out)
    assert out.exists()
    assert n == out.stat().st_size
    assert n > 0


# ---------------------------------------------------------------------------
# Structural properties: tag tree, language, marked status, reading order,
# table header association, chart-summary text survival.
# ---------------------------------------------------------------------------


def test_pdf_declares_the_requested_variant_language_and_marked_status():
    pdf_bytes = html_to_tagged_pdf_bytes(_main_report_html())
    assert PDF_VARIANT == "pdf/a-3a"
    _, root = _struct_tree(pdf_bytes)
    assert root.get("/Lang") == "en"
    mark_info = root.get("/MarkInfo")
    assert mark_info is not None
    assert bool(mark_info.get("/Marked")) is True


def test_pdf_has_a_struct_tree_root_with_a_document_element():
    pdf_bytes = html_to_tagged_pdf_bytes(_main_report_html())
    _, root = _struct_tree(pdf_bytes)
    struct_root = root.get("/StructTreeRoot")
    assert struct_root is not None
    tags = _walk_tags(struct_root)
    assert any(str(t.get("/S")) == "/Document" for t in tags)


def test_headings_appear_in_document_order():
    pdf_bytes = html_to_tagged_pdf_bytes(_main_report_html(with_events=True))
    _, root = _struct_tree(pdf_bytes)
    tags = _walk_tags(root.get("/StructTreeRoot"))
    heading_order = [str(t["/S"]) for t in tags if str(t.get("/S")) in ("/H1", "/H2")]
    assert heading_order, "no headings found in the tag tree"
    assert heading_order[0] == "/H1", "the report title must be the first heading"
    assert heading_order.count("/H1") == 1, "exactly one H1, matching the HTML report"
    assert heading_order.count("/H2") >= 5, "expected the report's usual H2 sections"


def test_tables_have_header_cells_with_ids_and_data_cells_reference_them():
    pdf_bytes = html_to_tagged_pdf_bytes(_main_report_html(with_events=True))
    _, root = _struct_tree(pdf_bytes)
    tags = _walk_tags(root.get("/StructTreeRoot"))
    table_count = sum(1 for t in tags if str(t.get("/S")) == "/Table")
    th_count = sum(1 for t in tags if str(t.get("/S")) == "/TH")
    td_with_headers = sum(1 for t in tags if str(t.get("/S")) == "/TD" and t.get("/A") is not None)
    assert table_count >= 2, "expected multiple tables (by-hour, by-day, event types)"
    assert th_count > 0, "expected tagged header cells"
    assert td_with_headers > 0, "expected data cells associated with a header via /A"


def test_chart_summary_text_survives_as_real_content():
    # The by-hour chart's SVG carries an aria-label like "Events by hour of day. 24
    # bars. ..." -- charts_to_text_summaries() turns that into a tagged <p>, which
    # should now be extractable text in the PDF (unlike the SVG aria-label, which a
    # separate check found WeasyPrint does not carry into /Alt at all).
    pdf_bytes = html_to_tagged_pdf_bytes(_main_report_html(with_events=True))
    reader, _ = _struct_tree(pdf_bytes)
    full_text = "\n".join(page.extract_text() for page in reader.pages)
    assert "Events by hour of day" in full_text
    assert "24 bars" in full_text


def test_formerly_failing_two_day_report_converts_to_tagged_pdf():
    """Chart-wrapper flattening covers the page-layout shape that used to crash."""
    pdf_bytes = html_to_tagged_pdf_bytes(_main_report_html(with_events=True, num_days=2))
    assert pdf_bytes[:5] == b"%PDF-"


def test_violations_report_has_no_chart_summaries_but_still_tags_its_table():
    # The violations report has no charts at all, so charts_to_text_summaries()
    # should be a no-op on it, and its one big events table should still tag.
    pdf_bytes = html_to_tagged_pdf_bytes(_violations_html())
    _, root = _struct_tree(pdf_bytes)
    tags = _walk_tags(root.get("/StructTreeRoot"))
    assert any(str(t.get("/S")) == "/Table" for t in tags)
    assert not any("chart-summary" in str(t) for t in tags)


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------


def _events():
    return [
        Event(1_767_312_000.0, 1_767_312_004.0, 4.0, -8.0, -12.0, coarse_tag="bark-like"),
        Event(1_767_315_600.0, 1_767_315_601.5, 1.5, -20.0, -24.0),
    ]


def test_cli_pdf_flag_writes_a_tagged_pdf(tmp_path, capsys):
    from report.render import main as report_main
    from store import EventStore

    db = tmp_path / "olive.db"
    with EventStore(db) as store:
        for ev in _events():
            store.add_event(ev)
    out_html = tmp_path / "r.html"
    out_pdf = tmp_path / "r.pdf"
    rc = report_main(
        [
            "--db",
            str(db),
            "--out",
            str(out_html),
            "--pdf",
            str(out_pdf),
            "--generated-at",
            "2026-01-01 UTC",
        ]
    )
    assert rc == 0
    assert out_pdf.exists()
    assert out_pdf.read_bytes()[:5] == b"%PDF-"
    assert "tagged PDF/A-3a" in capsys.readouterr().out


def test_cli_violations_pdf_flag_writes_a_tagged_pdf(tmp_path):
    from report.render import main as report_main
    from store import EventStore

    db = tmp_path / "olive.db"
    with EventStore(db) as store:
        for ev in _events():
            store.add_event(ev)
    out_html = tmp_path / "r.html"
    out_pdf = tmp_path / "violations.pdf"
    rc = report_main(
        [
            "--db",
            str(db),
            "--out",
            str(out_html),
            "--violations-pdf",
            str(out_pdf),
            "--generated-at",
            "2026-01-01 UTC",
        ]
    )
    assert rc == 0
    assert out_pdf.exists()
    assert out_pdf.read_bytes()[:5] == b"%PDF-"


def test_taggedpdfgenerationerror_is_importable_and_is_a_runtime_error():
    # Regression guard: report/render.py's CLI catches this by name.
    assert issubclass(TaggedPdfGenerationError, RuntimeError)


def test_cli_pdf_flag_fails_loudly_not_silently_when_export_unavailable(
    tmp_path, monkeypatch, capsys
):
    # If the 'pdf' extra is missing (or WeasyPrint's tagging crashes), the CLI must
    # report a real failure -- exit 1 with an explanation -- never silently produce
    # a non-tagged file while claiming success. Simulated here via monkeypatch
    # rather than actually uninstalling weasyprint, since this test file already
    # requires it to be present.
    import report.pdf_export as pdf_export
    from report.render import main as report_main
    from store import EventStore

    def boom(html, path):
        raise pdf_export.PdfExportUnavailable("simulated: extra not installed")

    monkeypatch.setattr(pdf_export, "write_tagged_pdf", boom)

    db = tmp_path / "olive.db"
    with EventStore(db) as store:
        for ev in _events():
            store.add_event(ev)
    rc = report_main(
        [
            "--db",
            str(db),
            "--out",
            str(tmp_path / "r.html"),
            "--pdf",
            str(tmp_path / "r.pdf"),
            "--generated-at",
            "2026-01-01 UTC",
        ]
    )
    assert rc == 1
    assert "Skipped" in capsys.readouterr().out
    assert not (tmp_path / "r.pdf").exists()


def test_cli_violations_pdf_flag_fails_loudly_on_tagging_error(tmp_path, monkeypatch, capsys):
    import report.pdf_export as pdf_export
    from report.render import main as report_main
    from store import EventStore

    def boom(html, path):
        raise pdf_export.TaggedPdfGenerationError("simulated: WeasyPrint tagging crash")

    monkeypatch.setattr(pdf_export, "write_tagged_pdf", boom)

    db = tmp_path / "olive.db"
    with EventStore(db) as store:
        for ev in _events():
            store.add_event(ev)
    rc = report_main(
        [
            "--db",
            str(db),
            "--out",
            str(tmp_path / "r.html"),
            "--violations-pdf",
            str(tmp_path / "violations.pdf"),
            "--generated-at",
            "2026-01-01 UTC",
        ]
    )
    assert rc == 1
    assert "Skipped" in capsys.readouterr().out
    assert not (tmp_path / "violations.pdf").exists()
