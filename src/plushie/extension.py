"""Backwards-compatibility re-exports from :mod:`plushie.native_widget`.

This module exists so ``from plushie.extension import ExtensionDef``
continues to work.  New code should import from
:mod:`plushie.native_widget` directly.

``ExtensionDef`` is an alias for :class:`~plushie.native_widget.NativeWidgetDef`.
"""

from __future__ import annotations

from plushie.native_widget import (
    RESERVED_PROP_NAMES as RESERVED_PROP_NAMES,
)
from plushie.native_widget import (
    CommandDef as CommandDef,
)
from plushie.native_widget import (
    NativeWidgetDef as NativeWidgetDef,
)
from plushie.native_widget import (
    ParamDef as ParamDef,
)
from plushie.native_widget import (
    ParamType as ParamType,
)
from plushie.native_widget import (
    PropDef as PropDef,
)
from plushie.native_widget import (
    PropType as PropType,
)
from plushie.native_widget import (
    build_command as build_command,
)
from plushie.native_widget import (
    build_node as build_node,
)
from plushie.native_widget import (
    command_names as command_names,
)
from plushie.native_widget import (
    generate_cargo_toml as generate_cargo_toml,
)
from plushie.native_widget import (
    generate_main_rs as generate_main_rs,
)
from plushie.native_widget import (
    prop_names as prop_names,
)
from plushie.native_widget import (
    validate as validate,
)
from plushie.native_widget import (
    validate_all as validate_all,
)

#: Alias for :class:`NativeWidgetDef`.
ExtensionDef = NativeWidgetDef

__all__ = [
    "RESERVED_PROP_NAMES",
    "CommandDef",
    "ExtensionDef",
    "NativeWidgetDef",
    "ParamDef",
    "ParamType",
    "PropDef",
    "PropType",
    "build_command",
    "build_node",
    "command_names",
    "generate_cargo_toml",
    "generate_main_rs",
    "prop_names",
    "validate",
    "validate_all",
]
