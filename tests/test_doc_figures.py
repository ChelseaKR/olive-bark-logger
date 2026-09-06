"""Merge-blocking: a number a document states about this repo is read back from the repo.

Every count in the documentation was typed by hand once and never re-read, and each one
drifted the moment the thing it counted changed:

* `docs/RESPONSIBLE-TECH-AUDITS.md` §F said "**ten** dev-toolchain-only CVEs are waived …
  **All ten** are in pip-audit's own transitive dependencies" for eight days after the
  2026-08-21 pass took the real number to **12** -- and the two additions broke the
  sentence twice over, because one of them is setuptools, a venv seed package that is not
  a pip-audit dependency at all. A waiver list that under-reports its own length is the
  worst possible place for a stale number.
* `docs/DOCUMENTATION-AUDIT.md` claimed "3 ADRs" when four already existed *at its own
  commit* (`8c00624`), and five exist now; and "33 Python/Node test files; 1 workflow
  file" against a tree that has since grown to a different number of both.

The pattern is `tests/test_ruleset_check.py`, which pins the README's CI/CD row to the
live ruleset rather than trusting the prose: state the figure once, derive it here, and
let the build fail when the two disagree. The failure message always names the true value,
so the fix is a one-line edit and never a guess.

Deliberately *not* gated: `docs/PROJECT-SCOPE.md`'s "37 hand-authored doc or metadata
files". Its own definition excludes "vendored provider licenses, dependency folders,
generated cache files, and generated artifacts", which no mechanical rule in this repo
reproduces, so any figure asserted here would be invented. It is left as the dated
point-in-time count it is, and labelled as one in the document.
"""

from __future__ import annotations

import re
from pathlib import Path

from conftest import ROOT

AUDITS = ROOT / "docs" / "RESPONSIBLE-TECH-AUDITS.md"
DOC_AUDIT = ROOT / "docs" / "DOCUMENTATION-AUDIT.md"
SCOPE = ROOT / "docs" / "PROJECT-SCOPE.md"
MAKEFILE = ROOT / "Makefile"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _claims(path: Path) -> str:
    """The document minus its blockquotes.

    This repo records a superseded claim by quoting it verbatim next to the correction
    (`docs/GAP-LEDGER.md` is built that way, and it is the honest thing to do). Those
    quotations live in blockquotes, and a scanner that reads them will find every figure
    it just fixed still "stated" in the file. Blockquotes are history; the rest is the
    claim. Dropping them is what lets a correction keep the false sentence on the record.
    """
    return "\n".join(line for line in _text(path).splitlines() if not line.lstrip().startswith(">"))


# --- the repo facts, read from the repo ----------------------------------------------


def waiver_count() -> int:
    """CVEs waived in `PIP_AUDIT_WAIVERS`, counted from the Makefile."""
    return len(re.findall(r"--ignore-vuln\s+\S+", _text(MAKEFILE)))


def adr_count() -> int:
    return len(list((ROOT / "docs" / "adr").glob("*.md")))


def count_test_files() -> int:
    """Python and Node test files, the two suites `make verify` runs."""
    return len(list((ROOT / "tests").glob("test_*.py"))) + len(
        list((ROOT / "pwa").glob("*.test.mjs"))
    )


def workflow_count() -> int:
    return len(list((ROOT / ".github" / "workflows").glob("*.yml")))


def verify_prerequisites() -> list[str]:
    """The targets `make verify` actually depends on."""
    match = re.search(r"^verify:\s*(.+)$", _text(MAKEFILE), re.MULTILINE)
    assert match, "Makefile has no `verify:` target -- the checks below have no premise"
    return match.group(1).split()


# --- the figures ---------------------------------------------------------------------


def test_the_waiver_count_in_the_audit_matches_the_makefile():
    stated = re.search(r"\*\*(\d+)\*\* dev-toolchain-only CVEs are waived", _claims(AUDITS))
    assert stated, "docs/RESPONSIBLE-TECH-AUDITS.md §F no longer states a waiver count"
    assert int(stated.group(1)) == waiver_count(), (
        f"§F says {stated.group(1)} waived CVEs; Makefile's PIP_AUDIT_WAIVERS has "
        f"{waiver_count()}. Update the document, and never by adding a waiver to match."
    )


