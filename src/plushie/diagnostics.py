"""Typed diagnostic variants emitted by the renderer.

The renderer's ``plushie-core::Diagnostic`` enum enumerates every
diagnostic the renderer can emit (tree normalization, prop validation,
font cap, panic guards, transport violations). Each variant arrives on
the wire as a map with a discriminator (``"kind": "..."``) and
variant-specific fields. :func:`decode` dispatches on that
discriminator to the matching ``@dataclass`` so apps pattern match on
a typed value rather than on a raw ``dict``.

Typed diagnostics flow through :class:`DiagnosticMessage`, which
carries the session ID, severity level, and the typed diagnostic.

## Unknown variants

The decoder raises :class:`ValueError` on an unrecognised ``kind``. A
new renderer variant requires an SDK update; silently dropping unknown
diagnostics would hide host / renderer version skew that the runtime
needs to see.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class DuplicateId:
    """A widget ID collided with one already declared within the same window scope."""

    id: str
    window_id: str | None = None


@dataclass(frozen=True, slots=True)
class EmptyId:
    """A view declared a widget with an empty ID where a non-empty one was expected."""

    type_name: str


@dataclass(frozen=True, slots=True)
class MultipleTopLevelWindows:
    """The tree holds more than one top-level window child."""

    window_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class UnknownWindow:
    """A subscription was declared for a window not present in the tree."""

    window_id: str
    subscription_tag: str


@dataclass(frozen=True, slots=True)
class UnrecognizedWidgetPlaceholder:
    """A ``__widget__`` placeholder in the tree had no registered expander."""

    id: str


@dataclass(frozen=True, slots=True)
class TreeDepthExceeded:
    """Tree traversal reached the global depth cap; the subtree was skipped."""

    id: str
    max_depth: int


@dataclass(frozen=True, slots=True)
class TooManyDuplicates:
    """Duplicate-ID collection stopped at the configured cap."""

    limit: int


@dataclass(frozen=True, slots=True)
class WidgetIdInvalid:
    """A user-authored widget ID violated the canonical ID ruleset."""

    reason: str
    type_name: str
    id: str
    detail: str


@dataclass(frozen=True, slots=True)
class MissingAccessibleName:
    """A widget that requires a screen-reader-announcable name was declared without one."""

    type_name: str
    id: str


@dataclass(frozen=True, slots=True)
class A11yRefUnresolved:
    """A cross-widget a11y reference did not resolve to any declared widget."""

    id: str
    key: str
    value: str
    is_member: bool


@dataclass(frozen=True, slots=True)
class PropRangeExceeded:
    """A numeric prop was outside its declared range and was clamped."""

    id: str
    type_name: str
    prop: str
    raw: float
    clamped: float
    non_finite: bool


@dataclass(frozen=True, slots=True)
class PropTypeMismatch:
    """A prop value had an unexpected JSON type."""

    id: str
    type_name: str
    prop: str
    value_debug: str
    expected_debug: str


@dataclass(frozen=True, slots=True)
class PropUnknown:
    """A widget carried a prop name not in its declared schema."""

    id: str
    type_name: str
    prop: str
    known_debug: str


@dataclass(frozen=True, slots=True)
class ContentLengthExceeded:
    """A text-like content prop exceeded its per-widget byte cap and was truncated."""

    id: str
    field: str
    actual: int
    cap: int
    truncated: int


@dataclass(frozen=True, slots=True)
class FontCacheCapExceeded:
    """The leaked font-family-name cache reached its entry cap."""

    max: int


@dataclass(frozen=True, slots=True)
class FontCapExceeded:
    """Inline fonts declared in Settings exceeded the process-wide cap."""

    max: int
    requested: int
    granted: int
    dropped: int


@dataclass(frozen=True, slots=True)
class FontFamilyNotFound:
    """A font family from default_font or its fallback chain did not resolve."""

    family: str


@dataclass(frozen=True, slots=True)
class InvalidSettings:
    """The Settings payload failed typed ``deny_unknown_fields`` validation."""

    detail: str


@dataclass(frozen=True, slots=True)
class RequiredWidgetsMissing:
    """The Settings handshake declared native widget names the renderer does not know about."""

    missing: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class WidgetPanic:
    """A non-trusted widget panicked inside the registry's ``catch_unwind`` firewall."""

    id: str
    type_name: str
    label: str


