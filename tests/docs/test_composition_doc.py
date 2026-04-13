"""Tests mirroring code examples from docs/composition-patterns.md.

Validates that the composition patterns shown in the doc produce
correct tree structures and handle events as described.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

import plushie
from plushie import ui
from plushie.events import Click
from plushie.tree import find, normalize
from plushie.types import Border, Shadow, StyleMap

# =========================================================================
# Tab bar (pattern 1)
# =========================================================================


@dataclass(frozen=True, slots=True)
class TabModel:
    active_tab: str = "overview"


TABS = ["overview", "details", "settings"]


class TabApp(plushie.App[TabModel]):
    def init(self) -> TabModel:
        return TabModel()

    def update(self, model: TabModel, event: object) -> TabModel:
        match event:
            case Click(id=tab_id) if tab_id.startswith("tab:"):
                return replace(model, active_tab=tab_id.removeprefix("tab:"))
            case _:
                return model

    def view(self, model: TabModel) -> dict[str, Any]:
        return ui.window(
            "main",
            ui.column(
                ui.row(
                    *(
                        ui.button(
                            f"tab:{tab}",
                            tab.capitalize(),
                            style=_tab_style(model.active_tab == tab),
                            padding={
                                "top": 10,
                                "bottom": 10,
                                "left": 20,
                                "right": 20,
                            },
                        )
                        for tab in TABS
                    ),
                    spacing=0,
                ),
                ui.rule(),
                ui.container(
                    "content",
                    ui.text(f"Content for {model.active_tab}"),
                    padding=20,
                    width="fill",
                    height="fill",
                ),
                width="fill",
            ),
            title="Tab Demo",
        )


def _tab_style(active: bool) -> StyleMap:
    if active:
        return (
            StyleMap()
            .with_background("#ffffff")
            .with_text_color("#1a1a1a")
            .with_border(Border(color="#0066ff", width=2, radius=0))
        )
    return (
        StyleMap()
        .with_background("#f0f0f0")
        .with_text_color("#666666")
        .with_hovered({"background": "#e0e0e0"})
    )


class TestTabBar:
    """Doc section: Tab bar: view structure and tab switching."""

    def test_view_contains_tab_buttons(self) -> None:
        app = TabApp()
        tree = normalize(app.view(app.init()))
        for tab in TABS:
            assert find(tree, f"tab:{tab}") is not None

    def test_clicking_tab_changes_active(self) -> None:
        app = TabApp()
        model = app.init()
        assert model.active_tab == "overview"

        model = app.update(model, Click(id="tab:settings"))
        assert model.active_tab == "settings"

    def test_unrelated_click_ignored(self) -> None:
        app = TabApp()
        model = app.init()
        model = app.update(model, Click(id="unrelated"))
        assert model.active_tab == "overview"

    def test_active_tab_style_has_border(self) -> None:
        style = _tab_style(active=True)
        assert style.border is not None
        assert style.border.color == "#0066ff"

    def test_inactive_tab_style_has_hovered(self) -> None:
        style = _tab_style(active=False)
        assert style.hovered is not None


# =========================================================================
# Sidebar navigation (pattern 2)
# =========================================================================


@dataclass(frozen=True, slots=True)
class SidebarModel:
    page: str = "inbox"


NAV_ITEMS = [
    ("inbox", "Inbox"),
    ("sent", "Sent"),
    ("drafts", "Drafts"),
    ("trash", "Trash"),
]


class SidebarApp(plushie.App[SidebarModel]):
    def init(self) -> SidebarModel:
        return SidebarModel()

    def update(self, model: SidebarModel, event: object) -> SidebarModel:
        match event:
            case Click(id=nav_id) if nav_id.startswith("nav:"):
                return replace(model, page=nav_id.removeprefix("nav:"))
            case _:
                return model

    def view(self, model: SidebarModel) -> dict[str, Any]:
        return ui.window(
            "main",
            ui.row(
                ui.container(
                    "sidebar",
                    ui.column(
                        *(
                            ui.button(f"nav:{id}", label, width="fill")
                            for id, label in NAV_ITEMS
                        ),
                        spacing=4,
                        width="fill",
                    ),
                    width=200,
                    height="fill",
                    background="#1e1e2e",
                    padding=8,
                ),
                ui.container(
                    "main_content",
                    ui.text(
                        "page_title",
                        f"{model.page.capitalize()} page",
                        size=20,
                    ),
                    width="fill",
                    height="fill",
                    padding=24,
                ),
                width="fill",
                height="fill",
            ),
            title="Sidebar Demo",
        )


class TestSidebar:
    """Doc section: Sidebar navigation."""

    def test_view_contains_nav_buttons(self) -> None:
        app = SidebarApp()
        tree = normalize(app.view(app.init()))
        for id, _label in NAV_ITEMS:
            assert find(tree, f"nav:{id}") is not None

    def test_clicking_nav_changes_page(self) -> None:
        app = SidebarApp()
        model = app.init()
        model = app.update(model, Click(id="nav:sent"))
        assert model.page == "sent"


# =========================================================================
# Modal dialog (pattern 4)
# =========================================================================


@dataclass(frozen=True, slots=True)
class ModalModel:
    show_modal: bool = False
    confirmed: bool = False


class ModalApp(plushie.App[ModalModel]):
    def init(self) -> ModalModel:
        return ModalModel()

    def update(self, model: ModalModel, event: object) -> ModalModel:
        match event:
            case Click(id="open_modal"):
                return replace(model, show_modal=True)
            case Click(id="confirm"):
                return replace(model, show_modal=False, confirmed=True)
            case Click(id="cancel"):
                return replace(model, show_modal=False)
            case _:
                return model

    def view(self, model: ModalModel) -> dict[str, Any]:
        layers: list[dict[str, Any]] = [
            ui.container(
                "main",
                ui.column(
                    ui.text("main_content", "Main application content", size=20),
                    *(
                        [
                            ui.text(
                                "confirmed_msg",
                                "Action confirmed.",
                                color="#22aa44",
                            )
                        ]
                        if model.confirmed
                        else []
                    ),
                    ui.button("open_modal", "Open Dialog", style="primary"),
                    spacing=12,
                    align_x="center",
                ),
                width="fill",
                height="fill",
                padding=24,
                center=True,
            ),
        ]

        if model.show_modal:
            layers.append(
                ui.container(
                    "overlay",
                    ui.container(
                        "dialog",
                        ui.column(
                            ui.text("dialog_title", "Confirm action", size=18),
                            ui.text(
                                "dialog_body",
                                "Are you sure?",
                                wrapping="word",
                            ),
                            ui.row(
                                ui.button("cancel", "Cancel", style="secondary"),
                                ui.button("confirm", "Confirm", style="primary"),
                                spacing=8,
                                align_x="end",
                            ),
                            spacing=16,
                        ),
                        max_width=400,
                        padding=24,
                        background="#ffffff",
                        border=Border(color="#dddddd", width=1, radius=8),
                        shadow=Shadow(color="#00000040", offset=(0, 4), blur_radius=16),
                    ),
                    width="fill",
                    height="fill",
                    background="#00000088",
                    center=True,
                )
            )

        return ui.window(
            "main",
            ui.stack(*layers, width="fill", height="fill"),
            title="Modal Demo",
        )


class TestModal:
    """Doc section: Modal dialog."""

    def test_open_modal_shows_overlay(self) -> None:
        app = ModalApp()
        model = replace(app.init(), show_modal=True)
        tree = normalize(app.view(model))
        assert find(tree, "overlay") is not None
        assert find(tree, "dialog") is not None

    def test_closed_modal_hides_overlay(self) -> None:
        app = ModalApp()
        tree = normalize(app.view(app.init()))
        assert find(tree, "overlay") is None

    def test_confirm_closes_and_sets_flag(self) -> None:
        app = ModalApp()
        model = replace(app.init(), show_modal=True)
        model = app.update(model, Click(id="confirm"))
        assert model.show_modal is False
        assert model.confirmed is True

    def test_cancel_closes_without_confirm(self) -> None:
        app = ModalApp()
        model = replace(app.init(), show_modal=True)
        model = app.update(model, Click(id="cancel"))
        assert model.show_modal is False
        assert model.confirmed is False


# =========================================================================
# Card (pattern 5)
# =========================================================================


def card(id: str, title: str, body: list[dict[str, Any]]) -> dict[str, Any]:
    """Reusable card helper. Returns a container node."""
    return ui.container(
        id,
        ui.column(
            ui.text("card_title", title, size=16, color="#1a1a1a"),
            ui.rule(),
            *body,
            spacing=8,
        ),
        width="fill",
        padding=16,
        background="#ffffff",
        border=Border(color="#e0e0e0", width=1, radius=8),
        shadow=Shadow(color="#00000020", offset=(0, 2), blur_radius=8),
    )


class TestCard:
    """Doc section: Card helper."""

    def test_card_has_correct_structure(self) -> None:
        node = card(
            "info",
            "System status",
            [ui.text("status_msg", "All good", color="#22aa44")],
        )
        assert node["id"] == "info"
        assert node["type"] == "container"
        assert node["props"].get("background") == "#ffffff"

    def test_card_contains_title_and_body(self) -> None:
        node = card("info", "Title", [ui.text("body", "Body text")])
        tree = normalize(node)
        assert find(tree, "card_title") is not None
        assert find(tree, "body") is not None

    def test_card_border_and_shadow(self) -> None:
        node = card("info", "Title", [])
        border = node["props"].get("border")
        shadow = node["props"].get("shadow")
        assert isinstance(border, Border)
        assert border.radius == 8
        assert isinstance(shadow, Shadow)
        assert shadow.blur_radius == 8


# =========================================================================
# StyleMap usage patterns
# =========================================================================


class TestStyleMapUsage:
    """Validates StyleMap builder chain patterns used across all composition docs."""

    def test_with_background_and_text_color(self) -> None:
        style = StyleMap().with_background("#ffffff").with_text_color("#1a1a1a")
        assert style.background == "#ffffff"
        assert style.text_color == "#1a1a1a"

    def test_with_border(self) -> None:
        style = StyleMap().with_border(Border(color="#0066ff", width=2, radius=0))
        assert style.border is not None
        assert style.border.color == "#0066ff"

    def test_with_hovered(self) -> None:
        style = StyleMap().with_hovered({"background": "#e0e0e0"})
        assert style.hovered == {"background": "#e0e0e0"}

    def test_with_pressed(self) -> None:
        style = StyleMap().with_pressed({"background": "#d0d0d0"})
        assert style.pressed == {"background": "#d0d0d0"}