def test_the_audit_names_setuptools_as_not_a_pip_audit_dependency():
    """The count was only half the defect. §F also said *all* the waivers were in
    pip-audit's own transitive dependencies while one of them was setuptools, which the
    Makefile's own note calls a venv seed package. Hold the substance, not just the digit."""
    text = _claims(AUDITS)
    if "PYSEC-2026-3447" not in _text(MAKEFILE):
        return  # waiver dropped; the sentence about it is allowed to go with it
    assert "setuptools" in text, (
        "a setuptools CVE is waived in the Makefile but §F does not mention setuptools"
    )
    section = text.split("**VEX")[1].split("\n\n")[0]
    assert "seed package" in section, (
        "§F must say what setuptools is (a venv seed package, not one of pip-audit's "
        "transitive dependencies) rather than folding it into that list"
    )


def test_the_adr_count_in_the_documentation_audit_is_current():
    stated = re.search(r"\|\s*(\d+) ADRs;", _claims(DOC_AUDIT))
    assert stated, "docs/DOCUMENTATION-AUDIT.md no longer states an ADR count"
    assert int(stated.group(1)) == adr_count(), (
        f"DOCUMENTATION-AUDIT says {stated.group(1)} ADRs; docs/adr/ holds {adr_count()}"
    )


def test_every_migrated_adr_is_indexed_by_the_roadmap():
    """The other half of the ADR migration's drift risk.

    GAP-DOC-1 moved the decisions embedded in `docs/ROADMAP.md` into numbered files and
    left index tables behind pointing at them. A hand-maintained index is the same shape
    as every count in this file -- true the day it is typed, silently short after the next
    addition -- and `tests/test_doc_links.py` only catches the direction where the index
    names a file that is not there. This catches the direction that matters more: a
    migrated ADR that no index row reaches, which is a decision the roadmap has stopped
    mentioning at all.

    Scoped by the ADRs' own `Migrated:` line rather than by a number range, so an ADR
    written from scratch later (0001-0004 were) is not required to appear there.
    """
    roadmap = _text(ROOT / "docs" / "ROADMAP.md")
    migrated = [
        p
        for p in sorted((ROOT / "docs" / "adr").glob("*.md"))
        if re.search(r"\*\*Migrated:\*\*[^\n]*docs/ROADMAP\.md", _text(p))
    ]
    assert migrated, "no ADR records being migrated from docs/ROADMAP.md -- check the marker"
    missing = [p.name for p in migrated if p.name not in roadmap]
    assert not missing, (
        f"ADRs migrated out of docs/ROADMAP.md that no index row there links: {missing}. "
        "Add a row to the 'ADRs added during build' or 'Productionization ADRs' table."
    )


def test_the_validation_surface_counts_are_current():
    """Stated in two documents. Both are read, so correcting one and not the other fails."""
    pattern = re.compile(r"(\d+) Python/Node test files[;,] (?:and )?(\d+) workflow files?")
    for path in (DOC_AUDIT, SCOPE):
        stated = pattern.search(_claims(path))
        assert stated, f"{path.name} no longer states the validation-surface counts"
        tests_said, flows_said = int(stated.group(1)), int(stated.group(2))
        assert tests_said == count_test_files(), (
            f"{path.name} says {tests_said} test files; the tree has {count_test_files()} "
            f"(tests/test_*.py plus pwa/*.test.mjs)"
        )
        assert flows_said == workflow_count(), (
            f"{path.name} says {flows_said} workflow file(s); .github/workflows/ holds "
            f"{workflow_count()}"
        )


# --- F4: what `make verify` does to committed artifacts ------------------------------


def test_make_verify_does_not_regenerate_committed_artifacts():
    """The premise of the check below, asserted against the Makefile.

    `docs/RESPONSIBLE-TECH-AUDITS.md` claimed "artifacts are committed and regenerated by
    `make verify`". `snapshot` is not one of verify's prerequisites and never was, and the
    only artifact the `a11y` leg writes is the gitignored `report.html`.
    """
    assert "snapshot" not in verify_prerequisites(), (
        "`snapshot` is now a prerequisite of `make verify`. That would make the old claim "
        "true -- update the documents and this test together, deliberately."
    )
    gitignore = _text(ROOT / ".gitignore")
    assert "/report.html" in gitignore, (
        "report.html is no longer gitignored, so `make a11y` may now regenerate a "
        "committed artifact; re-read the RTF-08 claim before relaxing anything"
    )


def test_no_document_says_make_verify_regenerates_the_artifacts():
    stale = "regenerated by `make verify`"
    offenders = [
        p.relative_to(ROOT).as_posix()
        for p in [*sorted(ROOT.glob("docs/**/*.md")), ROOT / "README.md"]
        if stale in _claims(p)
    ]
    assert not offenders, (
        f"documents still say `make verify` regenerates committed artifacts: {offenders}. "
        "It checks them (tests/test_report_snapshot.py byte-compares the golden); "
        "regenerating is `make snapshot` / scripts/gen_cover_spec.py."
    )