@dataclass(frozen=True, slots=True)
class SvgParseError:
    """SVG decode returned a parse error."""

    id: str
    source: str
    detail: str


@dataclass(frozen=True, slots=True)
class SvgDecodeTimeout:
    """SVG decode exceeded its wall-clock budget."""

    id: str
    source: str
    deadline_debug: str


@dataclass(frozen=True, slots=True)
class DashCacheCapExceeded:
    """The leaked dash-segment cache reached its entry cap."""

    max: int


@dataclass(frozen=True, slots=True)
class EmitterCoalesceCapExceeded:
    """The renderer-lib event coalesce map hit its cap and was force-flushed."""

    cap: int


@dataclass(frozen=True, slots=True)
class WidgetIdTypeCollision:
    """A composite widget ID was registered against two different widget types."""

    id: str
    existing_type: str
    incoming_type: str


@dataclass(frozen=True, slots=True)
class ViewPanicked:
    """The view function panicked and was caught by the runtime's safety net."""

    consecutive: int
    message: str


@dataclass(frozen=True, slots=True)
class UpdatePanicked:
    """The update function panicked and was caught by the runtime.

    The model is reverted to the last-good snapshot so the app keeps
    running; the consecutive counter is shared with
    :class:`ViewPanicked` so the frozen-UI overlay surfaces after
    enough total panics across either callback.
    """

    consecutive: int
    message: str


@dataclass(frozen=True, slots=True)
class UnknownMessageType:
    """A wire message carried a ``type`` field the SDK does not recognise."""

    msg_type: str


@dataclass(frozen=True, slots=True)
class DispatchLoopExceeded:
    """The runtime's command dispatch chain exceeded the configured depth limit."""

    depth: int
    limit: int


@dataclass(frozen=True, slots=True)
class BufferOverflow:
    """A single wire message exceeded the protocol's 64 MiB per-message size cap."""

    size: int
    limit: int


type Diagnostic = (
    DuplicateId
    | EmptyId
    | MultipleTopLevelWindows
    | UnknownWindow
    | UnrecognizedWidgetPlaceholder
    | TreeDepthExceeded
    | TooManyDuplicates
    | WidgetIdInvalid
    | MissingAccessibleName
    | A11yRefUnresolved
    | PropRangeExceeded
    | PropTypeMismatch
    | PropUnknown
    | ContentLengthExceeded
    | FontCacheCapExceeded
    | FontCapExceeded
    | FontFamilyNotFound
    | InvalidSettings
    | RequiredWidgetsMissing
    | WidgetPanic
    | SvgParseError
    | SvgDecodeTimeout
    | DashCacheCapExceeded
    | EmitterCoalesceCapExceeded
    | WidgetIdTypeCollision
    | ViewPanicked
    | UpdatePanicked
    | UnknownMessageType
    | DispatchLoopExceeded
    | BufferOverflow
)
"""Union of every typed diagnostic variant the renderer can emit."""


@dataclass(frozen=True, slots=True)
class DiagnosticMessage:
    """A structured diagnostic delivered through the renderer's diagnostic wire channel.

    Wire shape: ``{type: "diagnostic", session, level, diagnostic: {kind, ...}}``.
    The ``diagnostic`` field is one of the typed variants in this
    module, unified by the :data:`Diagnostic` alias.

    Attributes:
        session: Session the diagnostic is attributable to. Empty for
            process-scoped diagnostics (font load failures, renderer
            startup or panic, writer-dead, anything that affects the
            whole renderer rather than one session). Non-empty for
            session-scoped diagnostics (widget panics, view errors,
            tree validation warnings, anything produced inside a
            session's update / apply pipeline).
        level: Severity: ``"info"``, ``"warn"``, or ``"error"``.
        diagnostic: Typed variant, one of the classes unified by the
            :data:`Diagnostic` alias.
    """

    session: str
    level: str
    diagnostic: Diagnostic


