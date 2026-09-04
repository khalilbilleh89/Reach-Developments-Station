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
COLLECTIONS = FRONTEND / "components" / "projects" / "collections"
RECEIPT_PANEL = COLLECTIONS / "ReceiptPanel.tsx"
COLLECTION_ACCOUNT = COLLECTIONS / "CollectionAccount.tsx"
BACKEND_PERMISSIONS = ROOT / "app" / "modules" / "cashflow" / "permissions.py"
BACKEND_MODELS = ROOT / "app" / "modules" / "cashflow" / "models.py"
BACKEND_API = ROOT / "app" / "modules" / "cashflow" / "api.py"


def workspace_sources() -> list[Path]:
    """Every file that draws a cashflow figure."""
    return [*sorted(CASHFLOW.glob("*.tsx")), TAB]


def cashflow_namespace() -> str:
    """Just the ``cashflow`` namespace out of an API file that holds many."""
    source = read(API)
    block = source[source.index("export const cashflow = {") :]
    depth = 0
    for index, character in enumerate(block):
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return block[:index]
    raise AssertionError("the cashflow namespace is unbalanced")


def cashflow_api_methods() -> list[str]:
    """The method names on the ``cashflow`` namespace, read from its own source."""
    source = read(API)
    block = source[source.index("export const cashflow = {") :]
    depth = 0
    for index, character in enumerate(block):
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                block = block[:index]
                break
    return re.findall(r"^  (\w+):", block, re.M)


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

    def test_every_reason_the_calculator_can_return_has_words(self) -> None:
        """The map is keyed on the strings the server sends, not on their names.

        Keying it on the Python constant names instead — ``IRR_NO_RETURN``
        rather than ``no_positive_equity_cashflow`` — is a mistake that type
        checks, lints and builds cleanly, and then prints a raw identifier where
        an explanation should be.
        """
        calculator = (ROOT / "app" / "modules" / "cashflow" / "calculator.py").read_text(
            encoding="utf-8"
        )
        reasons = set(re.findall(r'^IRR_[A-Z_]+ = "([a-z_]+)"', calculator, re.MULTILINE))
        assert reasons, "the IRR reason constants moved; this guard needs its pattern updated"
        labels = read(CASHFLOW / "labels.ts")
        for reason in reasons:
            assert f"{reason}:" in labels, f"{reason} would render as a raw code"

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
                assert 'Notice tone="error"' in source, (
                    f"{path.name} handles a failure without saying so in words"
                )


class TestEveryFigureIsDenominated:
    """A bare number beside a denominated one reads as a different currency.

    `money(value, code)` prepends the real code; passing `null` prints the
    figure alone. Types and lint are both happy with that, and the screen shows
    "42,870.40" next to "JOD 1,868,858.34".
    """

    def test_no_component_formats_money_without_a_currency(self) -> None:
        for path in workspace_sources():
            for line in read(path).splitlines():
                assert "money(" not in line or ", null)" not in line, (
                    f"{path.name} renders an undenominated figure: {line.strip()}"
                )