def test_rtf_08_is_still_recorded_as_open():
    """The other direction, and the one that matters more. Narrowing the false
    "regenerated by make verify" claim must not quietly retire the gap it was covering:
    nothing regenerates the dated audit artifacts on release, and the ledger says so."""
    ledger = _text(ROOT / "docs" / "GAP-LEDGER.md")
    entry = ledger.split("## GAP-RTF-1")[1].split("## GAP-OBS-1")[0]
    assert "RTF-08" in entry and "remains open" in entry, (
        "GAP-RTF-1 no longer records RTF-08 as open. Correcting a claim downward is not "
        "the same as closing a gap; do not remove this unless the gap was actually fixed."
    )


# --- F5: which of verify's targets CI actually calls ---------------------------------


CONTRIBUTING = ROOT / "CONTRIBUTING.md"
CI = ROOT / ".github" / "workflows" / "ci.yml"


def make_targets_called_by_ci() -> set[str]:
    """Targets CI invokes as `make <target>`, so they cannot drift from the Makefile."""
    return set(re.findall(r"^\s*run:\s*make\s+([\w-]+)\s*$", _text(CI), re.MULTILINE))


def test_the_parity_table_matches_what_ci_actually_calls():
    """`CONTRIBUTING.md` said there was "the one place CI and the Makefile still don't
    call identical commands" and pointed at `GAP-CICD-1`, an entry about the branch
    ruleset that never mentions parity -- and contradicted itself eleven lines later.
    There are three such places, not one. Derive both numbers rather than typing them."""
    verify = [t for t in verify_prerequisites()]
    called = make_targets_called_by_ci() & set(verify)
    not_called = sorted(set(verify) - called)

    text = _claims(CONTRIBUTING)
    assert "## Local/CI parity" in text or "### Local/CI parity" in text, (
        "CONTRIBUTING.md has no Local/CI parity section; it is the place ci.yml points at"
    )
    stated = re.search(r"CI invokes\s*\n?\*\*(\w+)\*\* of them", text)
    assert stated, "the parity section no longer states how many targets CI invokes"
    words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7}
    assert words[stated.group(1)] == len(called), (
        f"CONTRIBUTING says CI invokes {stated.group(1)} of verify's targets as make "
        f"targets; ci.yml invokes {len(called)}: {sorted(called)}"
    )
    # Every target CI does *not* call as a make target must be named in the table, or a
    # reader is told the two agree somewhere they do not.
    parity = text.split("Local/CI parity")[1].split("## ")[0]
    missing = [t for t in not_called if f"`{t}`" not in parity]
    assert not missing, (
        f"CI does not invoke `make {'`/`make '.join(missing)}`, and the parity table does "
        f"not mention it. verify needs {verify}; CI calls {sorted(called)}."
    )


def test_no_document_points_at_gap_cicd_1_for_the_parity_statement():
    """GAP-CICD-1 is about the live branch ruleset and zizmor/CodeQL-actions. It has never
    discussed which commands CI runs, and two files cited it as though it had."""
    ledger_entry = _text(ROOT / "docs" / "GAP-LEDGER.md").split("## GAP-CICD-1")[1]
    ledger_entry = ledger_entry.split("## GAP-A11Y-1")[0]
    if "identical commands" in ledger_entry or "parity" in ledger_entry.lower():
        return  # the entry now does cover it; the citation would be fair
    for path in (CONTRIBUTING, CI):
        for line in _claims(path).splitlines():
            if "gap-cicd-1" not in line.lower():
                continue
            lowered = line.lower()
            assert "identical commands" not in lowered and "parity" not in lowered, (
                f"{path.name} cites GAP-CICD-1 for a parity statement that entry does not "
                f"make: {line.strip()}"
            )


def test_ci_points_at_a_document_that_actually_states_the_parity():
    """`ci.yml` cited `docs/RESPONSIBLE-TECH-AUDITS.md` §F and the README's Standards
    Conformance table for "the exact local/CI parity statement". The word parity appeared
    in neither. A citation has to land somewhere that says the thing."""
    for line in _claims(CI).splitlines():
        if "parity" not in line.lower():
            continue
        for cited in BARE_DOC.findall(line):
            target = ROOT / cited
            if not target.exists():
                continue
            assert "parity" in _text(target).lower(), (
                f"ci.yml cites {cited} for a parity statement; that file never says parity"
            )


BARE_DOC = re.compile(r"((?:docs|\.github)/[\w./-]+\.md|CONTRIBUTING\.md|README\.md)")


