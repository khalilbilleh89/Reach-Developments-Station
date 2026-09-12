#!/usr/bin/env python3
"""Select a small, explicit integration smoke contract; unknown/shared risk refuses."""

from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
from pathlib import Path

import ci_backend_tests as fast

ROOT = Path(__file__).resolve().parents[1]
REVIEWED_WORKFLOW = ".github/workflows/ci.yml"
# The complete reviewed delta, including indentation; no other workflow edit qualifies.
REVIEWED_WORKFLOW_LINES = (
    "-    branches: [main, integration/mvp3]",
    "+    branches: [main, integration/mvp3, integration/mvp3-management]",
    "-    if: github.event_name == 'pull_request' && "
    "github.event.pull_request.base.ref == 'integration/mvp3'",
    "+    if: github.event_name == 'pull_request' && "
    "(github.event.pull_request.base.ref == 'integration/mvp3' || "
    "github.event.pull_request.base.ref == 'integration/mvp3-management')",
)
GUARDS = (
    "tests/test_ci_selector.py",
    "tests/test_ci_workflow.py",
    "tests/test_ci_smoke.py",
    "tests/test_ci_shards.py",
    # Migration changes are admitted only through the exact MIGRATIONS entry
    # below, which adds their named integrity node to the selected contract.
    "tests/test_migrations.py",
    # Pure source-reading contract for this deliberately cross-domain Gate 0A
    # presentation slice. Its domain behaviour is covered by the registered
    # project, settings, cashflow, and prelaunch representatives below.
    "tests/test_gate0a_structure.py",
)
# Reviewed presentation-only architecture contracts. A changed file runs in
# full; this is exact ownership, not a wildcard exemption for shared tests.
PRESENTATION_CONTRACTS = ("tests/test_product_experience.py",)
BACKBONE = (
    "tests/test_config.py::test_defaults_describe_the_service",
    "tests/test_config.py::test_non_postgresql_backends_are_rejected",
    "tests/test_health.py::test_readiness_reports_ok_when_postgresql_is_reachable",
    "tests/test_health.py::test_unmatched_api_paths_answer_with_json_not_the_frontend_404",
    "tests/test_migrations.py::test_the_history_round_trips_from_empty_to_head_and_back",
    "tests/modules/test_auth.py::test_valid_credentials_open_a_session",
    "tests/modules/test_auth.py::test_wrong_password_is_rejected",
    "tests/modules/test_authorization.py::test_ordinary_roles_cannot_read_audit_history",
    "tests/modules/test_audit.py::test_creating_a_user_is_audited",
    "tests/modules/test_audit.py::test_an_audit_event_rolls_back_with_its_transaction",
    "tests/modules/test_strict_requests.py::test_a_refused_request_writes_no_audit_event",
    "tests/test_ci_selector.py::test_every_test_file_in_the_repository_is_claimed_by_something",
    "tests/test_ci_selector.py::test_the_real_dependency_map_has_no_cycle_of_any_length",
    "tests/test_ci_smoke.py::test_every_registered_contract_resolves_to_real_tests",
    "tests/test_ci_smoke.py::test_full_risk_refuses_instead_of_downgrading_or_running_full",
    "tests/test_ci_smoke.py::test_new_domain_refuses_until_registered",
    "tests/test_ci_smoke.py::test_reviewed_workflow_cli",
    "tests/test_ci_smoke.py::test_presentation_contract_has_exact_ownership_and_runs_when_changed",
    "tests/test_ci_smoke.py::test_migrations_need_explicit_ownership_and_integrity_test",
    "tests/test_ci_shards.py::test_all_collected_files_exactly_once_for_any_count",
    "tests/test_ci_workflow.py::test_lane_routing",
    "tests/test_ci_workflow.py::test_actual_aggregator_command_refuses_any_non_success",
    "tests/test_ci_workflow.py::test_shards_are_independent_complete_and_not_fail_fast",
    "tests/test_ci_workflow.py::test_real_postgres_and_structural_checks",
)

