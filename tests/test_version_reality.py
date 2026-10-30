"""The version this project declares, held against the releases it actually has.

`pyproject.toml` is the single source of the version (REL-02). Until 2026-09-06 it
declared `0.1.0` while `git tag` listed nothing at all -- a number published as though it
meant something, with no artifact behind it. GAP-REL-1 and the CHANGELOG both recorded
that in prose, and the prose was right; what was missing is that nothing checked it. The
same paragraph names the earlier form of this defect: `CITATION.cff` once carried
`date-released: 2026-06-30` for a release that never happened.

Three states are legitimate, and anything else is a defect:

* **Development** -- no tags at all, and the declared version says so in a form a tool
  can read (a PEP 440 ``.devN`` suffix, which sorts below the release it anticipates)
  *and* the documents a reader opens say so too. If nothing says it, the silence is the
  finding.
* **Prepared** -- the declared version is a bare ``X.Y.Z`` that no tag carries yet,
  newer than every tag that exists, beside exactly one dated ``## [X.Y.Z] - YYYY-MM-DD``
  heading in `CHANGELOG.md` and a `CITATION.cff` with the same version and the same date.
  This state exists because the commit that gets tagged is written, reviewed and merged
  before the tag can point at it, and `release.yml` (REL-14) refuses a tag that does not
  equal the declared version exactly -- so that commit can be in neither of the other two.
* **Released** -- a tag equals the declared version, and the dated heading's date is the
  day that annotated tag records.

**Tags exist and none matches the declared version**, outside the prepared state, is a
defect. The failure names the declared version and the newest tag, because "they
disagree" is not actionable without both numbers. So is a dated heading for a version that
is neither tagged nor the one being prepared: that is the phantom release, whatever number
it is written under.

What this suite cannot see is time. A release that is prepared and never tagged stays
green here; it is visible only as GAP-REL-1's "no tag cut yet" and as a missing GitHub
Release.

The tag-dependent branches are unreachable from this repository today, so they are driven
below against synthetic tag lists. The mismatch branch was proved end to end against a
throwaway clone of this repository carrying real `v9.9.9` and `v0.0.1` tags, and the
released branch against one carrying a real annotated `v0.1.0` tag, dated first on the
heading's day and then on another. They are never proved by tagging this repository: no
automation here may mint a tag.
"""

from __future__ import annotations

import datetime
import re
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest
from monitor import __version__ as PACKAGE_VERSION

ROOT = Path(__file__).resolve().parent.parent

#: PEP 440 developmental release. `0.1.0.dev0` is not `0.1.0`, and pip, `packaging`, and
#: an SBOM consumer all read the suffix as "this is not the release it is named after".
DEV_SUFFIX = re.compile(r"\.dev\d+$")

#: What the shared release authorizer accepts after the `v` (stable SemVer, no suffix).
STABLE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")

#: A release heading exactly as `release.yml`'s `awk` step finds it: at column 0, with the
#: `index($0, "## [" ver "]") == 1` prefix, then the Keep a Changelog date.
RELEASE_HEADING = re.compile(r"^## \[([^\]]+)\] - (.*)$", re.MULTILINE)

#: Any other line that tries to be a version heading -- indented (markdown still renders it,
#: `awk` no longer finds it) or undated. `[Unreleased]` is the one undated heading allowed.
LOOSE_HEADING = re.compile(r"^ {0,3}## \[(?!Unreleased\])[^\n]*$", re.MULTILINE)

#: Read with a regex rather than `tomllib`. Written while the floor was 3.9, before `tomllib`
#: (3.11+) was available; the floor is 3.11 now (docs/adr/0032) and the regex still works.
_PYPROJECT_VERSION = re.compile(r'^version = "([^"]+)"$', re.MULTILINE)


def declared_version(root: Path = ROOT) -> str:
    """The one source of truth for this project's version."""

    text = (root / "pyproject.toml").read_text(encoding="utf-8")
    matches = _PYPROJECT_VERSION.findall(text)
    assert len(matches) == 1, f"expected exactly one version declaration, found {matches}"
    return str(matches[0])


