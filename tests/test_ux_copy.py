"""The Project Overview must not invent a business rule.

PR-UX-01 review finding: the overview once said a blocking permit "stops a
unit being released". Unit release truth lives in inventory — completeness,
drawings, legal saleability, pricing approval, release date, block reason —
and does not read permit status, so that sentence described a rule the
backend does not enforce. The screen may report permit counts; it may not
claim they gate unit release. This guard keeps the false claim from
returning until a functional PR actually builds such a rule.
"""

from pathlib import Path

PROJECT_WORKSPACE = (
    Path(__file__).resolve().parent.parent
    / "frontend"
    / "src"
    / "components"
    / "projects"
    / "ProjectWorkspace.tsx"
)


def test_project_overview_does_not_tie_permits_to_unit_release() -> None:
    source = PROJECT_WORKSPACE.read_text(encoding="utf-8").lower()
    assert "stops a unit being released" not in source
    assert "cannot be released" not in source