_KINDS: dict[str, type] = {
    "duplicate_id": DuplicateId,
    "empty_id": EmptyId,
    "multiple_top_level_windows": MultipleTopLevelWindows,
    "unknown_window": UnknownWindow,
    "unrecognized_widget_placeholder": UnrecognizedWidgetPlaceholder,
    "tree_depth_exceeded": TreeDepthExceeded,
    "too_many_duplicates": TooManyDuplicates,
    "widget_id_invalid": WidgetIdInvalid,
    "missing_accessible_name": MissingAccessibleName,
    "a11y_ref_unresolved": A11yRefUnresolved,
    "prop_range_exceeded": PropRangeExceeded,
    "prop_type_mismatch": PropTypeMismatch,
    "prop_unknown": PropUnknown,
    "content_length_exceeded": ContentLengthExceeded,
    "font_cache_cap_exceeded": FontCacheCapExceeded,
    "font_cap_exceeded": FontCapExceeded,
    "font_family_not_found": FontFamilyNotFound,
    "invalid_settings": InvalidSettings,
    "required_widgets_missing": RequiredWidgetsMissing,
    "widget_panic": WidgetPanic,
    "svg_parse_error": SvgParseError,
    "svg_decode_timeout": SvgDecodeTimeout,
    "dash_cache_cap_exceeded": DashCacheCapExceeded,
    "emitter_coalesce_cap_exceeded": EmitterCoalesceCapExceeded,
    "widget_id_type_collision": WidgetIdTypeCollision,
    "view_panicked": ViewPanicked,
    "update_panicked": UpdatePanicked,
    "unknown_message_type": UnknownMessageType,
    "dispatch_loop_exceeded": DispatchLoopExceeded,
    "buffer_overflow": BufferOverflow,
}


def known_kinds() -> tuple[str, ...]:
    """Every wire-level ``kind`` string this SDK version decodes.

    Useful for assertions that the SDK covers the renderer's enum.
    """
    return tuple(_KINDS.keys())


_LIST_FIELDS: dict[type, frozenset[str]] = {
    MultipleTopLevelWindows: frozenset({"window_ids"}),
    RequiredWidgetsMissing: frozenset({"missing"}),
}


def decode(payload: dict[str, Any]) -> Diagnostic:
    """Decode a typed diagnostic from a wire payload dict.

    The payload is the value of the ``diagnostic`` field on the
    top-level ``diagnostic`` wire message: a dict containing ``kind``
    plus variant-specific fields.

    Raises:
        ValueError: if ``payload`` has no ``kind`` field or the
            ``kind`` is not one this SDK version recognises.
    """
    if not isinstance(payload, dict):
        raise ValueError(
            f"diagnostic payload must be a dict, got {type(payload).__name__}"
        )

    kind = payload.get("kind")
    if not isinstance(kind, str):
        raise ValueError(f"diagnostic payload missing string 'kind' field: {payload!r}")

    cls = _KINDS.get(kind)
    if cls is None:
        raise ValueError(
            f"unknown diagnostic kind {kind!r}. The renderer emitted a diagnostic "
            f"this SDK version does not recognize. Ensure the SDK and renderer "
            f"versions are compatible."
        )

    list_fields = _LIST_FIELDS.get(cls, frozenset())
    kwargs: dict[str, Any] = {}
    for field_name in cls.__dataclass_fields__:  # type: ignore[attr-defined]
        raw = payload.get(field_name)
        if field_name in list_fields:
            kwargs[field_name] = tuple(raw) if raw is not None else ()
        else:
            kwargs[field_name] = raw
    return cls(**kwargs)  # type: ignore[no-any-return]


__all__ = [
    "A11yRefUnresolved",
    "BufferOverflow",
    "ContentLengthExceeded",
    "DashCacheCapExceeded",
    "Diagnostic",
    "DiagnosticMessage",
    "DispatchLoopExceeded",
    "DuplicateId",
    "EmitterCoalesceCapExceeded",
    "EmptyId",
    "FontCacheCapExceeded",
    "FontCapExceeded",
    "FontFamilyNotFound",
    "InvalidSettings",
    "MissingAccessibleName",
    "MultipleTopLevelWindows",
    "PropRangeExceeded",
    "PropTypeMismatch",
    "PropUnknown",
    "RequiredWidgetsMissing",
    "SvgDecodeTimeout",
    "SvgParseError",
    "TooManyDuplicates",
    "TreeDepthExceeded",
    "UnknownMessageType",
    "UnknownWindow",
    "UnrecognizedWidgetPlaceholder",
    "UpdatePanicked",
    "ViewPanicked",
    "WidgetIdInvalid",
    "WidgetIdTypeCollision",
    "WidgetPanic",
    "decode",
    "known_kinds",
]