# Node IDs intentionally name a few existing, real PostgreSQL cases, not whole
# expensive domain files. A new module must register its contract here.
DOMAIN_SMOKE: dict[str, tuple[str, ...]] = {
    "management_reporting": (
        "tests/modules/test_management_reporting.py::test_capture_roundtrip_board_and_no_backdating",
        "tests/modules/test_management_reporting_security.py::test_phase_hidden_and_later_partial_reader_never_receive_document",
    ),
    "management_actions": (
        "tests/modules/test_portfolio_actions_api.py::test_versioned_lifecycle_and_immutable_history",
        "tests/modules/test_portfolio_actions_api.py::test_action_scope_owner_and_read_only_roles",
        "tests/modules/test_portfolio_actions_api.py::test_risk_action_does_not_resolve_permit",
        "tests/modules/test_portfolio_actions_api.py::test_outlook_horizons_and_action_due_independence",
    ),
    "portfolio": (
        "tests/modules/test_portfolio_risk_pagination.py::test_risk_pages_skip_summaries_and_scale_with_global_order",
        "tests/modules/test_portfolio_risk_pagination.py::test_hidden_high_risks_do_not_change_counts_coverage_or_offsets",
        "tests/modules/test_portfolio_risk_pagination.py::test_cashflow_mismatch_removes_both_candidates_and_keeps_coverage",
        "tests/modules/test_portfolio.py::test_empty_sources_are_unavailable_and_reads_do_not_write",
        "tests/modules/test_portfolio.py::test_safe_cashflow_owner_parity",
        "tests/modules/test_portfolio.py::test_roles_and_phase_scope_exclude_before_sources",
        "tests/modules/test_portfolio.py::test_foreign_and_mixed_cash_refuse_without_losing_collections",
        "tests/modules/test_portfolio.py::test_unauthorized_large_sources_and_phase_project_do_not_contribute",
        "tests/modules/test_portfolio.py::test_populated_owner_parity_and_allocation_dedup",
        "tests/modules/test_portfolio_governance.py::test_governed_forecast_and_opening_anchor_exact_parity",
        "tests/modules/test_portfolio_risks.py::test_receipts_refund_and_unconfirmed_golden",
    ),
    "settings": (
        "tests/modules/test_settings.py::test_a_currency_code_is_normalised_to_upper_case",
        "tests/modules/test_settings.py::test_a_country_pack_requires_an_active_currency",
        "tests/modules/test_settings.py::test_a_tax_rate_keeps_decimal_precision",
    ),
    "projects": (
        "tests/modules/test_projects.py::test_a_project_is_created_with_its_configured_basis",
        "tests/modules/test_projects.py::test_the_basis_may_be_corrected_during_setup",
        "tests/modules/test_projects.py::test_the_basis_locks_once_the_project_leaves_setup",
        "tests/modules/test_project_access.py::test_an_inaccessible_project_reports_not_found_rather_than_forbidden",
    ),
    "inventory": (
        "tests/modules/test_units.py::test_a_unit_is_created_with_its_four_status_dimensions",
        "tests/modules/test_units.py::test_correcting_a_unit_reference_never_changes_identity",
        "tests/modules/test_phase_access.py::test_the_register_never_returns_a_hidden_unit",
        "tests/modules/test_inventory_integrity.py::test_a_weighted_total_cannot_mix_units_of_measure",
    ),
    "pricing": (
        "tests/modules/test_price_versions.py::test_activation_is_the_only_thing_that_sets_pricing_approved",
        "tests/modules/test_price_versions.py::test_the_submitter_cannot_approve_their_own_price",
        "tests/modules/test_pricing_calculator.py::test_everything_together_still_reconciles_exactly",
    ),
    "sales": (
        "tests/modules/test_sale_contracts.py::test_activation_contracts_the_unit",
        "tests/modules/test_sale_contracts.py::test_a_contract_copies_the_reservations_frozen_quote_exactly",
        "tests/modules/test_sales_security.py::test_a_contract_in_a_hidden_phase_answers_as_missing",
    ),
    "payment_plans": (
        "tests/modules/test_payment_plan_lifecycle.py::test_a_reconciled_schedule_can_be_put_forward_and_sanctioned",
        "tests/modules/test_payment_plan_lifecycle.py::test_the_submitter_cannot_sanction_their_own_schedule",
        "tests/modules/test_payment_plan_reconciliation.py::test_the_rounding_residual_is_allocated_not_dropped",
    ),
    "collections": (
        "tests/modules/test_collection_receipts.py::TestRecording::test_a_recorded_receipt_is_not_yet_cash",
        "tests/modules/test_collection_receipts.py::TestConfirmation::test_confirmation_makes_it_cash",
        "tests/modules/test_collection_receipts.py::TestConfirmation::test_holding_both_roles_does_not_make_one_person_a_maker_checker_pair",
        "tests/modules/test_collection_spa_progress.py::test_percentage_uses_spa_tax_and_buyer_fees",
    ),
    "unit_economics": (
        "tests/modules/test_unit_economics_calculator.py::TestTheProfitLayers::test_the_worked_example",
        "tests/modules/test_unit_economics_calculator.py::TestDividingAPool::test_every_pool_reconciles_exactly",
        "tests/modules/test_unit_economics_security.py::TestWhoMaySeeAMargin::test_a_sales_advisor_may_not_see_cost_or_margin",
    ),
    "construction": (
        "tests/modules/test_construction_stages.py::test_completion_correction_and_stale_write",
        "tests/modules/test_construction_stages.py::test_stage_validation_and_read_only_roles",
        "tests/modules/test_construction_stage_independence.py",
    ),
    "cashflow": (
        "tests/modules/test_cashflow_development_movements.py::TestRecordingIsNotPaying::test_a_recorded_movement_is_not_yet_cash",
        "tests/modules/test_cashflow_development_movements.py::TestRecordingIsNotPaying::test_confirmation_by_a_second_person_makes_it_cash",
        "tests/modules/test_cashflow_development_movements.py::TestRecordingIsNotPaying::test_the_recorder_may_not_confirm_their_own_movement",
        "tests/modules/test_cashflow_concurrency.py::TestOneConfirmationPerMovement::test_two_confirmations_of_one_development_movement_leave_one_truth",
        "tests/modules/test_cashflow_security.py::TestAPartialViewIsRefusedNotFiltered::test_a_phase_scoped_reader_is_refused_every_project_total",
    ),
    "prelaunch": (
        "tests/modules/test_prelaunch.py::test_contextual_setup_does_not_grant_configuration_admin",
        "tests/modules/test_prelaunch.py::test_project_manager_records_the_same_unconfirmed_cashflow_row",
        "tests/modules/test_prelaunch.py::test_maker_checker_confirmation_and_reversal_count_the_row_once",
        "tests/modules/test_prelaunch.py::test_prelaunch_never_grants_broader_cash_authority",
        "tests/modules/test_prelaunch.py::test_prelaunch_lifecycle_is_cross_domain_independent",
        "tests/modules/test_prelaunch.py::test_sales_advisor_and_phase_scoped_reader_get_no_prelaunch_details",
        "tests/modules/test_prelaunch.py::test_utilities_row_survives_refused_downgrade_to_0015",
    ),
    "project_analysis": (
        "tests/modules/test_project_analysis.py::test_empty_sources_and_reads_have_no_side_effects",
    ),
    "consultant_engineering": (
        "tests/modules/test_consultant_engineering.py::test_create_activate_and_deliverable_lifecycle",
        "tests/modules/test_consultant_engineering.py::test_second_activation_conflicts",
        "tests/modules/test_consultant_engineering.py::test_commercial_reader_is_refused",
    ),
    "commissions": (
        "tests/modules/test_commissions_review.py::test_financial_independence_and_immutable_history",
        "tests/modules/test_commissions.py::test_150k_golden_decimal_calculation",
        "tests/modules/test_commissions.py::test_reconciliation_and_maker_checker",
        "tests/modules/test_commissions.py::test_partial_base_and_invalid_terms",
    ),
    "audit": (
        "tests/modules/test_audit.py::test_configuration_changes_are_audited",
        "tests/modules/test_audit.py::test_passwords_and_tokens_never_reach_the_audit_trail",
    ),
    "cutover": (
        "tests/modules/test_cutover_manifest.py::test_one_edited_byte_refuses_the_apply",
        "tests/modules/test_cutover_manifest.py::test_an_unsealed_manifest_cannot_authorise_an_apply",
    ),
}

