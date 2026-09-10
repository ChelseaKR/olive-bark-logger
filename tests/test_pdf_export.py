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


# ---------------------------------------------------------------------------
# The gate must hold for a report of any length, not only this one
# ---------------------------------------------------------------------------

#: The filler lengths the caption rule was measured over on 2026-09-06 (see
#: ``report/pdf_export.py``'s module docstring): the positive gate holds at all of them.
FILLER_SWEEP = (0, 1, 5, 20, 60)

#: The negative control's search space: every whole-paragraph offset up to a full extra
#: page of prose. It is a search and not a fixture because whether a given length crashes
#: without the caption rule is a fact about where a table happens to land on a page, not
#: about the rule. A control pinned to one length stops proving anything the first time
#: anyone adds a paragraph -- measured 2026-09-06, when adding one table to the report
#: moved every one of :data:`FILLER_SWEEP` out of the crashing shape at once.
CONTROL_SWEEP = tuple(range(60))


def _padded_report(extra_paragraphs: int) -> str:
    """The main report with `extra_paragraphs` filler paragraphs above its first table."""
    html = _main_report_html(with_events=True)
    filler = "<p>filler line</p>" * extra_paragraphs
    padded = html.replace(
        "<h2>Measurement conditions</h2>", f"<h2>Measurement conditions</h2>\n{filler}", 1
    )
    assert padded != html or extra_paragraphs == 0, "the filler was not injected"
    return padded


@pytest.mark.parametrize("extra_paragraphs", FILLER_SWEEP)
def test_the_tagged_pdf_survives_a_longer_report(extra_paragraphs):
    """Adding content to the report must not decide whether the PDF gate passes.

    Measured on 2026-09-06: before `caption { break-after: avoid }` was added to
    `_PDF_LAYOUT_STYLE`, this parametrization failed at 0, 1, 5 and 20 extra
    paragraphs and passed at 60. The verdict tracked nothing but where a table
    happened to land on a page, so the suite was green at exactly the report's
    own length and any edit to it was a coin flip.

    A gate whose result depends on how much prose sits above a table is not
    measuring what it claims to. This pins the property instead of the fixture.
    """
    pdf_bytes = html_to_tagged_pdf_bytes(_padded_report(extra_paragraphs))
    assert pdf_bytes[:5] == b"%PDF-"


def _weasyprint_major() -> int:
    """The installed WeasyPrint's major version, refusing anything it cannot read.

    The control below asks a different question of 67-69 than of 70+, so a version it
    misparses would silently take one of the two branches and prove nothing.
    """
    from report.pdf_export import _weasyprint

    raw = str(_weasyprint().__version__)
    major = raw.split(".", 1)[0]
    assert major.isdigit(), f"cannot read a major version out of WeasyPrint {raw!r}"
    return int(major)


def test_the_caption_keep_together_rule_is_the_one_doing_the_work():
    """The negative control for the rule above, run in-process -- with the version split
    upstream forced on 2026-09-08.

    Removing `caption { break-after: avoid }` from the injected style must bring the
    crash back somewhere in :data:`FILLER_SWEEP` -- the same family of report lengths
    the positive gate holds over. **On WeasyPrint 70.0 and later it must not**, because
    upstream fixed the bug the rule works around: Kozea/WeasyPrint#2761, titled
    `ValueError: Table wrapper without a table` in those words, is closed and listed in
    70.0's bug fixes as "Handle split tables with captions".

    Both halves are assertions, and neither is a skip. On 67-69 the rule is still
    load-bearing and this proves it; on 70+ the rule is inert and this proves *that*,
    so a regression that brought the crash back would fail here rather than pass
    quietly. The rule itself stays in `_PDF_LAYOUT_STYLE` because the `pdf` extra still
    admits `>=67`; retiring it needs the floor to move, which is ADR-0004's question and
    not a test's.

    This is what the cap at `<70` was for. The control found the change on the first CI
    run after the bound was widened, and its own failure message named both readings --
    dead code, or a sweep that stopped producing the crashing shape. The upstream
    changelog is what tells the two apart; the sweep could not.

    It searches :data:`CONTROL_SWEEP` for a crashing length rather than asserting one.
    Until 2026-09-06 it asserted the crash at the report's own length alone, and which
    length crashes is a fact about pagination rather than about the rule: the module
    docstring's own measurement has the unfixed code crashing at 0, 1, 5 and 20 filler
    paragraphs and *passing* at 60. Measured the same day, adding a single table to the
    report (the quiet-hours duration rollup) moved 0, 1, 5, 20 *and* 60 out of the
    crashing shape together -- a five-length control would have gone quietly green too.
    The claim worth holding is that the rule is load-bearing *somewhere* in the family
    of report lengths, so that is what is searched for, and the search stops at the
    first hit.
    """
    from report import pdf_export

    weakened = pdf_export._PDF_LAYOUT_STYLE.replace(
        "caption { break-after: avoid; page-break-after: avoid; }\n", ""
    )
    assert weakened != pdf_export._PDF_LAYOUT_STYLE, "the sabotage did not land"

    original = pdf_export._PDF_LAYOUT_STYLE
    pdf_export._PDF_LAYOUT_STYLE = weakened
    crashed: int | None = None
    try:
        for extra_paragraphs in CONTROL_SWEEP:
            try:
                html_to_tagged_pdf_bytes(_padded_report(extra_paragraphs))
            except TaggedPdfGenerationError as exc:
                assert "Table wrapper without a table" in str(exc)
                crashed = extra_paragraphs
                break
    finally:
        pdf_export._PDF_LAYOUT_STYLE = original

    major = _weasyprint_major()
    if major >= 70:
        assert crashed is None, (
            f"WeasyPrint {major}.x reintroduced `Table wrapper without a table` at "
            f"{crashed} filler paragraph(s) with the caption rule removed. Upstream "
            "Kozea/WeasyPrint#2761 was fixed in 70.0; this is a regression, and the "
            "caption rule in _PDF_LAYOUT_STYLE is load-bearing again on this version."
        )
        # The rule is inert here, so the length-sweep property is asserted the only way
        # left: the report still converts at a length the sweep covers, with the rule
        # restored. Without this the >=70 branch would assert only an absence.
        assert html_to_tagged_pdf_bytes(_padded_report(CONTROL_SWEEP[-1]))[:5] == b"%PDF-"
        return

    assert crashed is not None, (
        "removing `caption { break-after: avoid }` changed nothing at any of the "
        f"{len(CONTROL_SWEEP)} filler lengths in CONTROL_SWEEP on WeasyPrint "
        f"{major}.x, which is below the 70.0 that fixed Kozea/WeasyPrint#2761. So this "
        "control no longer shows the rule is load-bearing. Either the crash needs a "
        "page shape this sweep stopped producing and the sweep needs widening, or the "
        "fix was backported -- do not delete the control to get green."
    )

    # And with the rule restored, the length that crashed without it converts: the
    # control is about the rule, not about the fixture having become unconvertible.
    # This is also the only positive assertion at a length where the rule demonstrably
    # matters; FILLER_SWEEP's five are wherever the 2026-09-06 measurement left them.
    assert html_to_tagged_pdf_bytes(_padded_report(crashed))[:5] == b"%PDF-"
