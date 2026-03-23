"""Tests mirroring code examples from docs/accessibility.md.

Validates that a11y prop construction, heading levels, landmark roles,
cross-widget relationships, and hidden/decorative patterns produce
correct node structures.
"""

from __future__ import annotations

from plushie import ui
from plushie.tree import find, normalize

# ---------------------------------------------------------------------------
# Using the a11y prop
# ---------------------------------------------------------------------------


class TestA11yPropConstruction:
    """Doc section: Using the a11y prop."""

    def test_heading_with_level(self) -> None:
        node = ui.text(
            "title", "Welcome to MyApp", a11y={"role": "heading", "level": 1}
        )
        assert node["props"]["a11y"] == {"role": "heading", "level": 1}

    def test_heading_level_2(self) -> None:
        node = ui.text(
            "settings_heading", "Settings", a11y={"role": "heading", "level": 2}
        )
        assert node["props"]["a11y"]["level"] == 2

    def test_icon_button_label(self) -> None:
        node = ui.button("close", "X", a11y={"label": "Close dialog"})
        assert node["props"]["a11y"]["label"] == "Close dialog"

    def test_landmark_region(self) -> None:
        node = ui.container(
            "search_results",
            a11y={"role": "region", "label": "Search results"},
            children=[],
        )
        a11y = node["props"]["a11y"]
        assert a11y["role"] == "region"
        assert a11y["label"] == "Search results"

    def test_live_region_polite(self) -> None:
        node = ui.text("save_status", "5 items saved", a11y={"live": "polite"})
        assert node["props"]["a11y"]["live"] == "polite"

    def test_hidden_from_at(self) -> None:
        node = ui.image("divider", "/images/decorative-line.png", a11y={"hidden": True})
        assert node["props"]["a11y"]["hidden"] is True

    def test_expanded_state(self) -> None:
        node = ui.container(
            "details",
            a11y={"expanded": True, "role": "group", "label": "Advanced options"},
            children=[],
        )
        a11y = node["props"]["a11y"]
        assert a11y["expanded"] is True
        assert a11y["role"] == "group"

    def test_required_form_field(self) -> None:
        node = ui.text_input(
            "email",
            "user@example.com",
            a11y={"required": True, "label": "Email address"},
        )
        a11y = node["props"]["a11y"]
        assert a11y["required"] is True
        assert a11y["label"] == "Email address"


# ---------------------------------------------------------------------------
# Headings for structure
# ---------------------------------------------------------------------------


class TestHeadingStructure:
    """Doc section: Use headings to create structure."""

    def test_heading_hierarchy_in_view(self) -> None:
        tree = normalize(
            ui.window(
                "main",
                ui.column(
                    ui.text(
                        "page_title",
                        "Dashboard",
                        a11y={"role": "heading", "level": 1},
                    ),
                    ui.text(
                        "h_recent",
                        "Recent activity",
                        a11y={"role": "heading", "level": 2},
                    ),
                    ui.text(
                        "h_actions",
                        "Quick actions",
                        a11y={"role": "heading", "level": 2},
                    ),
                ),
                title="MyApp",
            )
        )

        h1 = find(tree, "page_title")
        assert h1 is not None
        assert h1["props"]["a11y"]["level"] == 1

        h2a = find(tree, "h_recent")
        assert h2a is not None
        assert h2a["props"]["a11y"]["level"] == 2


# ---------------------------------------------------------------------------
# Landmarks for page regions
# ---------------------------------------------------------------------------


class TestLandmarkRoles:
    """Doc section: Use landmarks for page regions."""

    def test_navigation_landmark(self) -> None:
        node = ui.container(
            "nav",
            a11y={"role": "navigation", "label": "Main navigation"},
            children=[
                ui.row(
                    ui.button("home", "Home"),
                    ui.button("settings", "Settings"),
                )
            ],
        )
        assert node["props"]["a11y"]["role"] == "navigation"

    def test_region_landmark(self) -> None:
        node = ui.container(
            "main_content",
            a11y={"role": "region", "label": "Main content"},
            children=[],
        )
        assert node["props"]["a11y"]["role"] == "region"

    def test_search_landmark(self) -> None:
        node = ui.container(
            "search_area",
            a11y={"role": "search", "label": "Search"},
            children=[
                ui.text_input("query", "", placeholder="Search..."),
                ui.button("go", "Search"),
            ],
        )
        assert node["props"]["a11y"]["role"] == "search"


# ---------------------------------------------------------------------------
# Cross-widget relationships (labelled_by, described_by, error_message)
# ---------------------------------------------------------------------------


class TestCrossWidgetRelationships:
    """Doc section: Cross-widget relationships."""

    def test_labelled_by(self) -> None:
        node = ui.text_input(
            "email",
            "",
            a11y={
                "labelled_by": "email-label",
                "described_by": "email-help",
                "error_message": "email-error",
            },
        )
        a11y = node["props"]["a11y"]
        assert a11y["labelled_by"] == "email-label"
        assert a11y["described_by"] == "email-help"
        assert a11y["error_message"] == "email-error"

    def test_normalize_resolves_a11y_refs_in_scope(self) -> None:
        """a11y ID refs should be resolved relative to scope during normalize."""
        tree = normalize(
            ui.container(
                "form",
                ui.text("email-label", "Email"),
                ui.text("email-help", "We'll send a confirmation"),
                ui.text_input(
                    "email",
                    "",
                    a11y={
                        "labelled_by": "email-label",
                        "described_by": "email-help",
                    },
                ),
            )
        )
        email_node = find(tree, "email")
        assert email_node is not None
        # After normalization, refs should be scoped
        a11y = email_node["props"]["a11y"]
        assert "labelled_by" in a11y
        assert "described_by" in a11y