# --- F7: a freshness stamp that is older than the content it stamps -------------------


DATE = re.compile(r"\b(20\d\d-\d\d-\d\d)\b")


def test_the_gap_ledgers_stamp_is_not_older_than_its_own_content():
    """The ledger's own preamble says a stale entry should "fail a build rather than
    ageing quietly". Its `Last verified` stamp said 2026-08-15 while entries below it
    recorded updates through 2026-08-27: three passes edited the file without moving it."""
    # Blockquotes are excluded for the same reason as everywhere else in this file: they
    # hold the record of a superseded claim, and a note *about* the stamp being late must
    # not itself become content the stamp has to cover.
    text = _claims(ROOT / "docs" / "GAP-LEDGER.md")
    stamp = re.search(r"\*\*Last verified:\s*(20\d\d-\d\d-\d\d)", text)
    assert stamp, "docs/GAP-LEDGER.md no longer carries a `Last verified` stamp"
    newest = max(DATE.findall(text))
    assert stamp.group(1) >= newest, (
        f"GAP-LEDGER says 'Last verified: {stamp.group(1)}' but carries content dated "
        f"{newest}. Move the stamp when you touch an entry."
    )


# --- F10: a supported-versions policy that presupposes a release ---------------------


def test_no_document_implies_a_release_exists_while_none_does():
    """`CITATION.cff`'s own in-file note makes `date-released` the marker: "Add
    `date-released` back only once a version is actually tagged." While it is absent, the
    README's supported-versions line may state a policy but must not read as a claim that
    a release stream exists -- the "phantom release" defect `CHANGELOG.md` was written to
    prevent, and which the README's `only the latest 0.y release receives fixes` reprised.
    """
    citation = _text(ROOT / "CITATION.cff")
    if re.search(r"^date-released:", citation, re.MULTILINE):
        return  # a release exists; the present-tense policy is fair
    line = next(
        (ln for ln in _claims(ROOT / "README.md").splitlines() if "Supported versions" in ln),
        None,
    )
    assert line, "README no longer states a supported-versions policy"
    assert "no version has been tagged" in line.lower(), (
        "no `v*` release exists (CITATION.cff has no date-released) but the README's "
        f"supported-versions line does not say so: {line.strip()}"
    )


# --- F5b: the two `pip-audit` runs are not the same command --------------------------


def _ignored_vulns(text: str) -> set[str]:
    return set(re.findall(r"--ignore-vuln\s+(\S+)", text))


def ci_dependency_audit_command() -> str:
    """The `run:` line of ci.yml's dependency-audit step, whatever it is called."""
    steps = re.split(r"^      - name: ", _text(CI), flags=re.MULTILINE)
    for step in steps:
        if step.lower().startswith("dependency audit"):
            return step.split("\n", 1)[1] if "\n" in step else ""
    return ""


def test_the_parity_table_names_the_pip_audit_waiver_divergence():
    """CONTRIBUTING.md calls itself "the authoritative statement of how `make verify` and
    CI differ", and its `security` row explained only the gitleaks difference. There is a
    second one, in the argument list: `make security` runs `pip-audit` with twelve
    `--ignore-vuln` flags and CI runs it with none.

    That is not a bug in either command -- the waivers are a >=3.9 accommodation and CI
    runs 3.12, where `uv.lock` resolves the fixed versions -- but it does mean a green
    `make verify` does not predict a green CI, which is precisely what the parity section
    exists to tell a contributor. Derive it, so the sentence cannot rot once the two
    argument lists are made to agree, or diverge further.
    """
    makefile_waivers = _ignored_vulns(_text(MAKEFILE))
    ci_waivers = _ignored_vulns(ci_dependency_audit_command())
    if makefile_waivers == ci_waivers:
        return  # the two commands now agree; there is nothing left to disclose

    # Stop at the next heading of any level: the disclosure has to be in the parity
    # section itself, not somewhere further down the file that happens to mention it.
    parity = _claims(CONTRIBUTING).split("Local/CI parity")[1].split("\n#")[0]
    assert "PIP_AUDIT_WAIVERS" in parity, (
        "`make security` and ci.yml run `pip-audit` with different `--ignore-vuln` sets "
        f"(Makefile {len(makefile_waivers)}, CI {len(ci_waivers)}), and CONTRIBUTING.md's "
        "Local/CI parity section does not mention it. A contributor is told the two gates "
        "agree everywhere that section does not list."
    )