# Exact reviewed ownership: names alone must not certify an arbitrary migration.
# New revisions register BOTH their owner and their own integrity test(s).
MIGRATIONS: dict[str, tuple[str, tuple[str, ...]]] = {
    "0025_prelaunch_master.py": (
        "cashflow",
        ("tests/modules/test_prelaunch_amendments.py::test_master_migration_guards_and_rollback",),
    ),
    "0026_common_areas.py": (
        "inventory",
        ("tests/modules/test_feasibility.py::test_common_area_migration_roundtrip",),

    ),
    "0024_merge_permits_inventory.py": (
        "projects",
        ("tests/test_migrations.py::test_parallel_permit_and_inventory_histories_converge",),
    ),
    "0023_permit_removal.py": ("projects", ("tests/modules/test_permit_entry_removal.py",)),
    "0023_inventory_options.py": (
        "inventory",
        (
            "tests/modules/test_inventory_configuration.py::test_migration_snapshots_choices_without_changing_units",
        ),
    ),
    "0022_land_analytics.py": (
        "projects",
        ("tests/modules/test_project_land_analytics.py",),
    ),
    "0021_sales_negotiated_price.py": ("sales", ("tests/modules/test_sales_negotiated_price.py",)),
    "0020_management_reporting.py": (
        "management_reporting",
        ("tests/modules/test_management_reporting_integrity.py",),
    ),
    "0019_management_actions.py": (
        "management_actions",
        ("tests/modules/test_migration_management_actions.py",),
    ),
    "0013_unit_master.py": (
        "inventory",
        ("tests/modules/test_migration_inventory_unit_master.py",),
    ),
    "0014_direct_unit_price.py": (
        "pricing",
        ("tests/modules/test_migration_inventory_unit_master.py",),
    ),
    "0015_construction_stages.py": (
        "construction",
        ("tests/test_migrations.py::test_construction_stages_upgrade_schema_and_clean_downgrade",),
    ),
    "0016_prelaunch_utilities.py": (
        "cashflow",
        (
            "tests/test_migrations.py::test_prelaunch_utilities_widens_only_the_development_category_check",
            "tests/modules/test_prelaunch.py::test_utilities_row_survives_refused_downgrade_to_0015",
        ),
    ),
    "0017_consultant_commissions.py": (
        "consultant_engineering",
        (
            "tests/test_migrations.py::test_the_history_round_trips_from_empty_to_head_and_back",
            "tests/modules/test_consultant_engineering.py::test_create_activate_and_deliverable_lifecycle",
            "tests/modules/test_commissions.py::test_150k_golden_decimal_calculation",
        ),
    ),
}


