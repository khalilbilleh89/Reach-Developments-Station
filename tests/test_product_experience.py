"""What Product Experience 3.0 is not allowed to do.

PR-V2-00 rebuilt how the product looks — tokens, shell, headers, registers,
forms, the record file — without moving one business rule into the browser.
That is the line worth guarding, and it cannot be guarded by a screenshot.
Every assertion here reads the frontend source and checks a structural rule
about presentation, the same idiom as ``test_ux_copy.py`` and
``test_cashflow_workspace.py``, and for the same reason: these are defects a
redesign commits silently, and each has a specific, expensive failure mode.

There is no JavaScript test runner in this repository and this file does not
introduce one. What it can prove without one is exactly the class of thing
that matters here: that the design system got simpler rather than larger,
that no arithmetic crept into the browser during the restyle, that a role
which may not read a module still never asks for it, that the overlays kept
their semantics, and that the shell's structure survived.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend" / "src"
STYLESHEET = FRONTEND / "app" / "globals.css"
UI = FRONTEND / "components" / "ui"
UI_INDEX = UI / "index.ts"
SHELL = FRONTEND / "components" / "shell"
NAVIGATION = SHELL / "navigation.ts"
APP_SHELL = SHELL / "AppShell.tsx"
SIDEBAR = SHELL / "AppSidebar.tsx"
SWITCHER = SHELL / "ProjectSwitcher.tsx"
ROLES = FRONTEND / "lib" / "roles.ts"
DASHBOARD = FRONTEND / "components" / "dashboard"
COMMAND_CENTRE = DASHBOARD / "ProjectCommandCenter.tsx"
PROJECTS = FRONTEND / "components" / "projects"
UNIT_360 = PROJECTS / "inventory" / "UnitDetailPanel.tsx"
BACKEND_MODULES = ROOT / "app" / "modules"

#: The screens PR-V2-00 upgraded as the proof of the system. The arithmetic
#: guards read these; the structural guards read everything.
REPRESENTATIVE_SCREENS = (
    PROJECTS / "ProjectsRegister.tsx",
    COMMAND_CENTRE,
    DASHBOARD / "AttentionPanel.tsx",
    DASHBOARD / "ProjectPlate.tsx",
    PROJECTS / "InventoryTab.tsx",
    UNIT_360,
    PROJECTS / "inventory" / "unit" / "UnitSummary.tsx",
    PROJECTS / "inventory" / "unit" / "UnitPricingSection.tsx",
    PROJECTS / "SalesTab.tsx",
    PROJECTS / "CollectionsTab.tsx",
    PROJECTS / "UnitEconomicsTab.tsx",
    PROJECTS / "cashflow" / "CashflowOverview.tsx",
)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def frontend_sources() -> list[Path]:
    """Every TypeScript file the product ships."""
    return sorted(
        path
        for pattern in ("**/*.ts", "**/*.tsx")
        for path in FRONTEND.glob(pattern)
        if "node_modules" not in path.parts
    )


def stylesheet_without_comments() -> str:
    return re.sub(r"/\*.*?\*/", "", read(STYLESHEET), flags=re.S)


def top_level_selectors(css: str) -> list[str]:
    """Every selector that opens a block at the top level, in order.

    A tiny brace walker rather than a CSS parser: the stylesheet is
    hand-written and the question is only which selectors open a block at
    depth zero. Rules nested inside ``@media`` are intentionally not counted —
    a responsive override of an existing rule is what a media query is for.
    """
    depth = 0
    buffer: list[str] = []
    selectors: list[str] = []
    for character in css:
        if character == "{":
            if depth == 0:
                selectors.append(" ".join("".join(buffer).split()))
            depth += 1
            buffer = []
        elif character == "}":
            depth -= 1
            buffer = []
        else:
            buffer.append(character)
    return selectors


def class_names_declared(css: str) -> set[str]:
    """Every ``.class`` a selector in the stylesheet names."""
    depth = 0
    buffer: list[str] = []
    names: set[str] = set()
    for character in css:
        if character == "{":
            names.update(re.findall(r"\.([A-Za-z_][\w-]*)", "".join(buffer)))
            depth += 1
            buffer = []
        elif character == "}":
            depth -= 1
            buffer = []
        else:
            buffer.append(character)
    return names


def role_set_from_backend(module: str, name: str) -> set[str]:
    source = read(BACKEND_MODULES / module / "permissions.py")
    block = source.split(name)[1].split(")")[0]
    return set(re.findall(r'"([a-z_]+)"', block))


def role_set_from_frontend(name: str) -> set[str]:
    source = read(ROLES)
    block = source.split(f"{name}: Roles = new Set(")[1].split(")")[0]
    return set(re.findall(r'"([a-z_]+)"', block))


# --------------------------------------------------------------------------- #
# The design system got simpler, not larger
# --------------------------------------------------------------------------- #


class TestThereIsOnePrimitiveSystem:
    """No aliases, no second copies, no ``Card2``.

    A redesign is where a component library grows a parallel set of "new"
    primitives beside the old ones, and two screens then drift apart while
    both believing they use the canonical one. The rule is that the canonical
    primitive is replaced, never duplicated.
    """

    RETIRED_ALIASES = ("Panel", "Stat", "StatRow", "FilterBar")

    def test_the_index_exports_no_retired_alias(self) -> None:
        index = read(UI_INDEX)
        exported = set(re.findall(r"\b([A-Z]\w+)\b", index))
        for alias in self.RETIRED_ALIASES:
            assert alias not in exported, (
                f"components/ui exports `{alias}`, an alias PR-V2-00 retired. "
                "Use the canonical primitive instead of keeping a second name for it."
            )

    def test_no_screen_imports_a_retired_alias(self) -> None:
        pattern = re.compile(r"import\s*\{([^}]*)\}\s*from\s*\"@/components/ui\"")
        for path in frontend_sources():
            for block in pattern.findall(read(path)):
                names = {name.strip().split(" as ")[0] for name in block.split(",")}
                for alias in self.RETIRED_ALIASES:
                    assert alias not in names, f"{path.name} still imports the retired `{alias}`"

    @pytest.mark.parametrize("suffix", ["2", "New", "Modern", "Legacy", "Old", "V2", "V3"])
    def test_no_primitive_is_a_second_version_of_another(self, suffix: str) -> None:
        for path in UI.glob("*.tsx"):
            assert not path.stem.endswith(suffix), (
                f"{path.name} looks like a second copy of a primitive. Replace the canonical one."
            )
            for name in re.findall(r"export function ([A-Z]\w+)", read(path)):
                assert not name.endswith(suffix), (
                    f"{path.name} exports `{name}`, a parallel primitive"
                )

    def test_every_primitive_is_exported_from_one_index(self) -> None:
        index = read(UI_INDEX)
        for path in UI.glob("*.tsx"):
            for name in re.findall(r"export function ([A-Z]\w+)", read(path)):
                assert re.search(rf"\b{name}\b", index), (
                    f"`{name}` in {path.name} is not exported from the index"
                )

    def test_no_module_defines_its_own_copy_of_a_primitive(self) -> None:
        """A `Card` or `Button` declared outside components/ui is a fork."""
        canonical = set(
            re.findall(r"export function ([A-Z]\w+)", "".join(read(p) for p in UI.glob("*.tsx")))
        )
        for path in frontend_sources():
            if UI in path.parents:
                continue
            for name in re.findall(r"(?:export )?function ([A-Z]\w+)\(", read(path)):
                assert name not in canonical, (
                    f"{path.name} declares its own `{name}`; "
                    "the canonical one lives in components/ui"
                )


class TestTheStylesheetIsOneLayer:
    """One rule per selector, one token per value, no colour outside the tokens.

    The previous stylesheet had grown a "refinements" section that re-declared
    thirteen selectors further down the file and won by being later. That is
    how a design system becomes larger every release while looking the same:
    nobody can change a rule without finding its shadow. Product Experience 3.0
    has no shadows, and this keeps it that way.
    """

    def test_no_top_level_selector_is_declared_twice(self) -> None:
        selectors = top_level_selectors(stylesheet_without_comments())
        seen: dict[str, int] = {}
        for selector in selectors:
            if selector.startswith("@"):
                continue
            seen[selector] = seen.get(selector, 0) + 1
        duplicates = sorted(selector for selector, count in seen.items() if count > 1)
        assert duplicates == [], (
            "these selectors are declared twice at the top level; fold the second into the first: "
            + ", ".join(duplicates)
        )

    def test_the_tokens_are_declared_once(self) -> None:
        selectors = [s for s in top_level_selectors(stylesheet_without_comments()) if s == ":root"]
        assert len(selectors) == 1, "the token block is split; every token lives in one :root"

    def test_no_literal_colour_outside_the_token_block(self) -> None:
        """A hex colour outside ``:root`` is a magic value a token cannot reach."""
        css = stylesheet_without_comments()
        root_start = css.index(":root {")
        root_end = css.index("}", root_start)
        outside = css[:root_start] + css[root_end:]
        literals = [
            match.group(0)
            for match in re.finditer(r"#[0-9a-fA-F]{3,8}\b", outside)
            # The select control's chevron is a data URI, where a custom
            # property cannot be used. That is the one permitted literal.
            if "url(" not in outside[max(0, match.start() - 240) : match.start()].split("\n")[-1]
        ]
        assert literals == [], f"literal colours outside :root: {literals}"

    def test_no_component_carries_a_literal_colour(self) -> None:
        for path in frontend_sources():
            source = read(path)
            assert not re.search(r"(?:color|background)\s*:\s*[\"']?#[0-9a-fA-F]{3,8}", source), (
                f"{path.name} hard-codes a colour; use a token"
            )
            assert not re.search(
                r"style=\{\{[^}]*(?:color|background|fontSize|padding|margin)\s*:", source
            ), (
                f"{path.name} sets a visual property inline; "
                "that belongs in the stylesheet under a token"
            )

    def test_every_class_the_stylesheet_declares_is_used(self) -> None:
        """Dead CSS is the other way a system grows without anybody noticing."""
        declared = class_names_declared(stylesheet_without_comments())
        source = "\n".join(read(path) for path in frontend_sources())
        unused = []
        for name in sorted(declared):
            if name in source:
                continue
            # A class composed at render time — `badge-${tone}`, `notice-${tone}`.
            stem = name.rsplit("-", 1)[0]
            if "-" in name and re.search(re.escape(stem) + r"-\$\{", source):
                continue
            unused.append(name)
        assert unused == [], f"classes the stylesheet declares and no component uses: {unused}"

    def test_every_class_a_component_uses_is_declared(self) -> None:
        """The reverse guard: a class name typed in a component must exist."""
        declared = class_names_declared(stylesheet_without_comments())
        # Names a component may use that the stylesheet does not need to draw.
        structural = {"app", "mobile-navigation"}
        missing: set[str] = set()
        for path in frontend_sources():
            for literal in re.findall(r'className="([^"]+)"', read(path)):
                for name in literal.split():
                    if name not in declared and name not in structural:
                        missing.add(f"{path.name}:{name}")
        assert missing == set(), (
            f"classes used but never declared in the stylesheet: {sorted(missing)}"
        )

    def test_there_is_exactly_one_light_theme(self) -> None:
        """No dark mode by accident.

        A dark theme is a real piece of work — every token, every status
        colour, every contrast pair — and half of one is worse than none. If
        one is ever added it is added deliberately, at the token layer, with
        every pair checked; until then nothing in the stylesheet responds to
        the operating system's preference.
        """
        css = read(STYLESHEET)
        assert "color-scheme: light" in css
        assert "prefers-color-scheme" not in css
        assert "data-theme" not in css

    def test_reduced_motion_is_respected(self) -> None:
        assert "prefers-reduced-motion" in read(STYLESHEET)

    def test_no_decorative_gradient_or_glass(self) -> None:
        """Modern means better hierarchy, not more decoration."""
        css = stylesheet_without_comments()
        assert "backdrop-filter" not in css, "no glassmorphism"
        gradients = re.findall(r"background(?:-image)?:\s*(?:radial|linear)-gradient", css)
        # The one permitted gradient is the two-pixel ink hairline over a command surface.
        assert len(gradients) <= 1, f"decorative gradients: {len(gradients)}"


# --------------------------------------------------------------------------- #
# The browser lays out, labels, filters, navigates and formats. Never calculates.
# --------------------------------------------------------------------------- #


class TestTheBrowserDoesNoFinancialArithmetic:
    """The restyle moved no business truth into React.

    Money crosses the wire as decimal strings because a figure put through a
    JavaScript float comes back subtly different from the one the ledger will
    enforce. A redesign is the moment somebody is most tempted to "just add up
    the column" for a nicer total, and this is where that is caught.
    """

    def test_no_screen_parses_money_into_a_float(self) -> None:
        for path in frontend_sources():
            source = read(path)
            for forbidden in ("parseFloat(", ".toFixed(", "Intl.NumberFormat"):
                assert forbidden not in source, f"{path.name} uses {forbidden}"

    def test_no_representative_screen_reduces_a_series(self) -> None:
        for path in REPRESENTATIVE_SCREENS:
            assert ".reduce(" not in read(path), (
                f"{path.name} reduces a series. Every total on these screens arrives computed."
            )

    def test_no_representative_screen_does_arithmetic_on_a_response_field(self) -> None:
        arithmetic = re.compile(
            r"\b(?:row|unit|summary|totals|data|economic|economics|cost|payable|position|price|window|project)"
            r"\.\w+\s*[-+*/]\s"
        )
        for path in REPRESENTATIVE_SCREENS:
            for line in read(path).splitlines():
                stripped = line.strip()
                if stripped.startswith(("//", "*")):
                    continue
                assert not arithmetic.search(line), (
                    f"{path.name} computes from a response field: {stripped}"
                )

    def test_the_formatting_layer_never_constructs_a_number_from_money(self) -> None:
        source = read(FRONTEND / "lib" / "format.ts")
        assert "Number(" not in source.replace("`Number(value) > 0`", "")
        assert "parseFloat" not in source

    def test_the_command_centre_states_only_server_figures(self) -> None:
        """Every `PositionFigure` on the overview is a response field, or a format of one."""
        centre = read(COMMAND_CENTRE)
        for value in re.findall(r"<PositionFigure[^>]*?value=\{([^}]*)\}", centre, flags=re.S):
            assert not re.search(r"[-+*/]\s*\d", value), (
                f"a position figure is computed: {value.strip()}"
            )
        # The comments may name what is absent; the code may not draw it.
        code = re.sub(r"/\*.*?\*/", "", centre, flags=re.S)
        code = "\n".join(line for line in code.splitlines() if not line.strip().startswith("//"))
        for invented in ("health", "trend", "projection", "score"):
            assert invented not in code.lower(), (
                f"the overview draws a {invented} the API does not return"
            )


# --------------------------------------------------------------------------- #
# What a role may not read, the browser does not ask for
# --------------------------------------------------------------------------- #


class TestOnlyEntitledReadersAsk:
    """Visual redesign must not weaken access control. Not fetch-then-hide."""

    @pytest.mark.parametrize(
        ("frontend_set", "module", "backend_set"),
        [
            ("CONSTRUCTION_READERS", "construction", "CONSTRUCTION_READER_ROLES"),
            ("CASHFLOW_READERS", "cashflow", "CASHFLOW_READER_ROLES"),
        ],
    )
    def test_the_frontend_role_set_matches_the_backend(
        self, frontend_set: str, module: str, backend_set: str
    ) -> None:
        expected = role_set_from_backend(module, backend_set)
        actual = role_set_from_frontend(frontend_set)
        assert actual == expected, (
            f"the interface offers {module} to {actual - expected} the server refuses, "
            f"or hides it from {expected - actual} the server would answer"
        )

    def test_every_command_centre_request_is_gated_on_its_reader_set(self) -> None:
        """A module summary is asked for only on behalf of a role the server answers.

        The overview grew a Delivery section in PR-V2-00, read from the
        construction summary. Design / Engineering may read that and may not
        read Unit Economics, so the two gates are different and stay different.
        """
        centre = read(COMMAND_CENTRE)
        gates = {
            "pricing.overview": "seesPricing",
            "pricing.register": "seesPricing",
            "sales.register": "seesSales",
            "paymentPlans.register": "seesPlans",
            "collections.summary": "seesCollections",
            "unitEconomics.summary": "seesEconomics",
            "construction.summary": "seesConstruction",
            "cashflow.summary": "seesCashflow",
        }
        for call, gate in gates.items():
            pattern = re.compile(r"useAnswer<\w+>\(\s*([^,]+),\s*\(\)\s*=>\s*" + re.escape(call))
            match = pattern.search(centre)
            assert match, f"the overview no longer requests {call} through useAnswer"
            assert gate in match.group(1), (
                f"{call} is requested without `{gate}`: {match.group(1).strip()}"
            )
        for flag, role_set in (
            ("seesPricing", "INTERNAL_PRICE_READERS"),
            ("seesSales", "SALES_READERS"),
            ("seesPlans", "PLAN_READERS"),
            ("seesCollections", "COLLECTION_READERS"),
            ("seesEconomics", "ECONOMICS_READERS"),
            ("seesConstruction", "CONSTRUCTION_READERS"),
            ("seesCashflow", "CASHFLOW_READERS"),
        ):
            assert f"const {flag} = hasAnyRole(roles, {role_set});" in centre

    def test_unit_360_asks_for_finance_only_on_behalf_of_finance_readers(self) -> None:
        """Legal and Collections open a unit file with no price, margin or cost requested."""
        unit = read(UNIT_360)
        assert "const seesEconomics = hasAnyRole(roles, ECONOMICS_READERS);" in unit
        assert "const seesListPrice = hasAnyRole(roles, LIST_PRICE_READERS);" in unit
        assert "const seesCollections = hasAnyRole(roles, COLLECTION_READERS);" in unit
        assert re.search(
            r"if \(!seesEconomics\) \{\s*setEconomics\(\{ status: \"off\" \}\);\s*return;", unit
        )
        assert re.search(
            r"if \(!seesListPrice\) \{\s*setPricingAnswer\(\{ status: \"off\" \}\);\s*return;", unit
        )
        assert "if (seesCollections && sale)" in unit

    def test_the_unit_headline_price_exists_only_when_pricing_was_answered(self) -> None:
        """The large price in the record header is drawn from the pricing answer alone.

        `unitPricing` is null unless the pricing request was made and answered,
        and the request is made only for LIST_PRICE_READERS — so a role refused
        the list price has no headline, not a hidden one.
        """
        unit = read(UNIT_360)
        assert (
            'const unitPricing = pricingAnswer.status === "ready" ? pricingAnswer.data : null;'
            in unit
        )
        headline = unit.split("const headline: DrawerHeadline | undefined = ")[1].split(";")[0]
        assert headline.startswith("unitPricing")
        assert "reference_price_ex_tax" in headline

    def test_navigation_groups_are_the_developers_departments_in_order(self) -> None:
        navigation = read(NAVIGATION)
        block = navigation.split("export const PROJECT_NAVIGATION")[1].split(
            "export type SettingsSection"
        )[0]
        # Groups sit at one indent, their items at two; the indent is the structure.
        groups = re.findall(r'\n    key: "([a-z]+)",\n    label: ', block)
        assert groups == ["home", "development", "commercial", "delivery", "finance", "governance"]
        items = re.findall(r'\n        key: "([a-z]+)",', block)
        assert items == [
            "overview",
            "land",
            "permits",
            "inventory",
            "pricing",
            "sales",
            "payments",
            "collections",
            "construction",
            "economics",
            "cashflow",
            "documents",
            "access",
        ]

    def test_every_gated_navigation_item_names_its_reader_set(self) -> None:
        navigation = read(NAVIGATION)
        for key, role_set in (
            ("pricing", "INTERNAL_PRICE_READERS"),
            ("sales", "SALES_READERS"),
            ("payments", "PLAN_READERS"),
            ("collections", "COLLECTION_READERS"),
            ("construction", "CONSTRUCTION_READERS"),
            ("economics", "ECONOMICS_READERS"),
            ("cashflow", "CASHFLOW_READERS"),
        ):
            entry = navigation.split(f'key: "{key}",')[1].split("},")[0]
            assert f"hasAnyRole(roles, {role_set})" in entry, f"{key} is not gated on {role_set}"
        access = navigation.split('key: "access",')[1].split("},")[0]
        assert "roles.has(ROLE_SYSTEM_ADMIN)" in access


# --------------------------------------------------------------------------- #
# The shell, the record file and the dialogs kept their semantics
# --------------------------------------------------------------------------- #


class TestTheShellKeepsItsStructure:
    def test_the_rail_collapses_and_becomes_a_drawer_by_width(self) -> None:
        css = stylesheet_without_comments()
        narrow = css.split("@media (width < 64rem)")[1].split("@media")[0]
        assert re.search(r"\.sidebar\s*\{\s*display:\s*none;", narrow)
        assert re.search(r"\.menu-button\s*\{\s*display:\s*inline-grid;", narrow)
        assert re.search(r"\.drawer,\s*\.drawer-narrow\s*\{\s*width:\s*100%;", narrow)
        collapsed = css.split("@media (width < 75rem)")[1].split("@media")[0]
        assert "--sidebar-collapsed-width" in collapsed

    def test_the_page_never_scrolls_sideways_because_registers_scroll_inside(self) -> None:
        css = stylesheet_without_comments()
        assert re.search(r"\.table-scroll\s*\{\s*overflow-x:\s*auto;", css)
        assert "min-width: 0" in css.split(".app-main {")[1].split("}")[0]

    def test_the_mobile_navigation_is_a_modal_dialog_on_the_shared_overlay(self) -> None:
        sidebar = read(SIDEBAR)
        assert 'role="dialog"' in sidebar
        assert 'aria-modal="true"' in sidebar
        assert "useOverlay<HTMLElement>(onClose" in sidebar
        assert 'aria-label="Navigation"' in sidebar

    def test_the_shell_reflects_both_the_preference_and_the_viewport(self) -> None:
        shell = read(APP_SHELL)
        assert "data-rail={rail}" in shell
        assert '"app app-narrow"' in shell
        assert "window.localStorage.getItem(RAIL_PREFERENCE)" in shell
        assert "matchMedia(NARROW_RAIL)" in shell

    def test_the_project_switcher_keeps_the_section_and_is_first_class(self) -> None:
        switcher = read(SWITCHER)
        assert "projectHref(row.id, section)" in switcher, (
            "switching projects must keep the open section"
        )
        assert 'aria-haspopup="dialog"' in switcher
        assert "useOverlay<HTMLDivElement>(onClose" in switcher
        sidebar = read(SIDEBAR)
        assert "<ProjectSwitcher" in sidebar
        assert "insideProject && projectId ? (" in sidebar

    def test_the_context_bar_carries_where_you_are(self) -> None:
        bar = read(SHELL / "ContextBar.tsx")
        assert 'aria-label="Breadcrumb"' in bar
        assert 'aria-current={last ? "page" : undefined}' in bar
        assert 'aria-controls="mobile-navigation"' in bar

    def test_the_current_navigation_item_is_marked_for_assistive_technology(self) -> None:
        sidebar = read(SIDEBAR)
        assert 'aria-current={current ? "page" : undefined}' in sidebar


class TestRecordsAndDialogsKeepTheirSemantics:
    def test_the_drawer_is_a_modal_dialog_named_after_its_record(self) -> None:
        drawer = read(UI / "Drawer.tsx")
        assert 'role="dialog"' in drawer
        assert 'aria-modal="true"' in drawer
        assert "aria-label={title}" in drawer
        assert 'useOverlay<HTMLDivElement>(onClose, "container")' in drawer
        assert 'document.body.style.overflow = "hidden"' in drawer

    def test_the_drawer_header_carries_identity_headline_actions_facts_and_sections(self) -> None:
        drawer = read(UI / "Drawer.tsx")
        for slot in (
            "drawer-eyebrow",
            "drawer-title",
            "drawer-subtitle",
            "drawer-meta",
            "drawer-headline",
            "drawer-head-actions",
            "drawer-facts",
            "drawer-sections",
        ):
            assert f'className="{slot}' in drawer or f"`{slot}" in drawer, (
                f"the record header lost its {slot}"
            )

    def test_confirmations_are_alert_dialogs_and_prompts_are_labelled(self) -> None:
        confirm = read(UI / "ConfirmDialog.tsx")
        assert 'role="alertdialog"' in confirm
        assert 'aria-modal="true"' in confirm
        prompt = read(UI / "PromptDialog.tsx")
        assert 'role="dialog"' in prompt
        assert '<span className="field-label">{label}</span>' in prompt
        form = read(UI / "FormDialog.tsx")
        assert 'role="dialog"' in form

    def test_no_screen_uses_a_browser_prompt(self) -> None:
        for path in frontend_sources():
            source = read(path)
            for line in source.splitlines():
                stripped = line.strip()
                if stripped.startswith(("*", "//")):
                    continue
                for forbidden in (
                    "window.prompt(",
                    "window.confirm(",
                    "window.alert(",
                    " confirm(",
                    " alert(",
                    " prompt(",
                ):
                    assert forbidden not in line, f"{path.name} uses a browser dialog: {stripped}"

    def test_tabs_are_a_real_tablist(self) -> None:
        tabs = read(UI / "Tabs.tsx")
        assert 'role="tablist"' in tabs
        assert 'role="tab"' in tabs
        assert 'role="tabpanel"' in tabs
        assert "ArrowRight" in tabs and "ArrowLeft" in tabs and "Home" in tabs and "End" in tabs

    def test_every_table_has_a_caption(self) -> None:
        table = read(UI / "Data.tsx")
        assert '<caption className="visually-hidden">{label}</caption>' in table

    def test_the_page_header_composes_title_status_actions_and_facts(self) -> None:
        headers = read(UI / "Headers.tsx")
        for prop in ("eyebrow", "title", "subtitle", "status", "actions", "meta", "compact"):
            assert f"{prop}?:" in headers or f"{prop}:" in headers
        assert '<h1 className="page-title">' in headers

    def test_empty_states_say_what_is_missing_and_what_to_do(self) -> None:
        feedback = read(UI / "Feedback.tsx")
        assert "hint?: string;" in feedback
        assert "actions?: ReactNode;" in feedback
        assert "icon?: IconName;" in feedback
        for path in frontend_sources():
            for line in read(path).splitlines():
                assert not re.search(r'title="0 records?"', line), (
                    f"{path.name} draws a count as an empty state"
                )

    def test_loading_states_have_the_shape_of_what_is_coming(self) -> None:
        feedback = read(UI / "Feedback.tsx")
        for shape in ("header", "metrics", "rows", "record", "page"):
            assert f'shape === "{shape}"' in feedback

    def test_the_icon_set_is_hand_drawn_and_nothing_else_is_installed(self) -> None:
        package = (ROOT / "frontend" / "package.json").read_text(encoding="utf-8")
        for forbidden in (
            "tailwind",
            "@mui",
            "@chakra",
            "antd",
            "@radix",
            "shadcn",
            "styled-components",
            "@emotion",
            "recharts",
            "chart.js",
            "d3",
            "redux",
            "zustand",
            "mobx",
            "lucide",
            "@heroicons",
            "react-icons",
            "framer-motion",
        ):
            assert forbidden not in package, f"frontend/package.json gained {forbidden}"
        icon = read(UI / "Icon.tsx")
        assert 'aria-hidden="true"' in icon