def repository_tags(root: Path = ROOT) -> list[str]:
    """Every tag this checkout can see. Empty means "none visible", not "none exist"."""

    result = subprocess.run(  # noqa: S603 - fixed argv, no shell
        ["git", "-C", str(root), "tag", "--list"],  # noqa: S607 - git is the tool
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def is_shallow(root: Path = ROOT) -> bool:
    """Whether this checkout was truncated -- an empty tag list then proves nothing."""

    result = subprocess.run(  # noqa: S603 - fixed argv, no shell
        ["git", "-C", str(root), "rev-parse", "--is-shallow-repository"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() == "true"


def remote_tags(root: Path = ROOT) -> list[str] | None:
    """The tags the remote actually has, or None when the remote could not be asked.

    The local list is only as complete as the fetch that produced it: `actions/checkout`
    fetches no tags unless asked, so a gate reading `git tag` off a default checkout
    answers "none" whatever the truth is, and passes blind. `git ls-remote` is the
    authoritative answer, and it goes over the git protocol -- it costs no GitHub API
    quota at all.
    """

    result = subprocess.run(  # noqa: S603 - fixed argv, no shell
        [  # noqa: S607 - git is the tool
            "git",
            "-C",
            str(root),
            "ls-remote",
            "--tags",
            "--refs",
            "origin",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    if result.returncode != 0:
        return None
    return sorted(
        line.rsplit("refs/tags/", 1)[-1]
        for line in result.stdout.splitlines()
        if "refs/tags/" in line
    )


def tag_dates(root: Path = ROOT) -> dict[str, str]:
    """Each annotated tag's date, in the tagger's own time zone (`taggerdate:short`).

    A lightweight tag has no tagger and is left out; the shared release authorizer refuses
    one anyway, so it can never be the tag a release is cut from.
    """

    result = subprocess.run(  # noqa: S603 - fixed argv, no shell
        [  # noqa: S607 - git is the tool
            "git",
            "-C",
            str(root),
            "for-each-ref",
            "refs/tags",
            "--format=%(refname:short) %(taggerdate:short)",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return {}
    dates = {}
    for line in result.stdout.splitlines():
        name, _, date = line.strip().partition(" ")
        if date:
            dates[name] = date
    return dates


def strip_v(tag: str) -> str:
    return tag[1:] if tag.startswith("v") else tag


def _numeric(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", strip_v(version)))


def newest_tag(tags: Sequence[str]) -> str:
    """The highest tag by numeric components, ties broken by name.

    Deliberately not `--sort=-creatordate`: a tag re-cut later would then read as newer
    than the release it replaced, and a shallow fetch may not carry creator dates at all.
    """

    def key(tag: str) -> tuple[tuple[int, ...], str]:
        return _numeric(tag), tag

    return max(tags, key=key)


def is_tagged(version: str, tags: Sequence[str]) -> bool:
    return any(strip_v(tag) == version for tag in tags)


def version_against_tags(
    declared: str, tags: Sequence[str], *, prepared: bool = False
) -> str | None:
    """The finding, or None when the declared version is answerable to the tags.

    `prepared` is whether `CHANGELOG.md` carries a dated heading for `declared`. It lets a
    bare, untagged version through only when that version is newer than every tag: a
    prepared release can run ahead of what was released, never behind it.
    """

    if not tags:
        return None
    if is_tagged(declared, tags):
        return None
    if prepared and STABLE.match(declared) and _numeric(declared) > _numeric(newest_tag(tags)):
        return None
    return (
        f"pyproject.toml declares version {declared!r}, and none of the {len(tags)} tag(s) in "
        f"this repository matches it. The newest tag is {newest_tag(tags)!r}. Either a release "
        "was cut without bumping the declared version, or the declared version has run ahead "
        "of what was released and should carry a PEP 440 '.devN' suffix until it is tagged."
    )


def changelog_release_headings(root: Path = ROOT) -> list[tuple[str, str]]:
    """Every `## [version] - date` heading `release.yml` could extract, in file order."""

    text = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    return [(version, date.strip()) for version, date in RELEASE_HEADING.findall(text)]


def is_prepared(root: Path, declared: str) -> bool:
    """A bare version with a dated CHANGELOG heading for it: a release written down."""

    return bool(STABLE.match(declared)) and any(
        version == declared for version, _ in changelog_release_headings(root)
    )


def _is_iso_date(value: str) -> bool:
    try:
        datetime.date.fromisoformat(value)
    except ValueError:
        return False
    return re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) is not None


def _declared_heading_findings(
    headings: Sequence[tuple[str, str]], declared: str, dates: Mapping[str, str]
) -> list[str]:
    """A bare declared version is a release written down: one heading, newest, on its day."""

    if not STABLE.match(declared):
        return []
    mine = [date for version, date in headings if version == declared]
    if len(mine) != 1:
        return [
            f"pyproject.toml declares the bare version {declared!r}, so CHANGELOG.md needs "
            f"exactly one '## [{declared}] - YYYY-MM-DD' heading; it has {len(mine)}. "
            "release.yml publishes that section as the release notes and fails without it."
        ]
    if headings[0][0] != declared:
        return [
            f"CHANGELOG.md's newest dated heading is {headings[0][0]!r}, not the declared "
            f"{declared!r}."
        ]
    tag_date = next((date for tag, date in dates.items() if strip_v(tag) == declared), None)
    if tag_date is not None and tag_date != mine[0]:
        return [
            f"CHANGELOG.md dates {declared!r} {mine[0]}, but its tag records {tag_date}. "
            "The heading and CITATION.cff's date-released must name the day the tag was signed."
        ]
    return []


def changelog_heading_findings(
    root: Path,
    declared: str,
    tags: Sequence[str],
    dates: Mapping[str, str] | None = None,
) -> list[str]:
    """Dated headings name releases. Each must be tagged, or be the one being prepared.

    `dates` maps tag name to the day the annotated tag records; when the declared version is
    tagged, its heading must carry that day. A release cut on another day than the one its
    notes give is the same defect as a date for a release that never happened, only smaller.
    """

    text = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    headings = changelog_release_headings(root)
    findings = []

    strict = {match.group(0) for match in RELEASE_HEADING.finditer(text)}
    for match in LOOSE_HEADING.finditer(text):
        line = match.group(0)
        if line not in strict:
            findings.append(
                f"CHANGELOG.md has {line.strip()!r}, which is not a '## [X.Y.Z] - YYYY-MM-DD' "
                "heading at column 0, the only form release.yml's awk step extracts (REL-10)."
            )

    for version, date in headings:
        if not _is_iso_date(date):
            findings.append(f"CHANGELOG.md's '## [{version}]' heading has no ISO date: {date!r}.")
        if not STABLE.match(version):
            findings.append(
                f"CHANGELOG.md has a dated heading for {version!r}, which is not a stable "
                "X.Y.Z; the release authorizer refuses any other tag."
            )
        elif not is_tagged(version, tags) and version != declared:
            findings.append(
                f"CHANGELOG.md dates a release of {version!r}, but no tag carries it and "
                f"pyproject.toml declares {declared!r}: a heading for a release that has not "
                "happened and is not being prepared."
            )

    return findings + _declared_heading_findings(headings, declared, dates or {})


#: Where a reader is told, in prose, that nothing has been released. Required while the
#: version is a development one and there are no tags; retired by the commit that prepares
#: the first release, which is the commit that gets tagged -- both directions gated.
UNRELEASED_STATEMENTS: tuple[tuple[str, str], ...] = (
    ("README.md", r"no version has been tagged or released yet"),
    ("CHANGELOG.md", r"No version of this project has been tagged or released yet"),
)


def unreleased_statement_findings(
    root: Path, tags: Sequence[str], declared: str | None = None
) -> list[str]:
    """`declared` defaults to the tree's own; the controls below drive the other states."""

    developing = DEV_SUFFIX.search(declared or declared_version(root)) is not None
    findings = []
    for name, pattern in UNRELEASED_STATEMENTS:
        text = (root / name).read_text(encoding="utf-8")
        present = re.search(pattern, text) is not None
        if not tags and developing and not present:
            findings.append(
                f"{name} no longer tells a reader that nothing has been released (expected to "
                f"match {pattern!r}), and no tag exists to make that true."
            )
        if tags and present:
            findings.append(
                f"{name} still says nothing has been released, but {newest_tag(tags)!r} exists."
            )
        elif not developing and present:
            findings.append(
                f"{name} still says nothing has been released, in the commit that prepares a "
                "release -- the commit that gets tagged, where the sentence becomes false."
            )
    return findings


def _citation_date(root: Path) -> str | None:
    text = (root / "CITATION.cff").read_text(encoding="utf-8")
    match = re.search(r'^date-released:\s*"?([^"\s]*)"?\s*$', text, re.MULTILINE)
    return match.group(1) if match else None


def citation_release_date_findings(root: Path, declared: str | None = None) -> list[str]:
    """`date-released` names a release, so it exists only beside a dated heading.

    This is the exact regression GAP-REL-1 records: a date sat here for a release that
    never happened, and was removed by hand in 2026-07-05 with nothing to stop it coming
    back. A date is now allowed only when the declared version is a bare one with a dated
    CHANGELOG heading (prepared or released), and it must be that heading's date.
    """

    declared = declared or declared_version(root)
    cited = _citation_date(root)
    heading = next(
        (date for version, date in changelog_release_headings(root) if version == declared), None
    )
    if not STABLE.match(declared) or heading is None:
        if cited is not None:
            return [
                f"CITATION.cff declares date-released {cited}, but {declared!r} has no dated "
                "CHANGELOG.md heading: it names a release that is neither cut nor prepared."
            ]
        return []
    if cited != heading:
        return [
            f"CITATION.cff's date-released is {cited!r}, but CHANGELOG.md dates {declared!r} "
            f"{heading}. They name one release and must name one day."
        ]
    return []


def supported_versions_findings(root: Path, declared: str | None = None) -> list[str]:
    """Once a release is written down, the README's supported-versions line names it."""

    declared = declared or declared_version(root)
    if DEV_SUFFIX.search(declared):
        return []
    text = (root / "README.md").read_text(encoding="utf-8")
    line = next((ln for ln in text.splitlines() if "**Supported versions:**" in ln), "")
    if f"`{declared}`" not in line:
        return [
            f"README.md's supported-versions line does not name `{declared}`, the version "
            f"pyproject.toml declares: {line.strip()!r}"
        ]
    return []


def restated_versions(root: Path) -> dict[str, str]:
    """Every place outside `pyproject.toml` that writes the version down again.

    `CITATION.cff` has to carry its own `version` field, so it is checked rather than
    derived. The demo scripts used to hard-code the number into the report they generate;
    they now read `monitor.__version__`, which is the installed distribution metadata.
    """

    citation = (root / "CITATION.cff").read_text(encoding="utf-8")
    citation_version = re.search(r'^version:\s*"?([^"\s]+)"?\s*$', citation, re.MULTILINE)
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    changelog_version = re.search(r"declare version\s+\(`([^`]+)`\)", changelog)
    return {
        "CITATION.cff version": citation_version.group(1) if citation_version else "",
        "CHANGELOG.md release stance": changelog_version.group(1) if changelog_version else "",
    }


def restatement_findings(root: Path, declared: str) -> list[str]:
    return [
        f"{where} says {found!r}, but pyproject.toml declares {declared!r}."
        for where, found in restated_versions(root).items()
        if found != declared
    ]


#: Scripts that stamp a version into a generated artifact. None may hard-code it.
GENERATORS = ("scripts/demo_report.py", "scripts/demo_pdf.py")

DECLARED = declared_version()
TAGS = repository_tags()
PREPARED = is_prepared(ROOT, DECLARED)


# --- the repository as it actually is --------------------------------------------------


def test_the_declared_version_is_answerable_to_the_tags_that_exist() -> None:
    finding = version_against_tags(DECLARED, TAGS, prepared=PREPARED)
    assert finding is None, finding


def test_an_empty_tag_list_is_measured_rather_than_inherited_from_a_shallow_clone() -> None:
    """An unfetched ref namespace looks exactly like a project that never released.

    That is an absence rendered as a value, which is the shape of defect this suite exists
    to refuse, so it fails here instead of quietly taking the easy branch. Every workflow
    that runs this suite checks out with `fetch-depth: 0`, which fetches `refs/tags/*`.
    """

    assert TAGS or not is_shallow(), (
        "this checkout is shallow and reports zero tags, which is indistinguishable from a "
        "repository that has never been released. Check out with fetch-depth: 0."
    )


def test_the_checkout_can_see_every_tag_the_remote_has() -> None:
    """The half the local tag list cannot prove about itself.

    A checkout that fetched no tags and a repository that has none are the same empty
    list, and the checks above would take the second reading and pass. The remote settles
    it. A skip here is a visible "not checked", not a pass: it means the remote could not
    be reached, which does not happen in CI.
    """

    published = remote_tags()
    if published is None:
        pytest.skip("the remote could not be reached; only this checkout's tag list is available")

    missing = sorted(set(published) - set(TAGS))
    assert not missing, (
        f"the remote has tag(s) this checkout cannot see: {missing}. A gate reading tags from "
        "this checkout would report 'never released' and pass. Check out with fetch-depth: 0."
    )

    finding = version_against_tags(DECLARED, published, prepared=PREPARED)
    assert finding is None, finding


def test_an_untagged_version_says_so_in_a_form_a_tool_can_read() -> None:
    """The prose is for people; this is the half a machine can act on."""

    if DEV_SUFFIX.search(DECLARED):
        assert not TAGS, (
            f"{DECLARED!r} is a developmental version, but {newest_tag(TAGS)!r} is tagged."
        )
    else:
        assert is_tagged(DECLARED, TAGS) or PREPARED, (
            f"pyproject.toml declares {DECLARED!r}, no tag carries it, and CHANGELOG.md has no "
            f"dated '## [{DECLARED}] - YYYY-MM-DD' heading, so nothing was ever built, signed "
            "or even prepared under that number. Either restore a PEP 440 '.devN' suffix, "
            "which says 'not that release, yet' in a form pip, an SBOM consumer and a "
            "dependency scanner all read, or prepare the release: the dated heading plus a "
            "matching CITATION.cff, in the commit that gets tagged -- release.yml asserts the "
            "tag equals this string exactly (REL-14)."
        )


def test_every_document_that_restates_the_version_agrees_with_pyproject() -> None:
    findings = restatement_findings(ROOT, DECLARED)
    assert findings == [], findings


def test_the_documents_state_the_release_stance_the_repository_is_in() -> None:
    findings = unreleased_statement_findings(ROOT, TAGS)
    findings += citation_release_date_findings(ROOT)
    findings += supported_versions_findings(ROOT)
    assert findings == [], findings


def test_every_dated_changelog_heading_is_a_release_that_is_tagged_or_prepared() -> None:
    findings = changelog_heading_findings(ROOT, DECLARED, TAGS, tag_dates())
    assert findings == [], findings


def test_the_package_reports_the_version_the_source_tree_declares() -> None:
    assert PACKAGE_VERSION == DECLARED, (
        f"the installed package reports {PACKAGE_VERSION!r} but pyproject.toml declares "
        f"{DECLARED!r} -- re-run `make dev` so the metadata matches the source tree."
    )


@pytest.mark.parametrize("script", GENERATORS)
def test_a_generator_stamps_the_derived_version_not_a_typed_one(script: str) -> None:
    """The version reaches the generated report through `monitor.__version__` or not at all."""

    source = (ROOT / script).read_text(encoding="utf-8")
    assert "app_version=__version__" in source, script
    assert DECLARED not in source, (
        f"{script} writes the version down again; read it from `monitor.__version__`."
    )


# --- the branches this repository cannot reach ------------------------------------------


def test_a_tag_that_matches_the_declared_version_is_the_passing_case() -> None:
    assert version_against_tags("0.1.0", ["v0.1.0"]) is None
    assert version_against_tags("0.1.0", ["0.1.0"]) is None
    assert version_against_tags("0.2.0", ["v0.1.0", "v0.2.0"]) is None


@pytest.mark.parametrize(
    ("declared", "tags", "newest"),
    [
        ("0.1.0", ["v0.2.0"], "v0.2.0"),
        ("0.1.0.dev0", ["v0.1.0"], "v0.1.0"),
        ("0.3.0", ["v0.1.0", "v0.10.0", "v0.9.0"], "v0.10.0"),
    ],
)
def test_a_declared_version_no_tag_backs_is_a_failure_that_names_both(
    declared: str, tags: list[str], newest: str
) -> None:
    """A gate that cannot fail is not a gate, and this repository cannot reach the failing
    state on its own, so it is driven here with tag lists it does not have."""

    finding = version_against_tags(declared, tags)
    assert finding is not None
    assert repr(declared) in finding
    assert repr(newest) in finding


def test_a_prepared_release_may_run_ahead_of_the_tags_but_never_behind_them() -> None:
    assert version_against_tags("0.2.0", ["v0.1.0"], prepared=True) is None
    assert version_against_tags("0.10.0", ["v0.9.0"], prepared=True) is None

    behind = version_against_tags("0.1.0", ["v0.2.0"], prepared=True)
    assert behind is not None and "'v0.2.0'" in behind
    level = version_against_tags("0.2.0", ["v0.2.1"], prepared=True)
    assert level is not None
    developing = version_against_tags("0.2.0.dev0", ["v0.1.0"], prepared=True)
    assert developing is not None, "a .devN version is never a prepared release"
    unprepared = version_against_tags("0.2.0", ["v0.1.0"])
    assert unprepared is not None, "a bare version with no dated heading is not prepared"


def test_the_newest_tag_is_chosen_numerically_not_lexically() -> None:
    assert newest_tag(["v0.9.0", "v0.10.0"]) == "v0.10.0"
    assert newest_tag(["v1.0.0", "v0.10.0"]) == "v1.0.0"


# --- negative controls: each check is shown to bite on a sabotaged copy ------------------


@pytest.fixture
def sabotage(tmp_path: Path) -> Path:
    """A copy of the documents these checks read, so a mutation cannot touch the repo."""

    copy = tmp_path / "repo"
    copy.mkdir()
    for name in ("README.md", "CHANGELOG.md", "CITATION.cff", "pyproject.toml"):
        shutil.copy(str(ROOT / name), str(copy / name))
    return copy


def _rewrite(path: Path, old: str, new: str) -> str:
    """Replace once, and prove the sabotage landed before any finding is trusted."""

    before = path.read_text(encoding="utf-8")
    after = before.replace(old, new, 1)
    assert after != before, f"the sabotage did not land: {old!r} not found in {path.name}"
    path.write_text(after, encoding="utf-8")
    return after


def _heading_date(root: Path, version: str) -> str:
    return next(date for v, date in changelog_release_headings(root) if v == version)


def test_the_clean_tree_produces_no_findings_at_all(sabotage: Path) -> None:
    """Without this, every negative control below could pass for the wrong reason."""

    assert declared_version(sabotage) == DECLARED
    assert restatement_findings(sabotage, DECLARED) == []
    assert unreleased_statement_findings(sabotage, []) == []
    assert citation_release_date_findings(sabotage) == []
    assert supported_versions_findings(sabotage) == []
    assert changelog_heading_findings(sabotage, DECLARED, []) == []


@pytest.mark.parametrize("document", [name for name, _ in UNRELEASED_STATEMENTS])
def test_a_development_tree_without_its_release_stance_sentence_is_caught(
    sabotage: Path, document: str
) -> None:
    """The development state, driven on a copy: no tags, a `.devN` version, no sentence.

    While a release is prepared the sentence is already gone, so the version is what gets
    driven; in a development tree the sentence is deleted first.
    """

    pattern = dict(UNRELEASED_STATEMENTS)[document]
    path = sabotage / document
    path.write_text(re.sub(pattern, "REMOVED", path.read_text(encoding="utf-8")), encoding="utf-8")
    assert re.search(pattern, path.read_text(encoding="utf-8")) is None

    findings = unreleased_statement_findings(sabotage, [], declared="9.9.9.dev0")
    assert any(document in finding for finding in findings), findings


@pytest.mark.parametrize("document", [name for name, _ in UNRELEASED_STATEMENTS])
def test_a_stance_sentence_left_standing_in_a_prepared_release_is_caught(
    sabotage: Path, document: str
) -> None:
    """The commit that prepares a release is the one that gets tagged, so it retires them."""

    pattern = dict(UNRELEASED_STATEMENTS)[document]
    path = sabotage / document
    path.write_text(path.read_text(encoding="utf-8") + "\n" + pattern + ".\n", encoding="utf-8")

    if STABLE.match(DECLARED):
        findings = unreleased_statement_findings(sabotage, [])
        assert any(document in finding for finding in findings), findings
    findings = unreleased_statement_findings(sabotage, ["v0.1.0"], declared="0.1.0")
    assert any(document in finding and "v0.1.0" in finding for finding in findings), findings


def test_a_citation_release_date_on_a_development_version_is_caught(sabotage: Path) -> None:
    """GAP-REL-1's original defect, reproduced deliberately on a copy: a date beside a
    version that no dated heading prepares."""

    path = sabotage / "CITATION.cff"
    text = path.read_text(encoding="utf-8")
    if _citation_date(sabotage) is None:
        path.write_text(text + "date-released: 2026-06-30\n", encoding="utf-8")
    assert _citation_date(sabotage) is not None, "the sabotage did not land"

    findings = citation_release_date_findings(sabotage, declared="9.9.9.dev0")
    assert findings and "9.9.9.dev0" in findings[0], findings
    findings = citation_release_date_findings(sabotage, declared="9.9.9")
    assert findings and "9.9.9" in findings[0], findings


@pytest.mark.skipif(not PREPARED, reason="no release is written down in this tree")
def test_a_citation_date_that_disagrees_with_the_changelog_is_caught(sabotage: Path) -> None:
    date = _heading_date(sabotage, DECLARED)
    _rewrite(sabotage / "CITATION.cff", f'date-released: "{date}"', 'date-released: "1999-01-01"')

    findings = citation_release_date_findings(sabotage)
    assert findings and "1999-01-01" in findings[0] and date in findings[0], findings


@pytest.mark.skipif(not PREPARED, reason="no release is written down in this tree")
def test_a_prepared_release_without_a_citation_date_is_caught(sabotage: Path) -> None:
    date = _heading_date(sabotage, DECLARED)
    _rewrite(sabotage / "CITATION.cff", f'date-released: "{date}"\n', "")

    assert citation_release_date_findings(sabotage) != []


@pytest.mark.skipif(not PREPARED, reason="no release is written down in this tree")
def test_a_readme_that_does_not_name_the_prepared_version_is_caught(sabotage: Path) -> None:
    path = sabotage / "README.md"
    line = next(
        ln
        for ln in path.read_text(encoding="utf-8").splitlines()
        if "**Supported versions:**" in ln
    )
    _rewrite(path, line, line.replace(f"`{DECLARED}`", "`9.9.9`"))

    findings = supported_versions_findings(sabotage)
    assert findings and DECLARED in findings[0], findings


@pytest.mark.skipif(not PREPARED, reason="no release is written down in this tree")
@pytest.mark.parametrize(
    ("sabotaged", "expected"),
    [
        ("## [{v}]", "needs\nexactly one"),
        (" ## [{v}] - {d}", "column 0"),
        ("## [{v}] - someday", "no ISO date"),
        ("## [{v}] - {d}\n\n## [{v}] - {d}", "it has 2"),
    ],
)
def test_a_release_heading_release_yml_cannot_extract_is_caught(
    sabotage: Path, sabotaged: str, expected: str
) -> None:
    date = _heading_date(sabotage, DECLARED)
    heading = f"## [{DECLARED}] - {date}"
    _rewrite(sabotage / "CHANGELOG.md", heading, sabotaged.format(v=DECLARED, d=date))

    findings = changelog_heading_findings(sabotage, DECLARED, [])
    joined = " ".join(findings).replace("\n", " ")
    assert expected.replace("\n", " ") in joined, findings


@pytest.mark.skipif(not PREPARED, reason="no release is written down in this tree")
def test_a_dated_heading_for_a_release_that_is_neither_tagged_nor_prepared_is_caught(
    sabotage: Path,
) -> None:
    """The phantom release, under a number other than the one being prepared."""

    date = _heading_date(sabotage, DECLARED)
    heading = f"## [{DECLARED}] - {date}"
    _rewrite(sabotage / "CHANGELOG.md", heading, f"{heading}\n\n## [0.0.9] - 2026-01-01")

    findings = changelog_heading_findings(sabotage, DECLARED, [])
    assert any("'0.0.9'" in finding for finding in findings), findings
    assert changelog_heading_findings(sabotage, DECLARED, ["v0.0.9"]) == []


@pytest.mark.skipif(not PREPARED, reason="no release is written down in this tree")
def test_a_prepared_heading_below_an_older_release_is_caught(sabotage: Path) -> None:
    """release.yml would still extract it, but the file would read newest-last."""

    date = _heading_date(sabotage, DECLARED)
    heading = f"## [{DECLARED}] - {date}"
    _rewrite(sabotage / "CHANGELOG.md", heading, f"## [0.0.9] - 2026-01-01\n\n{heading}")

    findings = changelog_heading_findings(sabotage, DECLARED, ["v0.0.9"])
    assert any("newest dated heading is '0.0.9'" in finding for finding in findings), findings


@pytest.mark.skipif(not PREPARED, reason="no release is written down in this tree")
def test_a_heading_dated_on_another_day_than_its_tag_is_caught(sabotage: Path) -> None:
    """The released state, driven with a synthetic tag and tag date."""

    date = _heading_date(sabotage, DECLARED)
    tag = f"v{DECLARED}"
    assert changelog_heading_findings(sabotage, DECLARED, [tag], {tag: date}) == []

    findings = changelog_heading_findings(sabotage, DECLARED, [tag], {tag: "1999-01-01"})
    assert findings and date in findings[0] and "1999-01-01" in findings[0], findings


@pytest.mark.parametrize(
    ("document", "old", "new"),
    [
        ("CITATION.cff", f'version: "{DECLARED}"', 'version: "9.9.9"'),
        ("CHANGELOG.md", f"(`{DECLARED}`)", "(`9.9.9`)"),
    ],
)
def test_a_restated_version_drifting_from_pyproject_is_caught(
    sabotage: Path, document: str, old: str, new: str
) -> None:
    path = sabotage / document
    before = path.read_text(encoding="utf-8")
    after = before.replace(old, new, 1)
    path.write_text(after, encoding="utf-8")

    assert after != before, f"the sabotage did not land: {old!r} not found in {document}"
    assert "9.9.9" in after

    findings = restatement_findings(sabotage, DECLARED)
    assert any("9.9.9" in finding for finding in findings), findings
