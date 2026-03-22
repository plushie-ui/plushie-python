"""Subscription types for ongoing event sources.

Return subscriptions from the ``subscribe`` callback.  The runtime diffs
the list each cycle using ``key``: subscriptions with the same key are
considered identical and kept alive; new keys trigger a subscribe message
to the renderer; removed keys trigger an unsubscribe.

Renderer subscriptions accept an optional ``max_rate`` that tells the
renderer to coalesce events beyond the given rate (events per second).

Usage::

    from plushie.subscriptions import Subscription

    def subscribe(self, model):
        subs = [Subscription.on_key_press("keys")]
        if model.animating:
            subs.append(Subscription.every(16, "tick"))
        return subs
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Subscription:
    """A subscription spec describing an ongoing event source.

    Subscriptions are pure data.  The runtime interprets them to manage
    subscribe/unsubscribe messages to the renderer and local timers.

    Attributes:
        kind: The subscription kind (e.g. ``"every"``,
            ``"on_key_press"``).
        tag: Identifier for subscription management and diffing.
        interval_ms: Timer interval in milliseconds (``every`` only).
        max_rate: Optional rate limit (events per second) for renderer
            subscriptions.  ``None`` means no limit.
    """

    kind: str
    tag: str
    interval_ms: int | None = None
    max_rate: int | None = None

    @property
    def key(self) -> tuple[str, ...]:
        """Unique identity for subscription diffing.

        Timer subscriptions key on ``(kind, interval_ms, tag)``.
        Renderer subscriptions key on ``(kind, tag)``.
        """
        if self.kind == "every":
            return ("every", str(self.interval_ms), self.tag)
        return (self.kind, self.tag)

    @property
    def wire_kind(self) -> str:
        """Wire format kind string for this subscription."""
        return self.kind

    # ------------------------------------------------------------------
    # Timer
    # ------------------------------------------------------------------

    @staticmethod
    def every(interval_ms: int, tag: str) -> Subscription:
        """Timer that fires every *interval_ms* milliseconds.

        Delivers a ``TimerTick`` event with the given *tag* to ``update``.
        """
        return Subscription(kind="every", tag=tag, interval_ms=interval_ms)

    # ------------------------------------------------------------------
    # Keyboard
    # ------------------------------------------------------------------

    @staticmethod
    def on_key_press(tag: str, *, max_rate: int | None = None) -> Subscription:
        """Subscribe to key press events."""
        return Subscription(kind="on_key_press", tag=tag, max_rate=max_rate)

    @staticmethod
    def on_key_release(tag: str, *, max_rate: int | None = None) -> Subscription:
        """Subscribe to key release events."""
        return Subscription(kind="on_key_release", tag=tag, max_rate=max_rate)

    @staticmethod
    def on_modifiers_changed(tag: str, *, max_rate: int | None = None) -> Subscription:
        """Subscribe to keyboard modifier state changes (shift, ctrl, alt, etc.)."""
        return Subscription(kind="on_modifiers_changed", tag=tag, max_rate=max_rate)

    # ------------------------------------------------------------------
    # Mouse
    # ------------------------------------------------------------------

    @staticmethod
    def on_mouse_move(tag: str, *, max_rate: int | None = None) -> Subscription:
        """Subscribe to mouse movement events (also delivers enter/leave)."""
        return Subscription(kind="on_mouse_move", tag=tag, max_rate=max_rate)

    @staticmethod
    def on_mouse_button(tag: str, *, max_rate: int | None = None) -> Subscription:
        """Subscribe to mouse button press and release events."""
        return Subscription(kind="on_mouse_button", tag=tag, max_rate=max_rate)

    @staticmethod
    def on_mouse_scroll(tag: str, *, max_rate: int | None = None) -> Subscription:
        """Subscribe to mouse scroll (wheel) events."""
        return Subscription(kind="on_mouse_scroll", tag=tag, max_rate=max_rate)

    # ------------------------------------------------------------------
    # Touch
    # ------------------------------------------------------------------

    @staticmethod
    def on_touch(tag: str, *, max_rate: int | None = None) -> Subscription:
        """Subscribe to touch events (pressed, moved, lifted, lost)."""
        return Subscription(kind="on_touch", tag=tag, max_rate=max_rate)

    # ------------------------------------------------------------------
    # IME
    # ------------------------------------------------------------------

    @staticmethod
    def on_ime(tag: str, *, max_rate: int | None = None) -> Subscription:
        """Subscribe to IME (Input Method Editor) events."""
        return Subscription(kind="on_ime", tag=tag, max_rate=max_rate)

    # ------------------------------------------------------------------
    # Window
    # ------------------------------------------------------------------

    @staticmethod
    def on_window_event(tag: str, *, max_rate: int | None = None) -> Subscription:
        """Subscribe to all window events (resize, move, focus, etc.)."""
        return Subscription(kind="on_window_event", tag=tag, max_rate=max_rate)

    @staticmethod
    def on_window_open(tag: str, *, max_rate: int | None = None) -> Subscription:
        """Subscribe to window open events."""
        return Subscription(kind="on_window_open", tag=tag, max_rate=max_rate)

    @staticmethod
    def on_window_close(tag: str, *, max_rate: int | None = None) -> Subscription:
        """Subscribe to window close request events."""
        return Subscription(kind="on_window_close", tag=tag, max_rate=max_rate)

    @staticmethod
    def on_window_resize(tag: str, *, max_rate: int | None = None) -> Subscription:
        """Subscribe to window resize events."""
        return Subscription(kind="on_window_resize", tag=tag, max_rate=max_rate)

    @staticmethod
    def on_window_move(tag: str, *, max_rate: int | None = None) -> Subscription:
        """Subscribe to window move events."""
        return Subscription(kind="on_window_move", tag=tag, max_rate=max_rate)

    @staticmethod
    def on_window_focus(tag: str, *, max_rate: int | None = None) -> Subscription:
        """Subscribe to window focus gained events."""
        return Subscription(kind="on_window_focus", tag=tag, max_rate=max_rate)

    @staticmethod
    def on_window_unfocus(tag: str, *, max_rate: int | None = None) -> Subscription:
        """Subscribe to window focus lost events."""
        return Subscription(kind="on_window_unfocus", tag=tag, max_rate=max_rate)

    # ------------------------------------------------------------------
    # File drop
    # ------------------------------------------------------------------

    @staticmethod
    def on_file_drop(tag: str, *, max_rate: int | None = None) -> Subscription:
        """Subscribe to file drop events (also delivers hovered/hover-left)."""
        return Subscription(kind="on_file_drop", tag=tag, max_rate=max_rate)

    # ------------------------------------------------------------------
    # Animation
    # ------------------------------------------------------------------

    @staticmethod
    def on_animation_frame(tag: str, *, max_rate: int | None = None) -> Subscription:
        """Subscribe to animation frame events (vsync ticks)."""
        return Subscription(kind="on_animation_frame", tag=tag, max_rate=max_rate)

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------

    @staticmethod
    def on_theme_change(tag: str, *, max_rate: int | None = None) -> Subscription:
        """Subscribe to system theme changes (light/dark mode)."""
        return Subscription(kind="on_theme_change", tag=tag, max_rate=max_rate)

    # ------------------------------------------------------------------
    # Catch-all
    # ------------------------------------------------------------------

    @staticmethod
    def on_event(tag: str, *, max_rate: int | None = None) -> Subscription:
        """Subscribe to all renderer events (catch-all)."""
        return Subscription(kind="on_event", tag=tag, max_rate=max_rate)


__all__ = ["Subscription"]
