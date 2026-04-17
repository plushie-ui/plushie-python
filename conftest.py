"""Root conftest for the plushie test suite.

Registers the plushie pytest plugin by module path so pytest picks
up the fixtures without depending on entry-point reinstallation.
This avoids a stale-install trap where `.dist-info/entry_points.txt`
drifts from `pyproject.toml` after editable installs.
"""

from __future__ import annotations

pytest_plugins = ["plushie.testing.plugin"]