# ---------------------------------------------------------------------------
# Hidden / decorative patterns
# ---------------------------------------------------------------------------


class TestHiddenDecorative:
    """Doc section: Hiding decorative content."""

    def test_rule_hidden(self) -> None:
        node = ui.rule(a11y={"hidden": True})
        assert node["props"]["a11y"]["hidden"] is True

    def test_image_hidden(self) -> None:
        node = ui.image("hero", "/images/banner.png", a11y={"hidden": True})
        assert node["props"]["a11y"]["hidden"] is True

    def test_image_decorative_prop(self) -> None:
        node = ui.image("divider", "/images/decorative-line.png", decorative=True)
        assert node["props"]["decorative"] is True

    def test_svg_decorative_prop(self) -> None:
        node = ui.svg("flourish", "/icons/flourish.svg", decorative=True)
        assert node["props"]["decorative"] is True

    def test_image_alt_text(self) -> None:
        node = ui.image("status_icon", "/icon.png", alt="Status: online")
        assert node["props"]["alt"] == "Status: online"


# ---------------------------------------------------------------------------
# Widget-specific a11y props (alt, label, description, decorative)
# ---------------------------------------------------------------------------


class TestWidgetSpecificA11yProps:
    """Doc section: Widget-specific accessibility props."""

    def test_image_alt(self) -> None:
        node = ui.image("logo", "/images/logo.png", alt="Company logo")
        assert node["props"]["alt"] == "Company logo"

    def test_svg_alt(self) -> None:
        node = ui.svg("icon", "/icons/search.svg", alt="Search")
        assert node["props"]["alt"] == "Search"

    def test_slider_label(self) -> None:
        node = ui.slider("volume", (0, 100), 50, label="Volume")
        assert node["props"]["label"] == "Volume"

    def test_progress_bar_label(self) -> None:
        node = ui.progress_bar("upload", (0, 100), 42, label="Upload progress")
        assert node["props"]["label"] == "Upload progress"

    def test_image_description(self) -> None:
        node = ui.image(
            "photo",
            "/photo.jpg",
            alt="Team photo",
            description="The engineering team at the 2025 offsite",
        )
        assert node["props"]["description"] == (
            "The engineering team at the 2025 offsite"
        )


# ---------------------------------------------------------------------------
# Custom widgets with state (canvas a11y)
# ---------------------------------------------------------------------------


class TestCustomWidgetState:
    """Doc section: Custom widgets with state."""

    def test_switch_a11y(self) -> None:
        node = ui.canvas(
            "dark-mode-switch",
            layers={},
            a11y={
                "role": "switch",
                "label": "Dark mode",
                "toggled": True,
            },
        )
        a11y = node["props"]["a11y"]
        assert a11y["role"] == "switch"
        assert a11y["toggled"] is True

    def test_meter_a11y(self) -> None:
        node = ui.canvas(
            "cpu-gauge",
            layers={},
            a11y={
                "role": "meter",
                "label": "CPU usage",
                "value": "75%",
                "orientation": "horizontal",
            },
        )
        a11y = node["props"]["a11y"]
        assert a11y["role"] == "meter"
        assert a11y["value"] == "75%"


# ---------------------------------------------------------------------------
# Set position and popup hints
# ---------------------------------------------------------------------------


class TestPositionAndPopup:
    """Doc section: Set position and popup hints."""

    def test_tab_position_in_set(self) -> None:
        tabs = [("t1", "Tab 1"), ("t2", "Tab 2"), ("t3", "Tab 3")]
        active = "t1"
        nodes = [
            ui.button(
                f"tab_{id}",
                label,
                a11y={
                    "role": "tab",
                    "selected": id == active,
                    "position_in_set": idx,
                    "size_of_set": len(tabs),
                },
            )
            for idx, (id, label) in enumerate(tabs, 1)
        ]
        assert nodes[0]["props"]["a11y"]["selected"] is True
        assert nodes[0]["props"]["a11y"]["position_in_set"] == 1
        assert nodes[2]["props"]["a11y"]["position_in_set"] == 3
        assert nodes[2]["props"]["a11y"]["size_of_set"] == 3

    def test_has_popup_menu(self) -> None:
        node = ui.button(
            "menu_btn",
            "Options",
            a11y={"has_popup": "menu", "expanded": False},
        )
        assert node["props"]["a11y"]["has_popup"] == "menu"

    def test_disabled_override(self) -> None:
        node = ui.button("submit", "Submit", a11y={"disabled": True})
        assert node["props"]["a11y"]["disabled"] is True


# ---------------------------------------------------------------------------
# Expanded / collapsed state
# ---------------------------------------------------------------------------


class TestExpandedCollapsed:
    """Doc section: Expanded/collapsed state."""

    def test_expanded_button(self) -> None:
        node = ui.button(
            "toggle_details",
            "Hide details",
            a11y={"expanded": True},
        )
        assert node["props"]["a11y"]["expanded"] is True

    def test_collapsed_button(self) -> None:
        node = ui.button(
            "toggle_details",
            "Show details",
            a11y={"expanded": False},
        )
        assert node["props"]["a11y"]["expanded"] is False
