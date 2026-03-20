"""
tests/architecture/test_domain_ownership.py

PR-F1: Domain Ownership / Isolation Tests.

Ensures that domain modules remain properly isolated — no module should
reach into another domain's internal concerns.

Rules enforced:
  - Pricing module must not import sales models or finance services.
  - Registry module must not manipulate finance tables directly.
  - Construction module must not depend on pricing logic.
  - Finance module is read-only (aggregation only; no write services).
  - Settings module must not import commercial-domain service logic.

These tests guard long-term architecture integrity by failing fast if a
cross-domain import boundary is violated.
"""

import importlib
import inspect
from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_module_source(module_path: str) -> str:
    """Read source lines of a Python module given its dotted import path."""
    try:
        mod = importlib.import_module(module_path)
        source_file = inspect.getfile(mod)
        return Path(source_file).read_text(encoding="utf-8")
    except (ImportError, TypeError, OSError):
        return ""


def _module_file_text(rel_path: str) -> str:
    """Return the raw text of a source file relative to the repo root."""
    root = Path(__file__).parents[2]
    full = root / rel_path
    if full.exists():
        return full.read_text(encoding="utf-8")
    return ""


# ---------------------------------------------------------------------------
# Test class: Pricing isolation
# ---------------------------------------------------------------------------


class TestPricingModuleIsolation:
    """Pricing module must not reach into sales or finance domain internals."""

    def test_pricing_service_does_not_import_sales_models(self):
        """pricing.service must not import from app.modules.sales.models."""
        source = _module_file_text("app/modules/pricing/service.py")
        assert source, "pricing/service.py not found"
        assert "from app.modules.sales.models" not in source, (
            "pricing.service imports sales models directly — "
            "pricing must only reference units and the pricing engine."
        )

    def test_pricing_service_does_not_import_finance_service(self):
        """pricing.service must not import from app.modules.finance.service."""
        source = _module_file_text("app/modules/pricing/service.py")
        assert source, "pricing/service.py not found"
        assert "from app.modules.finance.service" not in source, (
            "pricing.service imports finance.service — "
            "pricing must not depend on finance aggregation logic."
        )
        assert "import finance" not in source or "modules.finance" not in source, (
            "pricing.service must not import finance module logic."
        )

    def test_pricing_api_does_not_import_sales_service(self):
        """pricing.api must not import from app.modules.sales.service."""
        source = _module_file_text("app/modules/pricing/api.py")
        assert source, "pricing/api.py not found"
        assert "from app.modules.sales.service" not in source, (
            "pricing.api imports sales.service — "
            "API layer must not cross domain service boundaries."
        )

    def test_pricing_repository_does_not_import_sales_repository(self):
        """pricing.repository must not import from app.modules.sales.repository."""
        source = _module_file_text("app/modules/pricing/repository.py")
        assert source, "pricing/repository.py not found"
        assert "from app.modules.sales.repository" not in source, (
            "pricing.repository imports sales.repository — "
            "repositories must not cross domain boundaries."
        )


# ---------------------------------------------------------------------------
# Test class: Registry isolation
# ---------------------------------------------------------------------------


class TestRegistryModuleIsolation:
    """Registry module must not manipulate finance tables directly."""

    def test_registry_service_does_not_import_finance_repository(self):
        """registry.service must not import from app.modules.finance.repository."""
        source = _module_file_text("app/modules/registry/service.py")
        assert source, "registry/service.py not found"
        assert "from app.modules.finance.repository" not in source, (
            "registry.service imports finance.repository — "
            "registry must not read or write finance tables directly."
        )

    def test_registry_models_do_not_reference_finance_models(self):
        """registry.models must not import from app.modules.finance.models."""
        source = _module_file_text("app/modules/registry/models.py")
        assert source, "registry/models.py not found"
        assert "from app.modules.finance" not in source, (
            "registry.models imports finance models — "
            "ORM models must not cross domain table ownership boundaries."
        )

    def test_registry_repository_does_not_import_finance_tables(self):
        """registry.repository must not import finance models."""
        source = _module_file_text("app/modules/registry/repository.py")
        assert source, "registry/repository.py not found"
        assert "from app.modules.finance" not in source, (
            "registry.repository imports finance module — "
            "repository layer must respect domain table ownership."
        )


# ---------------------------------------------------------------------------
# Test class: Construction isolation
# ---------------------------------------------------------------------------


