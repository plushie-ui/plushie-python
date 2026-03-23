"""Rate Plushie -- app rating page with custom canvas widgets.

Demonstrates custom canvas widgets (StarRating, ThemeToggle) composed
with styled containers. The "Dark humor" toggle animates a face emoji
and flips the entire page theme.

Features:

- Custom canvas widgets as reusable modules (star_rating, theme_toggle)
- Interactive canvas shapes with click/hover/focus events
- Timer-based animation via subscriptions (16ms frame rate)
- Theme interpolation between light and dark palettes
- Review form with text input, text editor, and submit
- Container styling with border, padding, background

Run::

    python -m plushie run examples.rate_plushie:RatePlushie
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

import plushie
from examples.widgets.star_rating import render as star_render
from examples.widgets.theme_toggle import render as toggle_render
from plushie import ui
from plushie.events import (
    CanvasElementClick,
    CanvasElementEnter,
    CanvasElementLeave,
    Click,
    Input,
    Submit,
    TimerTick,
)
from plushie.subscriptions import Subscription
from plushie.types import Theme


@dataclass(frozen=True, slots=True)
class Review:
    """A single user review."""

    stars: int
    user: str
    time: str
    text: str


INITIAL_REVIEWS: tuple[Review, ...] = (
    Review(
        5,
        "elixir_fan_42",
        "2d ago",
        "Finally, native GUIs that don't make me want to cry.",
    ),
    Review(5, "beam_me_up", "3d ago", "The Elm architecture feels right at home here."),
    Review(
        4,
        "rustacean",
        "5d ago",
        "Solid Iced wrapper. Docked a star because I had to write Elixir.",
    ),
    Review(
        3,
        "web_refugee",
        "1w ago",
        "Where is my CSS grid? Also it works perfectly. Three stars.",
    ),
    Review(5, "otp_enjoyer", "1w ago", "Let it crash, but make it beautiful."),
    Review(
        1,
        "electron_mass",
        "2w ago",
        "No browser engine. No JavaScript runtime. What am I even paying for?",
    ),
)


@dataclass(frozen=True, slots=True)
class Model:
    """Rate Plushie model."""

    rating: int = 0
    hover_star: int | None = None
    toggle_progress: float = 0.0
    toggle_target: float = 0.0
    reviews: tuple[Review, ...] = INITIAL_REVIEWS
    review_name: str = ""
    review_comment: str = ""


def _submit_review(model: Model) -> Model:
    name = model.review_name.strip()
    comment = model.review_comment.strip()
    if not name or not comment or model.rating <= 0:
        return model
    review = Review(stars=model.rating, user=name, time="just now", text=comment)
    return replace(
        model,
        reviews=(review, *model.reviews),
        review_name="",
        review_comment="",
        rating=0,
    )


def _approach(current: float, target: float, step: float) -> float:
    if current < target:
        return min(current + step, target)
    if current > target:
        return max(current - step, target)
    return current


def _smoothstep(t: float) -> float:
    if t <= 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    return t * t * (3 - 2 * t)


def _fade(c1: tuple[int, int, int], c2: tuple[int, int, int], t: float) -> str:
    r = round(c1[0] + (c2[0] - c1[0]) * t)
    g = round(c1[1] + (c2[1] - c1[1]) * t)
    b = round(c1[2] + (c2[2] - c1[2]) * t)
    return f"#{r:02x}{g:02x}{b:02x}"


@dataclass(frozen=True, slots=True)
class _Theme:
    """Interpolated color theme."""

    page_bg: str
    card_bg: str
    card_border: str
    text: str
    text_secondary: str
    text_muted: str


def _theme(p: float) -> _Theme:
    return _Theme(
        page_bg=_fade((248, 248, 250), (19, 19, 31), p),
        card_bg=_fade((255, 255, 255), (28, 28, 50), p),
        card_border=_fade((224, 224, 224), (42, 42, 74), p),
        text=_fade((26, 26, 26), (240, 240, 245), p),
        text_secondary=_fade((102, 102, 102), (153, 153, 187), p),
        text_muted=_fade((170, 170, 170), (85, 85, 119), p),
    )


class RatePlushie(plushie.App[Model]):
    """App rating page with star rating and theme toggle."""

    def init(self) -> Model:
        return Model()

    def update(self, model: Model, event: object) -> Model:
        match event:
            # Star rating interactions
            case CanvasElementClick(id="stars", element_id=sid) if sid.startswith(
                "star-"
            ):
                n = int(sid.removeprefix("star-"))
                return replace(model, rating=n + 1)

            case CanvasElementEnter(id="stars", element_id=sid) if sid.startswith(
                "star-"
            ):
                n = int(sid.removeprefix("star-"))
                return replace(model, hover_star=n + 1)

            case CanvasElementLeave(id="stars"):
                return replace(model, hover_star=None)

            # Theme toggle
            case CanvasElementClick(id="theme-toggle"):
                target = 1.0 if model.toggle_target == 0.0 else 0.0
                return replace(model, toggle_target=target)

            # Review form
            case Input(id="review-name", value=v):
                return replace(model, review_name=v)
            case Input(id="review-comment", value=v):
                return replace(model, review_comment=v)
            case Click(id="submit-review"):
                return _submit_review(model)
            case Submit(id="review-name"):
                return _submit_review(model)

            # Animation
            case TimerTick(tag="animate"):
                return replace(
                    model,
                    toggle_progress=_approach(
                        model.toggle_progress, model.toggle_target, 0.06
                    ),
                )

            case _:
                return model

    def subscribe(self, model: Model) -> list[Subscription]:
        if model.toggle_progress != model.toggle_target:
            return [Subscription.every(16, "animate")]
        return []

    def view(self, model: Model) -> dict[str, Any]:
        p = _smoothstep(model.toggle_progress)
        t = _theme(p)

        page_theme = Theme.custom(
            "rate-plushie",
            background=t.page_bg,
            text=t.text,
            primary=_fade((59, 130, 246), (139, 92, 246), p),
        )

        return ui.window(
            "main",
            ui.themer(
                "page-theme",
                ui.container(
                    "page",
                    ui.column(
                        ui.text(
                            "heading",
                            "Rate Plushie",
                            size=28,
                            color=t.text,
                            a11y={"role": "heading", "level": 1},
                        ),
                        _rating_card(model, p, t),
                        ui.text(
                            "reviews-heading",
                            "Reviews",
                            size=20,
                            color=t.text,
                            a11y={"role": "heading", "level": 2},
                        ),
                        _reviews_list(model.reviews, p, t),
                        spacing=24,
                        width="fill",
                    ),
                    padding=(32, 24, 32, 24),
                    background=t.page_bg,
                    width="fill",
                    height="fill",
                ),
                theme=page_theme,
            ),
            title="Rate Plushie",
        )


def _rating_card(model: Model, p: float, t: _Theme) -> dict[str, Any]:
    return ui.container(
        "rating-card",
        ui.column(
            ui.text(
                "prompt",
                "How would you rate Plushie?",
                size=14,
                color=t.text_secondary,
            ),
            star_render(
                "stars",
                model.rating,
                hover=model.hover_star,
                theme_progress=p,
            ),
            ui.rule(),
            _review_form(model),
            _theme_row(model, t),
            spacing=20,
        ),
        padding=24,
        width="fill",
        border={"width": 1, "color": t.card_border, "rounded": 12},
        background=t.card_bg,
    )


def _review_form(model: Model) -> dict[str, Any]:
    return ui.column(
        ui.text_input(
            "review-name",
            model.review_name,
            placeholder="Your name",
            a11y={"label": "Your name"},
        ),
        ui.text_editor(
            "review-comment",
            model.review_comment,
            placeholder="Write your review...",
            height=80,
            a11y={"label": "Review text"},
        ),
        ui.button("submit-review", "Submit Review"),
        id="review-form",
        spacing=12,
        width="fill",
    )


def _theme_row(model: Model, t: _Theme) -> dict[str, Any]:
    return ui.row(
        ui.space(width="fill"),
        ui.text("toggle-label", "Dark humor", color=t.text_secondary),
        toggle_render("theme-toggle", model.toggle_progress),
        id="theme-row",
        align_y="center",
    )


def _reviews_list(reviews: tuple[Review, ...], p: float, t: _Theme) -> dict[str, Any]:
    children: list[dict[str, Any]] = []
    for i, review in enumerate(reviews):
        if i > 0:
            children.append(ui.rule(id=f"sep-{i}"))
        children.append(_review_card(review, i, p, t))

    return ui.column(*children, id="reviews", spacing=0, width="fill")


def _review_card(review: Review, i: int, p: float, t: _Theme) -> dict[str, Any]:
    return ui.column(
        ui.row(
            star_render(
                f"rstars-{i}",
                review.stars,
                readonly=True,
                scale=0.4,
                theme_progress=p,
            ),
            ui.text(f"rname-{i}", review.user, size=12, color=t.text_secondary),
            ui.space(width="fill"),
            ui.text(f"rtime-{i}", review.time, size=12, color=t.text_muted),
            id=f"rhdr-{i}",
            spacing=8,
            align_y="center",
        ),
        ui.text(
            f"rtext-{i}",
            f"\u201c{review.text}\u201d",
            size=14,
            color=t.text,
        ),
        id=f"review-{i}",
        spacing=4,
        padding=12,
        width="fill",
    )


if __name__ == "__main__":
    plushie.run(RatePlushie)
