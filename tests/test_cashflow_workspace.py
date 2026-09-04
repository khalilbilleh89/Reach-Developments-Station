"""What the Cashflow workspace is not allowed to do.

PR-MVP-10A put the whole of the project's cash truth behind an API on purpose:
the monthly bridge, the funding trough, the escrow rules, the NPV and the equity
IRR are all computed once, in Decimal, on the server. PR-MVP-10B draws it.

The line between those two jobs is the thing worth guarding, and it cannot be
guarded by a screenshot. Every assertion here reads the frontend source and
checks a rule about presentation — the same idiom as ``test_ux_copy.py``, and
for the same reason: these are defects the browser would commit silently, and
each of them has a specific, expensive failure mode.

There is no JavaScript test runner in this repository and this file does not
introduce one. What it can prove without one is exactly the class of thing that
matters here: that no arithmetic crept into the browser, that the three-state
month vocabulary survived, that an escrow's current effect is read from the two
fields that decide it, that a CSV comes from the server, and that a role which
may not read the project's cash never asks for it.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend" / "src"
CASHFLOW = FRONTEND / "components" / "projects" / "cashflow"
TAB = FRONTEND / "components" / "projects" / "CashflowTab.tsx"
NAVIGATION = FRONTEND / "components" / "shell" / "navigation.ts"
ROLES = FRONTEND / "lib" / "roles.ts"
API = FRONTEND / "lib" / "api" / "index.ts"
COMMAND_CENTRE = FRONTEND / "components" / "dashboard" / "ProjectCommandCenter.tsx"
BACKEND_PERMISSIONS = ROOT / "app" / "modules" / "cashflow" / "permissions.py"


def workspace_sources() -> list[Path]:
    """Every file that draws a cashflow figure."""
    return [*sorted(CASHFLOW.glob("*.tsx")), TAB]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class TestTheBrowserDoesNoFinancialArithmetic:
    """The rule the whole module rests on.

    Money crosses the wire as decimal strings because a cash position put
    through a JavaScript float comes back subtly different from the one the
    ledger will enforce — and the difference lands in the least significant
    digit, which is exactly where a reconciliation looks. A browser that
    re-derives a total is a browser that can disagree with the server about a
    number the server is about to act on.
    """

    def test_no_component_parses_money_into_a_number(self) -> None:
        for path in workspace_sources():
            source = read(path)
            for forbidden in ("parseFloat", "parseInt", "Number("):
                assert forbidden not in source, (
                    f"{path.name} uses {forbidden}: a money string turned into a "
                    "float is a figure that can disagree with the ledger."
                )

    def test_no_component_reduces_or_sums_a_series(self) -> None:
        """A total on this screen is one the server computed and named."""
        for path in workspace_sources():
            source = read(path)
            assert ".reduce(" not in source, (
                f"{path.name} reduces a series. Every total the cashflow "
                "workspace shows arrives computed; adding one here creates a "
                "second answer to a question that has one."
            )

    def test_no_component_does_decimal_arithmetic_on_a_figure(self) -> None:
        """No ``a - b`` or ``a + b`` over values read out of a response."""
        arithmetic = re.compile(r"\b(?:row|position|summary|window|totals|data)\.\w+\s*[-+*/]\s")
        for path in workspace_sources():
            for line in read(path).splitlines():
                assert not arithmetic.search(line), (
                    f"{path.name} computes from a response field: {line.strip()}"
                )


class TestTheThreeStateMonthSurvives:
    """A part-spent month is not a finished one, and the screen must say so.

    Reducing the vocabulary back to Actual / Forecast is the single most likely
    regression here, because two labels look tidier than three. It would present
    the month a report is taken in as complete, dropping every payment still due
    before it ends — a project read on the third of the month showing a funding
    cliff that disappears on the fourth.
    """

    def test_all_three_bases_are_named_in_words(self) -> None:
        labels = read(CASHFLOW / "labels.ts")
        assert '"Actual + Forecast"' in labels
        assert "actual_and_forecast" in labels
        assert '  actual: "Actual"' in labels
        assert '  forecast: "Forecast"' in labels

    def test_the_current_month_basis_is_explained_and_not_only_coloured(self) -> None:
        """Colour is never the only carrier: a legend states each basis in prose."""
        labels = read(CASHFLOW / "labels.ts")
        assert "monthBasisNote" in labels
        monthly = read(CASHFLOW / "CashflowMonthly.tsx")
        assert "monthBasisNote" in monthly, (
            "the monthly table must render the explanation, not just the badge"
        )
        assert "title={monthBasisNote" not in monthly, (
            "a title attribute is invisible to a keyboard and to a touch screen"
        )

    def test_the_three_customer_series_stay_apart(self) -> None:
        """Scheduled, expected and received are three truths, never merged."""
        monthly = read(CASHFLOW / "CashflowMonthly.tsx")
        for field in (
            "customer_scheduled_due",
            "customer_forecast_receipts",
            "customer_actual_receipts",
        ):
            assert field in monthly


class TestEscrowReportsItsCurrentEffectAndNotItsStatus:
    """A confirmed restriction over a reversed receipt holds nothing.

    The persisted status stays ``confirmed`` — what happened is not rewritten —
    so a screen that reads the status alone reports restricted cash the project
    does not have, and contradicts the summary on the same figure.
    """

    def test_the_screen_reads_both_fields_the_backend_added(self) -> None:
        escrow = read(CASHFLOW / "CashflowEscrow.tsx")
        assert "counts_as_restricted" in escrow
        assert "receipt_stands" in escrow
        assert "counts_as_released" in escrow
        assert "restriction_counts" in escrow

    def test_a_reversed_receipt_is_explained_rather_than_hidden(self) -> None:
        escrow = read(CASHFLOW / "CashflowEscrow.tsx")
        assert "Underlying receipt reversed" in escrow
        assert "Not currently counted" in escrow

    def test_a_release_says_why_it_has_stopped_freeing_anything(self) -> None:
        escrow = read(CASHFLOW / "CashflowEscrow.tsx")
        assert "the escrow it frees no longer stands" in escrow


class TestUnavailableFiguresAreSaidAndNotInvented:
    """A null is a fact. Rendering it as zero is a claim nobody made."""

    def test_an_unavailable_irr_shows_its_reason(self) -> None:
        overview = read(CASHFLOW / "CashflowOverview.tsx")
        assert "equity_irr_unavailable_reason" in overview
        assert "irrReasonLabel" in overview
        assert "Not available" in overview

    def test_a_null_coverage_is_explained(self) -> None:
        overview = read(CASHFLOW / "CashflowOverview.tsx")
        assert "forecast_collection_coverage === null" in overview
        assert "Not meaningful" in overview

    def test_a_null_variance_rate_is_explained(self) -> None:
        management = read(CASHFLOW / "CashflowManagement.tsx")
        assert "variance_rate === null" in management
        assert "Not meaningful against a zero forecast" in management

    def test_a_failure_is_never_drawn_as_an_empty_position(self) -> None:
        """Every section separates "nothing to report" from "could not load"."""
        for path in workspace_sources():
            source = read(path)
            if 'status === "failed"' in source:
                assert "Notice tone=\"error\"" in source, (
                    f"{path.name} handles a failure without saying so in words"
                )


class TestExportsComeFromTheServer:
    """The file a reader saves is the file the server rendered.

    The backend renders both CSVs from the same response object the screen
    draws, so the export and the screen cannot disagree. Rebuilding either in
    JavaScript would create a second rendering of the same figures.
    """

    def test_both_exports_are_backend_urls(self) -> None:
        api = read(API)
        assert "cashflowCsvHref" in api
        assert "monthly.csv" in api or '"monthly"' in api
        monthly = read(CASHFLOW / "CashflowMonthly.tsx")
        drilldown = read(CASHFLOW / "CashflowDrilldown.tsx")
        assert 'cashflowCsvHref(projectId, "monthly"' in monthly
        assert 'cashflowCsvHref(projectId, "drilldown"' in drilldown

    def test_no_component_builds_a_csv(self) -> None:
        for path in workspace_sources():
            source = read(path)
            assert "text/csv" not in source
            assert "createObjectURL" not in source


class TestDrilldownKeepsSourceOwnership:
    """Management reporting without lineage is an assertion.

    Cashflow consolidates records other modules govern and deliberately keeps no
    shadow ledger, so a reader who has to correct a figure must be able to see
    which module to open.
    """

    def test_every_source_type_is_named_and_attributed(self) -> None:
        labels = read(CASHFLOW / "labels.ts")
        for source_type in (
            "collection_receipt",
            "collection_refund",
            "construction_payment",
            "cashflow_development_movement",
            "cashflow_financing_movement",
            "payment_plan_installment",
            "cashflow_forecast_line",
        ):
            assert source_type in labels, f"{source_type} has no human label"
        assert "sourceTypeOwner" in labels
        assert '"Collections"' in labels
        assert '"Construction"' in labels
        assert '"Payment plans"' in labels

    def test_the_drilldown_shows_the_owning_module(self) -> None:
        drilldown = read(CASHFLOW / "CashflowDrilldown.tsx")
        assert "sourceTypeOwner" in drilldown
        assert "Owned by" in drilldown

    def test_nothing_is_relabelled_as_a_generic_transaction(self) -> None:
        labels = read(CASHFLOW / "labels.ts")
        assert "Cashflow transaction" not in labels


class TestOnlyEntitledReadersAsk:
    """A role that may not read the project's cash never requests it.

    Not fetch-then-hide: the figures never reach the browser at all. The server
    decides again on every call, but asking for something the reader may not
    have is a privacy failure the response cannot undo.
    """

    def test_the_frontend_role_set_matches_the_backend(self) -> None:
        backend = read(BACKEND_PERMISSIONS)
        block = backend.split("CASHFLOW_READER_ROLES")[1].split(")")[0]
        expected = set(re.findall(r'"([a-z_]+)"', block))
        frontend = read(ROLES)
        block = frontend.split("CASHFLOW_READERS")[1].split("]")[0]
        actual = set(re.findall(r'"([a-z_]+)"', block))
        assert actual == expected, (
            f"the interface offers Cashflow to {actual - expected} the server refuses, "
            f"or hides it from {expected - actual} the server would answer"
        )

    def test_collections_and_sales_are_not_cashflow_readers(self) -> None:
        frontend = read(ROLES)
        block = frontend.split("CASHFLOW_READERS")[1].split("]")[0]
        outside = (
            "collections",
            "sales_advisor",
            "sales_operations",
            "legal",
            "design_engineering",
        )
        for role in outside:
            assert f'"{role}"' not in block

    def test_navigation_hides_cashflow_from_everyone_else(self) -> None:
        navigation = read(NAVIGATION)
        assert "CASHFLOW_READERS" in navigation
        assert 'key: "cashflow"' in navigation
        assert "hasAnyRole(roles, CASHFLOW_READERS)" in navigation

    def test_the_workspace_refuses_before_it_asks(self) -> None:
        tab = read(TAB)
        assert "const canRead = hasAnyRole(roles, CASHFLOW_READERS);" in tab
        # Every request is gated on canRead, so an ineligible role issues none.
        for call in re.findall(r"useAnswer\(\s*([^,]+),", tab):
            assert "canRead" in call, f"a cashflow request is not gated on canRead: {call}"

    def test_the_project_overview_gates_its_cash_tiles_the_same_way(self) -> None:
        centre = read(COMMAND_CENTRE)
        assert "CASHFLOW_READERS" in centre
        assert "seesCashflow" in centre
        assert "operational && seesCashflow" in centre


class TestGovernanceIsTheServersToDecide:
    """The interface offers an action on role. The server decides on identity."""

    def test_no_dialog_uses_a_browser_prompt(self) -> None:
        for path in workspace_sources():
            source = read(path)
            assert "window.prompt" not in source
            assert "window.confirm" not in source

    def test_a_refusal_is_shown_in_the_servers_own_words(self) -> None:
        tab = read(TAB)
        assert "caught instanceof ApiError ? caught.message" in tab, (
            "a maker/checker or stale-source refusal explains what to do next; "
            "paraphrasing it loses that"
        )

    def test_the_forecast_opening_month_is_derived_not_asked_for(self) -> None:
        """The server requires the start month to be the cutoff's month."""
        forecasts = read(CASHFLOW / "CashflowForecasts.tsx")
        assert "asOfDate.slice(0, 7)" in forecasts
        assert "forecast_start_month: startMonth" in forecasts

    def test_the_discount_rate_is_labelled_per_period(self) -> None:
        forecasts = read(CASHFLOW / "CashflowForecasts.tsx")
        assert "Discount rate per period" in forecasts
        assert "annual" not in forecasts.lower()


class TestNoUnitLevelCashIsInvented:
    """There is no honest per-unit bank balance, so none is drawn.

    Project cash is project cash. Allocating unrestricted cash, a funding gap or
    an IRR to a unit would be inventing an allocation the business does not
    have, and it would look exactly like a figure somebody could act on.
    """

    def test_unit_360_shows_no_project_cash_position(self) -> None:
        unit_files = list((FRONTEND / "components" / "projects" / "inventory").glob("*.tsx"))
        assert unit_files, "the unit record files moved; this guard needs its path updated"
        for path in unit_files:
            source = read(path)
            for forbidden in (
                "unrestricted_cash",
                "funding_requirement",
                "peak_funding_deficit",
                "equity_irr",
            ):
                assert forbidden not in source, (
                    f"{path.name} shows {forbidden}, which is a project figure with "
                    "no honest per-unit allocation"
                )