class TestConstructionModuleIsolation:
    """Construction module must not depend on pricing logic."""

    def test_construction_service_does_not_import_pricing_service(self):
        """construction.service must not import from app.modules.pricing.service."""
        source = _module_file_text("app/modules/construction/service.py")
        assert source, "construction/service.py not found"
        assert "from app.modules.pricing.service" not in source, (
            "construction.service imports pricing.service — "
            "construction domain must not depend on pricing logic."
        )

    def test_construction_service_does_not_import_pricing_models(self):
        """construction.service must not import from app.modules.pricing.models."""
        source = _module_file_text("app/modules/construction/service.py")
        assert source, "construction/service.py not found"
        assert "from app.modules.pricing.models" not in source, (
            "construction.service imports pricing models — "
            "construction must not depend on pricing data models."
        )

    def test_construction_models_do_not_reference_sales_models(self):
        """construction.models must not import from app.modules.sales.models."""
        source = _module_file_text("app/modules/construction/models.py")
        assert source, "construction/models.py not found"
        assert "from app.modules.sales.models" not in source, (
            "construction.models imports sales models — "
            "construction ORM layer must not depend on the sales domain."
        )

    def test_construction_api_does_not_import_finance_service(self):
        """construction.api must not import from app.modules.finance.service."""
        source = _module_file_text("app/modules/construction/api.py")
        assert source, "construction/api.py not found"
        assert "from app.modules.finance.service" not in source, (
            "construction.api imports finance.service — "
            "construction API layer must not cross into finance domain."
        )


# ---------------------------------------------------------------------------
# Test class: Finance read-only isolation
# ---------------------------------------------------------------------------


class TestFinanceModuleIsolation:
    """Finance module performs read-only aggregation; it must not write to other domains."""

    def test_finance_service_does_not_import_sales_service(self):
        """finance.service must not import from app.modules.sales.service (write layer)."""
        source = _module_file_text("app/modules/finance/service.py")
        assert source, "finance/service.py not found"
        assert "from app.modules.sales.service" not in source, (
            "finance.service imports sales.service — "
            "finance must only aggregate via repositories, not orchestrate sales operations."
        )

    def test_finance_service_does_not_import_registry_service(self):
        """finance.service must not import from app.modules.registry.service."""
        source = _module_file_text("app/modules/finance/service.py")
        assert source, "finance/service.py not found"
        assert "from app.modules.registry.service" not in source, (
            "finance.service imports registry.service — "
            "finance aggregation must remain independent of registry operations."
        )

    def test_finance_repository_does_not_import_construction_models(self):
        """finance.repository must not import from app.modules.construction.models."""
        source = _module_file_text("app/modules/finance/repository.py")
        assert source, "finance/repository.py not found"
        assert "from app.modules.construction.models" not in source, (
            "finance.repository imports construction models — "
            "finance aggregation scope is limited to sales and collections data."
        )


# ---------------------------------------------------------------------------
# Test class: Settings isolation
# ---------------------------------------------------------------------------


class TestSettingsModuleIsolation:
    """Settings module must not import commercial-domain service logic."""

    def test_settings_service_does_not_import_sales_service(self):
        """settings.service must not import from app.modules.sales.service."""
        source = _module_file_text("app/modules/settings/service.py")
        assert source, "settings/service.py not found"
        assert "from app.modules.sales.service" not in source, (
            "settings.service imports sales.service — "
            "configuration domain must not depend on commercial operations."
        )

    def test_settings_service_does_not_import_finance_service(self):
        """settings.service must not import from app.modules.finance.service."""
        source = _module_file_text("app/modules/settings/service.py")
        assert source, "settings/service.py not found"
        assert "from app.modules.finance.service" not in source, (
            "settings.service imports finance.service — "
            "settings module must remain independent of finance aggregation."
        )

    def test_settings_models_do_not_reference_sales_models(self):
        """settings.models must not import from app.modules.sales.models."""
        source = _module_file_text("app/modules/settings/models.py")
        assert source, "settings/models.py not found"
        assert "from app.modules.sales" not in source, (
            "settings.models imports from the sales domain — "
            "settings ORM models must be self-contained configuration entities."
        )


# ---------------------------------------------------------------------------
# Test class: Module structure completeness
# ---------------------------------------------------------------------------


class TestModuleStructureCompleteness:
    """Each core domain module must have the required structural files."""

    CORE_MODULES = [
        "projects",
        "pricing",
        "sales",
        "payment_plans",
        "finance",
        "registry",
        "construction",
        "settings",
    ]

    REQUIRED_FILES = ["api.py", "models.py", "schemas.py", "service.py", "repository.py"]

    def test_core_modules_have_required_files(self):
        """Each core domain module must contain all 5 required structural files."""
        root = Path(__file__).parents[2] / "app" / "modules"
        missing = []
        for module in self.CORE_MODULES:
            module_dir = root / module
            for filename in self.REQUIRED_FILES:
                if not (module_dir / filename).exists():
                    missing.append(f"{module}/{filename}")
        assert not missing, (
            "Core domain modules are missing required files:\n"
            + "\n".join(f"  {m}" for m in missing)
        )
