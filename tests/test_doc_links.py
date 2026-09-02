"""Merge-blocking: a document may not point at a file or a heading that is not there.

Nothing in this repository read a link. `docs/DOCUMENTATION-AUDIT.md` asserts "All
authored-doc relative links checked after rebase; 0 unresolved" and "24 root-level/template
links checked; 0 unresolved" -- both hand counts, from one afternoon, never re-run. In the
meantime:

* three README links into `docs/GAP-LEDGER.md` carried anchors that no longer matched the
  headings they pointed at (`#gap-obs-1--...-tier-c-structlog-reference-implementation`
  twice, and `#gap-sec-1--...-lockfileosv-scanner-...` once). A GitHub anchor that does not
  match silently lands the reader at the top of the file, so nothing looked broken;
* `.github/workflows/ci.yml` cited the WeasyPrint ADR under its pre-rename `0003-`
  filename for over a month after `7fe55bb` renamed that file to `0004-`. Thirteen other
  references in the tree were updated. The one inside a YAML comment was not, because no
  link checker existed and a comment is not a link.

Two scanners, matching those two shapes:

1. **Markdown links.** Every `[text](target)` in a tracked `.md` file: the file resolves,
   and if the target carries a `#fragment`, a heading in the destination slugifies to it.
   Inline code spans are removed first (`md_link_targets`), because Markdown renders no
   link inside backticks and this scanner read one there: a changelog entry quoting a
   regex was told to add the file it "linked" to. Removing the span rather than skipping
   the whole line keeps the target of a code-labelled link -- the house style here --
   checked.
2. **Bare in-repo paths.** Every `path/to/file.ext` mentioned in tracked Markdown, YAML,
   Python, or the Makefile resolves. This is the half that catches a stale citation in a
   comment, which is where the ADR rename hid.

The one escape from (2) is the marker `link-check: historical` on the same line, for the
places that must name a path precisely *because* it is gone -- a canary below, and a
record of a defect that was fixed. It is deliberately a single greppable string with no
pattern argument, so every use is visible in one `grep` and none of them can be broad.
Using it to silence a live reference would be the same defect this file exists to catch.

`slugify` implements GitHub's heading-anchor algorithm; `test_slugify_matches_github`
pins it against headings taken verbatim out of this repository's own files, so the rule
is checked against real data rather than asserted.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from conftest import ROOT

# Extensions worth scanning for bare path citations. Text a human wrote about the repo.
SCANNED_SUFFIXES = {".md", ".yml", ".yaml", ".py", ".toml", ".cff", ".json"}
SCANNED_NAMES = {"Makefile", "Dockerfile"}

# `docs/ideation/` is a proposals folder: its "Shape:" lines name modules an idea *would*
# add (an `interchange.py` under `report/`, and friends), which by construction do not
# exist yet. Those are design sketches, not citations, so they are out of scope for the
# bare-path scan. Their markdown links are still checked -- a proposal may invent a
# module, not a broken link.
PROPOSAL_DIRS = (ROOT / "docs" / "ideation",)

# A bare in-repo path citation: at least one directory segment, then a filename with a
# known extension. Anchored on a directory so prose like "report.html" (a generated
# artifact, not a tracked file) is not swept in.
BARE_PATH = re.compile(
    r"(?<![\w./-])"
    r"((?:\.github|docs|tests|scripts|monitor|report|store|pwa|spec|deploy)"
    r"(?:/[\w.-]+)*"
    r"/[\w.-]+\.(?:md|py|json|yml|yaml|mjs|js|html|toml|cff|sh|service|webmanifest))"
)

# `[text](target)` -- non-greedy, and it tolerates one level of nested brackets in the
# label (`[`code`](x)` and `[GAP-A11Y-1](y)` both appear in this repo).
MD_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")

# An inline code span: a run of backticks, the shortest span closed by an equal run.
# Markdown does not render links inside one, and neither does this scanner -- see
# `md_link_targets`.
CODE_SPAN = re.compile(r"(`+)(?:(?!\1).)*?\1", re.DOTALL)

# Targets that are not repository paths.
EXTERNAL = re.compile(r"^(https?:|mailto:|#|\.\./STANDARDS)")

# The single, deliberate escape hatch for the bare-path scan: a line that names a path
# precisely because it no longer exists. See the module docstring.
HISTORICAL = "link-check: historical"


def tracked_files() -> list[Path]:
    """Every file git tracks. Untracked scratch files are not published claims."""
    out = subprocess.run(  # fixed argv, no shell, repo-local
        ["git", "ls-files", "-z"],  # noqa: S607 - git resolved from PATH by design
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [ROOT / name for name in out.stdout.split("\0") if name]


def scanned_files() -> list[Path]:
    return [
        p
        for p in tracked_files()
        if (p.suffix in SCANNED_SUFFIXES or p.name in SCANNED_NAMES)
        and p.is_file()
        and not any(d in p.parents for d in PROPOSAL_DIRS)
    ]


def markdown_files() -> list[Path]:
    return [p for p in tracked_files() if p.suffix == ".md" and p.is_file()]


def md_link_targets(line: str) -> list[str]:
    """Link targets on one line of Markdown, ignoring anything inside a code span.

    `MD_LINK` alone reads `[...](...)` wherever the characters occur, including inside
    backticks -- where Markdown renders no link at all. That is not hypothetical: this
    repository's own changelog quotes the regex an earlier defect used, which contains a
    character class immediately followed by a group, and the scanner demanded a file be
    added for it. A gate that a truthful sentence cannot pass is a false-failure trap,
    the same shape as the unanchored import regex in issue #68 -- and worse here, because
    the pressure it creates is to reword the document rather than fix the check.

    Code spans are removed rather than skipped over, so a real link whose *label* is code
    -- ``[`monitor/features.py`](../monitor/features.py)``, which this repository writes
    often -- still has its target checked; only the label goes.
    """
    return MD_LINK.findall(CODE_SPAN.sub("", line))


def slugify(heading: str) -> str:
    """GitHub's heading-anchor algorithm.

    Strip the leading `#`s, drop inline markup, lowercase, delete everything that is not
    a word character, a space or a hyphen, then turn spaces into hyphens. Runs of spaces
    become runs of hyphens, which is why `GAP-QM-1 - Quality` yields a double hyphen.
    """
    text = re.sub(r"^#+\s*", "", heading.strip())
    text = re.sub(r"<[^>]+>", "", text)  # inline HTML
    text = text.replace("`", "").replace("*", "").replace("_", "")
    # A markdown link inside a heading contributes only its label.
    text = MD_LINK.sub(lambda m: m.group(0).split("]")[0][1:], text)
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    return text.strip().replace(" ", "-")


def anchors_in(path: Path) -> set[str]:
    """Every fragment a reader can land on in this file: heading slugs, plus explicit
    `<a name=...>` / `id=...` targets if any are ever added."""
    text = path.read_text(encoding="utf-8")
    slugs: set[str] = set()
    seen: dict[str, int] = {}
    in_fence = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not line.startswith("#"):
            continue
        slug = slugify(line)
        if not slug:
            continue
        # GitHub disambiguates a repeated heading as `slug-1`, `slug-2`, ...
        count = seen.get(slug, 0)
        slugs.add(slug if count == 0 else f"{slug}-{count}")
        seen[slug] = count + 1
    slugs |= set(re.findall(r'(?:name|id)="([\w-]+)"', text))
    return slugs


# --- 1. markdown links resolve, anchors included -------------------------------------


def test_every_markdown_link_resolves_to_a_file():
    broken: list[str] = []
    for path in markdown_files():
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for target in md_link_targets(line):
                if EXTERNAL.match(target):
                    continue
                dest = (path.parent / target.split("#")[0]).resolve()
                if not dest.exists():
                    rel = path.relative_to(ROOT)
                    broken.append(f"{rel}:{lineno} -> {target}")
    assert not broken, "markdown links pointing at files that do not exist:\n" + "\n".join(broken)


def test_every_markdown_anchor_matches_a_real_heading():
    """The failure that hides: GitHub drops an unmatched anchor and shows the top of the
    file, so a wrong `#fragment` reads as a working link forever."""
    broken: list[str] = []
    for path in markdown_files():
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for target in md_link_targets(line):
                if EXTERNAL.match(target) or "#" not in target:
                    continue
                file_part, _, fragment = target.partition("#")
                dest = (path.parent / file_part).resolve() if file_part else path
                if not dest.exists() or dest.suffix != ".md":
                    continue
                if fragment not in anchors_in(dest):
                    rel = path.relative_to(ROOT)
                    broken.append(f"{rel}:{lineno} -> {target}")
    assert not broken, (
        "markdown anchors that match no heading (GitHub silently lands the reader at the "
        "top of the file, so these look fine in a browser):\n" + "\n".join(broken)
    )


def test_a_code_span_is_not_read_as_a_link_and_a_code_label_still_is():
    """Both halves of `md_link_targets`, against the sentence that exposed the first.

    The left column is text this repository actually writes. Before code spans were
    stripped, the first row made `test_every_markdown_link_resolves_to_a_file` demand a
    file named after a regex fragment -- a truthful changelog entry the gate could not
    pass, whose only cheap fix was to reword the document. The last two rows are the
    reason stripping is not the same as skipping the line: a link whose *label* is code
    is the repository's house style, and its target must still be checked.
    """
    cases = [
        (r'the pattern `/from\s+["\'](\./[^"\']+)["\']/g` matched the bare word', []),
        ("`[GAP-A11Y-1](notes/nope.md)` is quoted, not linked", []),
        (
            "[`monitor/features.py`](../monitor/features.py) is a real link",
            ["../monitor/features.py"],
        ),
        ("[plain](./a.md) and `code` and [second](./b.md)", ["./a.md", "./b.md"]),
    ]
    for line, expected in cases:
        assert md_link_targets(line) == expected, line
    # And the raw pattern still sees the quoted regex, so the difference is the stripping
    # and not a line that happened to stop matching for some other reason.
    assert MD_LINK.findall(cases[0][0])


# --- 2. bare in-repo path citations resolve ------------------------------------------


def test_every_in_repo_path_citation_resolves():
    """The half that catches a stale path in a comment. `ci.yml` cited a renamed ADR for
    a month because a YAML comment is not a link and nothing else read it."""
    broken: list[str] = []
    for path in scanned_files():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:  # pragma: no cover - no such file today
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if HISTORICAL in line:
                continue
            for cited in BARE_PATH.findall(line):
                if (ROOT / cited).exists():
                    continue
                rel = path.relative_to(ROOT)
                broken.append(f"{rel}:{lineno} -> {cited}")
    assert not broken, "in-repo paths cited in tracked files that do not exist:\n" + "\n".join(
        broken
    )


# --- canaries: prove both scanners bite ----------------------------------------------


def test_slugify_matches_github(tmp_path):
    """Pinned against headings copied verbatim from this repo's own files, with the
    anchors the README links to. If this drifts, every anchor check above is noise."""
    cases = {
        "## GAP-OBS-1 — Observability: `--log-format json`": (
            "gap-obs-1--observability---log-format-json"
        ),
        "## GAP-SEC-1 — Security & Supply-Chain: harden-runner block-mode, CodeQL, "
        "osv-scanner, TruffleHog, SBOM+signing, Scorecard": (
            "gap-sec-1--security--supply-chain-harden-runner-block-mode-codeql-osv-scanner"
            "-trufflehog-sbomsigning-scorecard"
        ),
        "## GAP-A11Y-2 — Accessibility: tagged PDF/A export (EXP-06) has no human AT "
        "walkthrough or veraPDF CI gate": (
            "gap-a11y-2--accessibility-tagged-pdfa-export-exp-06-has-no-human-at-walkthrough"
            "-or-verapdf-ci-gate"
        ),
        "## Standards Conformance": "standards-conformance",
        "## Local status page": "local-status-page",
    }
    for heading, expected in cases.items():
        assert slugify(heading) == expected, heading


def test_the_anchor_scanner_flags_a_planted_broken_anchor(tmp_path):
    dest = tmp_path / "DEST.md"
    dest.write_text("# Real Heading\n\ncontent\n", encoding="utf-8")
    assert anchors_in(dest) == {"real-heading"}
    assert "not-a-heading" not in anchors_in(dest)


def test_the_path_scanner_flags_a_planted_stale_path():
    """The exact defect: a renamed ADR still cited in a comment."""
    stale = "docs/adr/0003-weasyprint-for-tagged-pdf-a-export.md"  # link-check: historical
    line = f"#     {stale}). Structural-only gate"  # link-check: historical
    assert BARE_PATH.findall(line) == [stale]
    assert not (ROOT / stale).exists(), "the plant must be a path that really is absent"
    # ...and it must find the correct one too, or the scanner is just noise.
    real = BARE_PATH.findall("see docs/adr/0004-weasyprint-for-tagged-pdf-a-export.md.")
    assert real == ["docs/adr/0004-weasyprint-for-tagged-pdf-a-export.md"]
    assert (ROOT / real[0]).exists()


def test_the_historical_marker_is_narrow_and_used_sparingly():
    """The escape hatch is only safe while it stays visible and rare. Assert both halves:
    a line without the marker is still flagged, and every use in the tree is countable."""
    plain = "cites docs/adr/0003-weasyprint-for-tagged-pdf-a-export.md"  # link-check: historical
    assert HISTORICAL not in plain and BARE_PATH.findall(plain), (
        "premise: this line names an absent path and carries no marker"
    )
    uses = [
        f"{p.relative_to(ROOT)}:{n}"
        for p in scanned_files()
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
        if HISTORICAL in line
    ]
    assert len(uses) <= 6, (
        f"the historical-path escape is spreading ({len(uses)} uses): {uses}. It exists "
        "for a canary and a fixed-defect record, not as a way past a live broken citation."
    )