class TestAControlCheckIsNotDenominated:
    """A check's two figures are money on one check and a count on another.

    `CheckOut` carries `expected` and `actual` for both kinds and the response
    does not say which it is, so prefixing the project's currency prints
    "JOD 1" for "one escrow lost its backing". The figures are therefore
    rendered exactly as the server sent them, and the check's own sentence
    carries the meaning. Narrowing that contract is noted as a follow-up rather
    than guessed at here.
    """

    def test_check_figures_are_not_formatted_as_money(self) -> None:
        for name in ("CashflowManagement.tsx", "CashflowForecasts.tsx"):
            source = read(CASHFLOW / name)
            assert "money(check." not in source, (
                f"{name} denominates a control check's figure, which is a count "
                "on some checks and money on others"
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


class TestEveryWriteTheApiOffersIsReachable:
    """A recorded API method nobody calls is a feature the product does not have.

    ``recordRestriction`` existed, was typed, and matched a working endpoint —
    and no screen called it, so a project with no escrow had no way to record
    its first one. The empty state even described the act. Nothing failed:
    lint, types and the browser were all satisfied by a method that was simply
    never reached, which is exactly why this is asserted rather than trusted.
    """

    def test_no_cashflow_api_method_is_dead(self) -> None:
        names = cashflow_api_methods()
        assert len(names) > 20, "the cashflow namespace moved; this guard needs its parser updated"
        callers = "\n".join(read(path) for path in FRONTEND.rglob("*.ts*") if path != API)
        dead = [name for name in names if f"cashflow.{name}(" not in callers]
        assert dead == [], (
            f"{', '.join(dead)} is offered by the API and called by nothing. Either "
            "the product cannot perform it, or the method should not exist."
        )


class TestRestrictingCashStartsFromTheReceiptThatHoldsIt:
    """Escrow attaches to a confirmed buyer receipt, so it is started from one.

    The alternative — a form in the Cashflow workspace asking for a receipt
    identifier — would ask a finance controller to paste a UUID, and would let
    them paste the wrong one. The row already knows which receipt it is.
    """

    def test_a_confirmed_receipt_offers_the_action(self) -> None:
        source = read(RECEIPT_PANEL)
        assert 'receipt.status === "confirmed"' in source, (
            "the escrow action must be offered on the same condition the server "
            "enforces: only confirmed cash can be held back"
        )
        assert "Restrict cash" in source

    def test_the_receipt_identifier_comes_from_the_row(self) -> None:
        source = read(RECEIPT_PANEL)
        assert "cashflow.recordRestriction(projectId, target.id" in source, (
            "the receipt id must travel with the selected row"
        )
        for typed in ("receipt_id", "receiptId"):
            assert f"value={{{typed}}}" not in source, (
                f"{typed} is bound to an input: the operator is being asked to type an identifier"
            )

    def test_only_a_cashflow_recorder_is_offered_it(self) -> None:
        """Being able to read Collections is not permission to move cash."""
        panel = read(RECEIPT_PANEL)
        assert "canRestrictCash && receipt.status" in panel

        account = read(COLLECTION_ACCOUNT)
        assert "hasAnyRole(roles, CASHFLOW_RECORDERS)" in account, (
            "the gate must name the Cashflow recorder set, not a role that happens "
            "to match it today"
        )
        assert "canCollect" not in account.split("canRestrictCash =")[1].split("\n")[0], (
            "the escrow gate must not be derived from Collections access"
        )

    def test_the_amount_ceiling_is_left_to_the_server(self) -> None:
        """The server knows the receipt's worth and what is already held."""
        source = read(RECEIPT_PANEL)
        dialog = source[source.index("function RestrictCashDialog") :]
        for arithmetic in ("parseFloat", "Number(", " - ", "Math."):
            assert arithmetic not in dialog.split("return (")[0], (
                "the dialog is computing a ceiling rather than letting the server "
                "refuse an amount it alone can judge"
            )


class TestAForecastLineIsChosenAndNotTyped:
    """Every governed value is offered as a choice; only figures are typed.

    The dialog previously asked for a construction cost code as free text and
    sent it as ``construction_cost_code_id`` — which meant the only way to
    schedule a trade was to know its UUID. It asked for a category as free text
    against a closed backend set, and it asked the operator to state a financing
    direction the server derives and refuses to be told.
    """

    def test_the_cost_code_is_picked_from_the_project(self) -> None:
        source = read(CASHFLOW / "CashflowForecasts.tsx")
        assert "construction.costCodes(projectId)" in source, (
            "the cost codes must be read from Construction rather than typed"
        )
        assert "{code.code} — {code.name}" in source, "the picker must show a readable label"

    def test_the_cost_code_field_is_not_a_text_input(self) -> None:
        source = read(CASHFLOW / "CashflowForecasts.tsx")
        field = source[source.index("function CostCodeField") :]
        assert "<select" in field
        assert 'className="input"\n            value={costCode}' not in source

    def test_a_project_with_no_cost_codes_says_so(self) -> None:
        source = read(CASHFLOW / "CashflowForecasts.tsx")
        assert "has no construction cost codes yet" in source, (
            "an empty picker is a dead end; the preparer has to be told where to go"
        )

    def test_the_category_is_a_governed_set(self) -> None:
        source = read(CASHFLOW / "CashflowForecasts.tsx")
        assert "DEVELOPMENT_CATEGORY_OPTIONS" in source
        assert "FINANCING_TYPE_OPTIONS" in source
        field = source[source.index("{needsCategory ? (") : source.index("{needsCostCode ?")]
        assert "<select" in field, (
            "the category must be a select over the governed set, not a text input"
        )
        assert "<input" not in field, "the category is still typed"
        assert "categoryOptions.map" in field, "the select must be built from the governed set"

    def test_the_financing_direction_is_not_an_operator_choice(self) -> None:
        """An equity contribution is cash in. That is a fact, not a preference.

        Reading a stored line's direction back is fine and the register does it.
        What may not happen is the preparer being asked to state one: the server
        derives it from the movement type and refuses a stated one that
        disagrees, so the control could only ever agree or be rejected.
        """
        source = read(CASHFLOW / "CashflowForecasts.tsx")
        dialog = source[
            source.index("function ForecastLineDialog") : source.index("function CostCodeField")
        ]
        assert "flow_direction:" not in dialog, (
            "the dialog is still sending a direction the server derives"
        )
        assert "setFlowDirection" not in source, "the direction is still operator state"
        assert '<option value="inflow">' not in source, "the direction is still offered as a choice"

    def test_an_incomplete_line_cannot_be_saved(self) -> None:
        source = read(CASHFLOW / "CashflowForecasts.tsx")
        assert "disabled={!complete}" in source
        assert "(!needsCategory || Boolean(category))" in source, (
            "a blank category must be caught here rather than sent and 422'd"
        )


class TestARejectedForecastIsHistory:
    """Terminal states are named, never inferred from what they are not.

    ``status !== "active" && status !== "superseded"`` reads correctly and
    admits ``rejected``, which the server answers with a 409 — and would admit
    every terminal status invented after it.
    """

    def test_the_open_statuses_match_the_backend(self) -> None:
        frontend = set(
            re.findall(
                r'"(\w+)"',
                read(CASHFLOW / "labels.ts").split("FORECAST_OPEN_STATUSES")[1].split("]")[0],
            )
        )
        backend = set(
            re.findall(
                r"FORECAST_(\w+)",
                read(BACKEND_MODELS).split("FORECAST_OPEN = frozenset({")[1].split("})")[0],
            )
        )
        assert frontend == {name.lower() for name in backend}, (
            f"the workspace thinks {sorted(frontend)} are open; the server thinks "
            f"{sorted(name.lower() for name in backend)}"
        )

    def test_no_action_is_offered_by_a_negative_status_check(self) -> None:
        source = read(CASHFLOW / "CashflowForecasts.tsx")
        assert 'version.status !== "active"' not in source, (
            "a negative check silently admits every terminal status added later"
        )
        # Every governance action names the statuses it is for. The refresh gate
        # is the narrower `isRefreshable` rather than the open set, because an
        # approved version is open and must not be refreshed.
        assert "canPrepare && isRefreshable ?" in source

    def test_editing_a_line_is_narrower_than_refreshing(self) -> None:
        """The server allows an edit on a draft alone, and a refresh while open."""
        source = read(CASHFLOW / "CashflowForecasts.tsx")
        assert "canPrepare && isDraft ?" in source
        assert 'const isDraft = version.status === "draft";' in source


class TestNoForecastYetIsNotAFailure:
    """A project that has never activated a forecast is early, not broken.

    The accuracy endpoint needs a version to measure and answers 404 without
    one. Asking anyway drew a red fault over an ordinary state — and the fix
    must not go the other way and swallow a real fault as an empty state.
    """

    def test_the_accuracy_request_waits_for_the_summary(self) -> None:
        source = read(TAB)
        assert "forecastInForce === true" in source, (
            "the accuracy endpoint must not be asked until the summary says there "
            "is a forecast to measure"
        )
        assert 'summary.status === "ready" ? summary.data.has_active_forecast : null' in source

    def test_the_four_states_stay_apart(self) -> None:
        """Loading, refused, failed and no-forecast are four different sentences."""
        source = read(TAB)
        block = source[
            source.index("const accuracyAnswer") : source.index("const accuracyAnswer") + 700
        ]
        for state in ('status: "loading"', 'status: "failed"', 'status: "denied"'):
            assert state in block, (
                f"the summary's {state} must reach the accuracy card; gating the "
                "request would otherwise render it as silence"
            )

    def test_a_genuine_failure_is_still_drawn_as_a_failure(self) -> None:
        management = read(CASHFLOW / "CashflowManagement.tsx")
        accuracy = management[management.index("function Accuracy(") :]
        assert "if (forecastInForce === false)" in accuracy
        assert 'answer.status === "failed"' in accuracy, (
            "the empty state must not replace the error branch"
        )
        assert accuracy.index("forecastInForce === false") < accuracy.index(
            'status === "failed"'
        ), "only the known no-forecast case gets the empty state; it is checked first and by name"

    def test_the_empty_state_says_what_unlocks_it(self) -> None:
        management = read(CASHFLOW / "CashflowManagement.tsx")
        assert "No forecast in force" in management
        assert "after a governed forecast has been activated" in management


class TestTheApiMirrorsWhatTheEndpointReturns:
    """A wrong generic is invisible until somebody reads a field that is not there.

    ``setForecastLine`` was typed as the whole forecast file. The endpoint
    answers with the one line it wrote, so any caller trusting the type would
    have found ``lines`` undefined at runtime with nothing to explain it.
    """

    def test_the_forecast_line_write_returns_a_line(self) -> None:
        api = read(API)
        call = api[api.index("setForecastLine:") : api.index("refreshCustomerSnapshot:")]
        assert "put<CashflowForecastLine>" in call, (
            "PUT /forecasts/{id}/lines answers with ForecastLineOut, not the detail"
        )

    def test_every_cashflow_generic_matches_the_backend_response_model(self) -> None:
        """The whole namespace, so the next drift is caught rather than reviewed."""
        routes = dict(
            re.findall(
                r'@router\.\w+\(\s*"([^"]+)",?\s*(?:\n\s*)?response_model=schemas\.(\w+)',
                read(BACKEND_API),
            )
        )
        assert routes, "the cashflow routes moved; this guard needs its parser updated"
        pairs = {
            "/forecasts/{version_id}/lines": "CashflowForecastLine",
            "/forecasts/{version_id}": "CashflowForecastDetail",
            "/summary": "CashflowSummary",
            "/monthly": "CashflowMonthly",
        }
        # Scoped to the cashflow namespace: Construction has a forecast-line
        # write of its own at a path that ends the same way, and matching the
        # whole file would compare this module's route against that one's type.
        namespace = cashflow_namespace()
        for route, frontend_type in pairs.items():
            assert route in routes, f"{route} is gone from the cashflow API"
            path = route.replace("{version_id}", "${versionId}")
            index = namespace.index(f"cashflowRoot(projectId)}}{path}")
            window = namespace[max(0, index - 220) : index]
            assert frontend_type in window, (
                f"{route} answers with {routes[route]}; the frontend claims "
                f"something other than {frontend_type}"
            )


class TestTheGovernanceMatrixMirrorsTheServer:
    """Six statuses, three different permissions, and none of them inferred.

    An approved version is the interesting one. It is *open* — it holds the
    project's one open forecast slot — and it is not *refreshable*, because the
    CFO approved the months a particular buyer schedule produced. Wiring a
    refresh button to the open set collapses those two questions into one and
    silently changes what somebody signed for; that is why the two sets are
    named separately on both sides of the wire.
    """

    def test_the_refreshable_set_matches_the_backend(self) -> None:
        frontend = set(
            re.findall(
                r'"(\w+)"',
                read(CASHFLOW / "labels.ts")
                .split("FORECAST_REFRESHABLE_STATUSES")[1]
                .split("]")[0],
            )
        )
        backend = set(
            re.findall(
                r"FORECAST_(\w+)",
                read(BACKEND_MODELS).split("FORECAST_REFRESHABLE = frozenset({")[1].split("})")[0],
            )
        )
        assert frontend == {name.lower() for name in backend}, (
            f"the workspace thinks {sorted(frontend)} may be refreshed; the server "
            f"thinks {sorted(name.lower() for name in backend)}"
        )

    def test_the_two_sets_are_not_the_same_set(self) -> None:
        """If they ever become equal, one of them has been redefined to suit a button."""
        labels = read(CASHFLOW / "labels.ts")
        open_statuses = set(
            re.findall(r'"(\w+)"', labels.split("FORECAST_OPEN_STATUSES")[1].split("]")[0])
        )
        refreshable = set(
            re.findall(r'"(\w+)"', labels.split("FORECAST_REFRESHABLE_STATUSES")[1].split("]")[0])
        )
        assert "approved" in open_statuses, "an approved version still holds the open slot"
        assert "approved" not in refreshable, (
            "an approved version's buyer schedule may not be re-pinned under the "
            "signature it carries"
        )

    def test_the_refresh_button_is_gated_on_refreshable_not_open(self) -> None:
        source = read(CASHFLOW / "CashflowForecasts.tsx")
        assert "forecastIsRefreshable(version.status)" in source
        assert "canPrepare && isRefreshable ?" in source
        assert "canPrepare && isOpen" not in source, (
            "the refresh button is wired to the open set, which includes approved"
        )

    def test_an_approved_version_offers_activation_and_an_exit(self) -> None:
        source = read(CASHFLOW / "CashflowForecasts.tsx")
        assert "canActivate && isApproved ?" in source
        assert "canApprove && isApproved ?" in source, (
            "an approved version that cannot be activated needs a governed way out"
        )
        assert "Withdraw approval" in source

    def test_a_withdrawal_is_not_called_a_rejection(self) -> None:
        """The version really was approved. Saying "Reject" would deny that."""
        source = read(CASHFLOW / "CashflowForecasts.tsx")
        words = source[source.index("const REASON_WORDS") : source.index("const LINE_SOURCE_KINDS")]
        assert "Withdraw this approval" in words
        assert "The approval stays on the record" in words
        withdraw = words[words.index("withdraw: {") :]
        assert "Reject" not in withdraw.split("},")[0]

    def test_a_withdrawal_asks_for_its_reason(self) -> None:
        source = read(CASHFLOW / "CashflowForecasts.tsx")
        assert '"approve" | "reject" | "withdraw"' in source
        assert 'setReasonFor("withdraw")' in source, (
            "withdrawal must go through the reason prompt, not straight to the server"
        )

    def test_no_mutation_is_offered_on_a_terminal_status(self) -> None:
        """Rejected, active and superseded are history, for every role."""
        source = read(CASHFLOW / "CashflowForecasts.tsx")
        for guard in (
            "canPrepare && isDraft ?",
            "canPrepare && isRefreshable ?",
            "canActivate && isApproved ?",
            "canApprove && isApproved ?",
        ):
            assert guard in source, (
                f"{guard} is the only thing standing between a terminal status and a button"
            )
        assert 'version.status !== "active"' not in source
        assert 'version.status !== "superseded"' not in source
