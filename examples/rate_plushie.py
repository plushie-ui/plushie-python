"""Rate Plushie -- app rating page with custom canvas widgets.

Demonstrates custom canvas widgets (StarRating, ThemeToggle) composed
with styled containers. The "Dark humor" toggle animates a face emoji
and flips the entire page theme.

The review form showcases form validation with:

- Per-field error state tracked in the model
- Visual error styling via ``StyleMap`` (border + background tint)
- Accessible error wiring via ``a11y`` (required, invalid, error_message)
- Validate-on-submit with clear-on-change for responsive UX

Run::

    python -m plushie run examples.rate_plushie:RatePlushie
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

import plushie
from examples.widgets.star_rating import StarRating
from examples.widgets.theme_toggle import ThemeToggle
from plushie import ui
from plushie.events import Click, Input, RawEvent, Submit
from plushie.types import Border, StyleMap, Theme


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
    dark_mode: bool = False
    toggle_progress: float = 0.0
    toggle_target: float = 0.0
    reviews: tuple[Review, ...] = INITIAL_REVIEWS
    review_name: str = ""
    review_comment: str = ""
    errors: dict[str, str] = field(default_factory=dict)


def _validate_review(model: Model) -> dict[str, str]:
    errors: dict[str, str] = {}
    if not model.review_name.strip():
        errors["name"] = "Name is required"
    if not model.review_comment.strip():
        errors["comment"] = "Review text is required"
    if model.rating <= 0:
        errors["rating"] = "Please select a rating"
    return errors


def _submit_review(model: Model) -> Model:
    errors = _validate_review(model)
    if errors:
        return replace(model, errors=errors)

    name = model.review_name.strip()
    comment = model.review_comment.strip()
    review = Review(stars=model.rating, user=name, time="just now", text=comment)
    return replace(
        model,
        reviews=(review, *model.reviews),
        review_name="",
        review_comment="",
        rating=0,
        errors={},
    )


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
    error_text: str
    error_border: str
    error_bg: str


def _theme(p: float) -> _Theme:
    return _Theme(
        page_bg=_fade((248, 248, 250), (19, 19, 31), p),
        card_bg=_fade((255, 255, 255), (28, 28, 50), p),
        card_border=_fade((224, 224, 224), (42, 42, 74), p),
        text=_fade((26, 26, 26), (240, 240, 245), p),
        text_secondary=_fade((102, 102, 102), (153, 153, 187), p),
        text_muted=_fade((170, 170, 170), (85, 85, 119), p),
        error_text=_fade((185, 28, 28), (255, 100, 100), p),
        error_border=_fade((220, 38, 38), (255, 80, 80), p),
        error_bg=_fade((254, 242, 242), (50, 20, 20), p),
    )


def _input_style(error: str | None, t: _Theme) -> Any:
    if error is None:
        return "default"
    error_border = Border(color=t.error_border, width=2, radius=4)
    return StyleMap(
        border=error_border,
        background=t.error_bg,
        focused={"border": error_border},
    )


class RatePlushie(plushie.App[Model]):
    """App rating page with star rating and theme toggle."""

    def init(self) -> Model:
        return Model()

    def update(self, model: Model, event: object) -> Model:
        match event:
            # Star rating emits :select with the number of stars.
            case RawEvent(kind="select", id="stars", data=data):
                stars = data.get("value", 0)
                errors = {k: v for k, v in model.errors.items() if k != "rating"}
                return replace(model, rating=stars, errors=errors)

            # Theme toggle emits :toggle with the new state.
            case RawEvent(kind="toggle", id="theme-toggle", data=data):
                return replace(model, dark_mode=data.get("value", False))

            case Input(id="review-name", value=v):
                errors = {k: val for k, val in model.errors.items() if k != "name"}
                return replace(model, review_name=v, errors=errors)
            case Input(id="review-comment", value=v):
                errors = {k: val for k, val in model.errors.items() if k != "comment"}
                return replace(model, review_comment=v, errors=errors)
            case Click(id="submit-review"):
                return _submit_review(model)
            case Submit(id="review-name"):
                return _submit_review(model)

            case _:
                return model

    def subscribe(self, model: Model) -> list[Any]:
        return []

    def view(self, model: Model) -> dict[str, Any]:
        p = 1.0 if model.dark_mode else 0.0
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
    stars_children: list[dict[str, Any]] = [
        StarRating.build(
            "stars",
            props={"rating": model.rating, "theme_progress": p},
        ),
    ]
    rating_error = model.errors.get("rating")
    if rating_error:
        stars_children.append(
            ui.text(
                "stars-error",
                rating_error,
                size=12,
                color=t.error_text,
                a11y={"role": "alert", "live": "polite"},
            )
        )

    return ui.container(
        "rating-card",
        ui.column(
            ui.text(
                "prompt",
                "How would you rate Plushie?",
                size=14,
                color=t.text_secondary,
            ),
            ui.column(*stars_children, spacing=4),
            ui.rule(),
            _review_form(model, t),
            _theme_row(model, t),
            spacing=20,
            width="fill",
        ),
        padding=24,
        width="fill",
        border={"width": 1, "color": t.card_border, "rounded": 12},
        background=t.card_bg,
    )


def _review_form(model: Model, t: _Theme) -> dict[str, Any]:
    name_error = model.errors.get("name")
    comment_error = model.errors.get("comment")

    name_children: list[dict[str, Any]] = [
        ui.text_input(
            "review-name",
            model.review_name,
            placeholder="Your name",
            on_submit=True,
            style=_input_style(name_error, t),
            a11y={
                "label": "Your name",
                "required": True,
                "invalid": name_error is not None,
                "error_message": "review-name-error" if name_error else None,
            },
        ),
    ]
    if name_error:
        name_children.append(
            ui.text(
                "review-name-error",
                name_error,
                size=12,
                color=t.error_text,
                a11y={"role": "alert", "live": "polite"},
            )
        )

    comment_children: list[dict[str, Any]] = [
        ui.text_editor(
            "review-comment",
            model.review_comment,
            placeholder="Write your review...",
            height=80,
            style=_input_style(comment_error, t),
            a11y={
                "label": "Review text",
                "required": True,
                "invalid": comment_error is not None,
                "error_message": "review-comment-error" if comment_error else None,
            },
        ),
    ]
    if comment_error:
        comment_children.append(
            ui.text(
                "review-comment-error",
                comment_error,
                size=12,
                color=t.error_text,
                a11y={"role": "alert", "live": "polite"},
            )
        )

    return ui.column(
        ui.column(*name_children, spacing=4, width="fill"),
        ui.column(*comment_children, spacing=4, width="fill"),
        ui.button("submit-review", "Submit Review"),
        id="review-form",
        spacing=12,
        width="fill",
    )


def _theme_row(model: Model, t: _Theme) -> dict[str, Any]:
    return ui.row(
        ui.space(width="fill"),
        ui.text("toggle-label", "Dark humor", color=t.text_secondary),
        ThemeToggle.build("theme-toggle"),
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
            StarRating.build(
                f"rstars-{i}",
                props={
                    "rating": review.stars,
                    "readonly": True,
                    "scale": 0.4,
                    "theme_progress": p,
                },
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
