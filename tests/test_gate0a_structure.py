"""Critical Gate 0A classification and operator-navigation contracts."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_gate0a_is_the_canonical_three_pr_mvp2_plan() -> None:
    names = {path.name for path in (ROOT / "docs").iterdir()}
    assert {
        "MVP2_GATE0A_PRODUCT_SPEC.md",
        "MVP2_GATE0A_ROADMAP.md",
        "MVP2_GATE0A_ACCEPTANCE.md",
    } <= names
    # True MVP3 now has its own documents; Gate 0A remains the historical MVP2 plan.
    assert {"MVP3_PRODUCT_SPEC.md", "MVP3_ROADMAP.md", "MVP3_ACCEPTANCE.md"} <= names
    mvp3 = (ROOT / "docs" / "MVP3_PRODUCT_SPEC.md").read_text(encoding="utf-8")
    assert mvp3.startswith("# True MVP3 product specification")
    roadmap = (ROOT / "docs" / "MVP2_GATE0A_ROADMAP.md").read_text(encoding="utf-8")
    assert "2 / 3 merged" in roadmap
    assert "3 / 3 complete" in roadmap
    assert "main as Draft" in roadmap
    assert "G0A-01 — MERGED" in roadmap
    assert "G0A-02 — MERGED" in roadmap
    assert "G0A-03 — FINAL" in roadmap
    assert "True MVP 3 — NOT STARTED" in roadmap
    assert "historical technical debt" in roadmap and "integration/mvp3" in roadmap


def test_final_gate0a_navigation_contains_implemented_destinations() -> None:
    navigation = (ROOT / "frontend/src/components/shell/navigation.ts").read_text(encoding="utf-8")
    development = navigation.split('key: "development"', 1)[1].split('key: "commercial"', 1)[0]
    commercial = navigation.split('key: "commercial"', 1)[1].split('key: "delivery"', 1)[0]
    for label in (
        'label: "Land"',
        'label: "Permits"',
        'label: "Pre-Launch"',
        'label: "Inventory"',
        'label: "Consultant Engineer"',
    ):
        assert label in development
    for label in (
        'label: "Sales"',
        'label: "Payment Plans"',
        'label: "Collections"',
        'label: "Commissions"',
    ):
        assert label in commercial
    for absent in (
        'label: "Pricing"',
        'label: "Sales & Legal"',
    ):
        assert absent not in development + commercial


def test_ordinary_settings_has_no_generic_configuration_destinations() -> None:
    navigation = (ROOT / "frontend/src/components/shell/navigation.ts").read_text(encoding="utf-8")
    settings = navigation.split("export const SETTINGS_NAVIGATION", 1)[1]
    assert 'label: "Reference data"' not in settings
    assert 'label: "Country packs"' not in settings
    assert 'label: "Currencies"' not in settings


def test_issued_retains_its_label_and_completion_is_a_distinct_status() -> None:
    permits = (ROOT / "frontend/src/components/projects/PermitsTab.tsx").read_text(encoding="utf-8")
    assert 'issued: "Obtained / Issued"' in permits
    assert 'completed: "Completed"' in permits
    assert 'issued: ["completed", "expired", "renewed"]' in permits
    assert "completed: []" in permits


def test_new_project_keeps_normalized_contextual_configuration() -> None:
    source = (ROOT / "frontend/src/components/projects/ProjectsRegister.tsx").read_text(
        encoding="utf-8"
    )
    assert "settings.createCurrency" in source
    assert "settings.createCountryPack" in source
    assert "ROLE_SYSTEM_ADMIN" in source
    assert "country_pack_id" in source and "base_currency_id" in source
    assert "Configure the basis first" not in source