class SmokeRefused(ValueError):
    """Not eligible for smoke-only review; never fall back to Full implicitly."""


def validate_contract(nodes: tuple[str, ...] | list[str], root: Path = ROOT) -> None:
    """Catch deleted files/functions without importing or executing domain tests."""
    if not nodes:
        raise SmokeRefused("Empty Backend Smoke contract")
    for node in nodes:
        parts = node.split("::")
        path = root / parts[0]
        if not path.is_file() or not parts[0].startswith("tests/"):
            raise SmokeRefused(f"Missing smoke test: {node}")
        body = ast.parse(path.read_text(encoding="utf-8")).body
        for name in parts[1:]:
            found = next(
                (
                    item
                    for item in body
                    if isinstance(item, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                    and item.name == name
                ),
                None,
            )
            if found is None:
                raise SmokeRefused(f"Missing smoke test: {node}")
            body = found.body


def select(changed: list[str], root: Path = ROOT) -> tuple[list[str], list[str]]:
    domains: set[str] = set()
    nodes = set(BACKBONE)
    # Model imports in Alembic's environment are the ordinary companion to a
    # reviewed, registered domain migration. Alone, an env.py edit remains
    # shared infrastructure and is refused below.
    has_registered_migration = any(
        raw.replace("\\", "/").startswith(fast.MIGRATION_VERSIONS_PREFIX)
        and Path(raw.replace("\\", "/")).name in MIGRATIONS
        for raw in changed
    )
    for raw in changed:
        path = raw.replace("\\", "/")
        if path in (
            *fast.FULL_RISK_PATHS,
            "app/modules/inventory/custom_fields.py",
        ) or path.startswith((*fast.FULL_RISK_PREFIXES, ".github/")):
            raise SmokeRefused(
                f"{path}: system-wide blast radius; not eligible for Gate 0A Smoke. "
                "Avoid the shared change or obtain explicit full-gate exception/review."
            )
        if path.startswith(fast.MIGRATION_VERSIONS_PREFIX):
            migration = MIGRATIONS.get(Path(path).name)
            if not migration or not migration[1]:
                raise SmokeRefused(
                    f"Unclassified migration {path}: "
                    "register its owner and integrity tests for review"
                )
            domain, tests = migration
            domains.add(domain)
            nodes.update(tests)
        elif path == "app/db/migrations/env.py" and has_registered_migration:
            continue
        elif path.startswith("app/db/"):
            raise SmokeRefused(
                f"{path}: shared DB infrastructure requires explicit full-gate review"
            )
        elif path.startswith("app/modules/"):
            domain = fast.domain_of_module_path(path)
            if domain is None:
                raise SmokeRefused(f"Cannot classify {path}")
            domains.add(domain)
        elif path.startswith(fast.CUTOVER_PACKAGE) or path.startswith(fast.CUTOVER_FIXTURES):
            domains.add("cutover")
        elif path.startswith("tests/"):
            if path in PRESENTATION_CONTRACTS:
                nodes.add(path)
                continue
            if path in GUARDS:
                continue
            owners = {
                domain
                for domain in fast.DOMAIN_TEST_PREFIXES
                if path in fast.tests_for_domain(domain, [path])
            }
            if not owners:
                raise SmokeRefused(
                    f"Unclassified/shared test change {path}; "
                    "register ownership or request full-gate review"
                )
            # A large new regression file does not silently turn Smoke into Full.
            # The registered representatives run here; Fast/Full still discover all.
            domains.update(owners)
        elif path in {
            "scripts/ci_backend_smoke.py",
            "scripts/ci_backend_shards.py",
            fast.SELECTOR_SCRIPT,
            "app/main.py",
        }:
            continue
        elif path.startswith("frontend/"):
            for domain in DOMAIN_SMOKE:
                if f"/{domain}/" in path or path.endswith(f"/api/{domain}.ts"):
                    domains.add(domain)
        elif path.startswith("docs/") or path.endswith(".md") or path in fast.INERT_FILES:
            continue
        else:
            raise SmokeRefused(
                f"Unclassified infrastructure {path}; explicit full-gate review required"
            )
    for domain in sorted(domains):
        if not DOMAIN_SMOKE.get(domain):
            raise SmokeRefused(
                f"New domain '{domain}' has no Backend Smoke contract. "
                "Register representative smoke tests before this integration PR can merge."
            )
        nodes.update(DOMAIN_SMOKE[domain])
    selected = sorted(nodes)
    validate_contract(selected, root)
    return selected, sorted(domains)


def reviewed_workflow_diff(base: str) -> str:
    """Read committed base-to-HEAD changes, never the working tree or final shape."""
    try:
        return subprocess.run(
            [
                "git",
                "diff",
                "--no-ext-diff",
                "--no-textconv",
                "--no-renames",
                "--no-color",
                "--unified=0",
                base,
                "HEAD",
                "--",
                REVIEWED_WORKFLOW,
            ],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except subprocess.CalledProcessError as error:
        raise fast.CannotDiff(f"could not inspect reviewed workflow against {base}") from error


def is_reviewed_workflow_delta(diff: str) -> bool:
    """Exactly two one-line substitutions in an ordinary file; metadata also fails closed."""
    lines = diff.splitlines()
    if len(lines) < 4 or lines[0] != f"diff --git a/{REVIEWED_WORKFLOW} b/{REVIEWED_WORKFLOW}":
        return False
    if not re.fullmatch(r"index [0-9a-f]+\.\.[0-9a-f]+ 100644", lines[1]):
        return False
    if lines[2:4] != [f"--- a/{REVIEWED_WORKFLOW}", f"+++ b/{REVIEWED_WORKFLOW}"]:
        return False
    hunks = [line for line in lines[4:] if line.startswith("@@")]
    if len(hunks) != 2 or any(not re.fullmatch(r"@@ -\d+ \+\d+ @@.*", h) for h in hunks):
        return False
    return tuple(line for line in lines[4:] if not line.startswith("@@")) == REVIEWED_WORKFLOW_LINES


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base")
    parser.add_argument("--changed", nargs="*")
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    try:
        changed = (
            args.changed
            if args.changed is not None
            else fast.changed_files(args.base or "origin/integration/mvp3")
        )
        # Only an explicit, real PR diff may remove this one path from full-risk review.
        # --changed cannot supply or forge the companion-test evidence.
        if (
            args.changed is None
            and args.base is not None
            and REVIEWED_WORKFLOW in changed
            and "tests/test_ci_workflow.py" in changed
            and is_reviewed_workflow_delta(reviewed_workflow_diff(args.base))
        ):
            changed = [path for path in changed if path != REVIEWED_WORKFLOW]
        paths, domains = select(changed)
    except (SmokeRefused, fast.CannotDiff, OSError, SyntaxError) as error:
        print(f"Backend Smoke refused: {error}", file=sys.stderr)
        return 1
    print(f"Backend Smoke: direct domains {', '.join(domains) or 'backbone only'}")
    print("\n".join(paths))
    print("Smoke is not full regression evidence and cannot certify a main merge.")
    if args.out:
        Path(args.out).write_text("\n".join(paths) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