def test_the_waiver_scanner_reads_the_makefile_and_the_workflow():
    """Canary: both halves of the comparison above must actually find their text, or the
    divergence check passes by reading two empty sets."""
    assert _ignored_vulns(_text(MAKEFILE)), "no --ignore-vuln flags found in the Makefile"
    assert ci_dependency_audit_command().strip(), (
        "ci.yml has no step named 'Dependency audit'; the comparison above has no CI side"
    )
    assert _ignored_vulns("--ignore-vuln A-1 --ignore-vuln A-2") == {"A-1", "A-2"}


# --- F11: the workflow static-analysis gate --------------------------------------------


RULESET = ROOT / ".github" / "rulesets" / "main.json"


def test_the_workflow_linter_is_pinned_to_a_version():
    """A gate whose verdict can change without a commit is the defect
    `scripts/check_nightly_macos.py` was rewritten to stop having, in its other shape.

    `make workflows` shells out to a tool this repo does not lock, so the pin is the only
    thing making today's "no findings" reproducible tomorrow. `uvx --from zizmor zizmor`
    would silently move to the newest release; the next new audit would then read as a
    regression in a pull request that did not touch a workflow.
    """
    makefile = _text(MAKEFILE)
    assert re.search(r"^workflows:$", makefile, re.MULTILINE), (
        "the `workflows` target is gone; docs/GAP-LEDGER.md#gap-cicd-1 records it as the "
        "enforced floor for the workflow surface"
    )
    requirements = re.findall(r"zizmor==(\S+)", makefile)
    assert requirements, (
        "the Makefile invokes zizmor without `==<version>`, so the gate's verdict can "
        "change with no commit in this repository to explain it"
    )
    # The pin may be written through a make variable; resolve one level of `$(NAME)`
    # rather than requiring a literal, so the version can stay a named constant.
    assignments = dict(re.findall(r"^([A-Z_]+)\s*[:?]?=\s*(\S+)\s*$", makefile, re.MULTILINE))
    versions = set()
    for req in requirements:
        var = re.fullmatch(r"\$\(([A-Z_]+)\)", req)
        versions.add(assignments.get(var.group(1), "") if var else req)
    unpinned = sorted(v for v in versions if not re.fullmatch(r"\d+\.\d+\.\d+", v))
    assert not unpinned, (
        f"zizmor's version does not resolve to a literal release: {unpinned}. A linter "
        "that floats changes its verdict with no commit here to explain it."
    )
    assert len(versions) == 1, f"zizmor is pinned to more than one version: {sorted(versions)}"


def test_codeql_is_not_described_as_a_gate_while_it_is_not_one():
    """The documents say CodeQL *reports* rather than gates, because
    `codeql-action/analyze` exits 0 on a finding. That is only true while the context is
    absent from the required-check list -- and if it is ever added, three documents start
    understating the gate instead. Derive it from the committed ruleset rather than
    trusting either side's prose.
    """
    import json

    workflow = ROOT / ".github" / "workflows" / "codeql.yml"
    if not workflow.exists():
        return  # nothing to describe

    contexts = {
        check.get("context")
        for rule in json.loads(_text(RULESET)).get("rules", [])
        if rule.get("type") == "required_status_checks"
        for check in rule.get("parameters", {}).get("required_status_checks", [])
    }
    codeql_required = any(c and c.startswith("codeql") for c in contexts)

    ledger = _claims(ROOT / "docs" / "GAP-LEDGER.md")
    entry = ledger.split("## GAP-CICD-1")[1].split("## GAP-A11Y-1")[0]
    says_reporting = "reporting" in entry or "does not block a merge" in entry
    assert codeql_required != says_reporting, (
        "docs/GAP-LEDGER.md#gap-cicd-1 and .github/rulesets/main.json disagree about "
        f"whether CodeQL blocks a merge: required contexts {sorted(c for c in contexts if c)}, "
        f"ledger describes it as reporting-only: {says_reporting}"
    )


# --- canaries ------------------------------------------------------------------------


def test_the_figure_scanners_read_real_values():
    """Prove each derivation returns something, so a silently-empty glob cannot make
    every assertion above vacuously agree with a doc that says zero."""
    assert waiver_count() > 0
    assert adr_count() > 0
    assert count_test_files() > 0
    assert workflow_count() > 0
    assert verify_prerequisites(), "verify has no prerequisites -- the gate set is empty"


def test_the_waiver_counter_counts_flags_not_lines():
    """`grep -c ignore-vuln Makefile` counts lines, which happens to agree today. Count
    the flags, so two waivers written on one line cannot under-report."""
    planted = "X := \\\n\t--ignore-vuln A-1 --ignore-vuln A-2 \\\n\t--ignore-vuln A-3\n"
    assert len(re.findall(r"--ignore-vuln\s+\S+", planted)) == 3
