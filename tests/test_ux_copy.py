"""Guards against the frontend misstating what the backend said.

Two PR-UX-01 review findings live here. The overview once said a blocking
permit "stops a unit being released" — a rule the backend does not enforce —
and the price register once denominated a row's frozen price in the ACTIVE
configuration's currency rather than the row's own. Both are the same class
of defect: the screen inventing a fact, and both guards read the frontend
source because the rule they protect is about presentation, not behaviour.
"""

from pathlib import Path

FRONTEND = Path(__file__).resolve().parent.parent / "frontend" / "src"
PROJECT_WORKSPACE = FRONTEND / "components" / "projects" / "ProjectWorkspace.tsx"
PRICING_TAB = FRONTEND / "components" / "projects" / "PricingTab.tsx"


def test_project_overview_does_not_tie_permits_to_unit_release() -> None:
    source = PROJECT_WORKSPACE.read_text(encoding="utf-8").lower()
    assert "stops a unit being released" not in source
    assert "cannot be released" not in source


def test_price_register_rows_are_denominated_by_their_own_version() -> None:
    """A frozen price keeps the currency it was approved in.

    The backend returns ``currency_id`` on every price register row, taken
    from that row's own price version. The register must resolve exactly that
    field — never the active configuration's ``overview.currency_id``, which
    describes what the project prices in TODAY and can differ from what a
    unit's standing price was approved in.
    """
    collapsed = "".join(PRICING_TAB.read_text(encoding="utf-8").split())
    for field in ("reference_price_ex_tax", "price_per_internal_area"):
        assert f"money(row.{field},currencyCodeOf(row.currency_id))" in collapsed
        assert f"money(row.{field},currencyCodeOf(overview" not in collapsed
