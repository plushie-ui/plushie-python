"""Tests for the renderer subprocess environment whitelist.

The whitelist must match the canonical list shared across every host
SDK: secrets and unrelated vars never propagate to the renderer child,
while display/rendering/locale/accessibility/font/plushie-toggle vars
do.
"""

from __future__ import annotations

import os

from plushie.connection import _build_env


def test_forwards_whitelisted_exact_vars(monkeypatch):
    monkeypatch.setenv("HOME", "/home/tester")
    monkeypatch.setenv("RUST_LOG", "plushie=debug")

    env = _build_env()

    assert env.get("HOME") == "/home/tester"
    assert env.get("RUST_LOG") == "plushie=debug"


def test_forwards_prefix_matched_vars(monkeypatch):
    monkeypatch.setenv("LC_ALL", "en_US.UTF-8")
    monkeypatch.setenv("MESA_GL_VERSION_OVERRIDE", "4.5")

    env = _build_env()

    assert env.get("LC_ALL") == "en_US.UTF-8"
    assert env.get("MESA_GL_VERSION_OVERRIDE") == "4.5"


def test_forwards_plushie_prefix(monkeypatch):
    monkeypatch.setenv("PLUSHIE_NO_CATCH_UNWIND", "1")
    monkeypatch.setenv("PLUSHIE_DEBUG_FOO", "bar")

    env = _build_env()

    assert env.get("PLUSHIE_NO_CATCH_UNWIND") == "1"
    assert env.get("PLUSHIE_DEBUG_FOO") == "bar"


def test_strips_non_whitelisted_secrets(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "leak-me")
    monkeypatch.setenv("GITHUB_TOKEN", "also-leak")
    monkeypatch.setenv("DATABASE_URL", "postgres://secret")

    env = _build_env()

    assert "AWS_ACCESS_KEY_ID" not in env
    assert "GITHUB_TOKEN" not in env
    assert "DATABASE_URL" not in env


def test_extra_overrides_take_precedence():
    env = _build_env({"RUST_LOG": "plushie=trace", "CUSTOM_VAR": "hi"})

    assert env.get("RUST_LOG") == "plushie=trace"
    assert env.get("CUSTOM_VAR") == "hi"


def test_subprocess_does_not_see_leaked_secret(monkeypatch):
    """The filtered env dict must be usable with subprocess.Popen."""
    monkeypatch.setenv("SHOULD_NOT_LEAK", "xxx")

    env = _build_env()

    assert "SHOULD_NOT_LEAK" not in env
    # Sanity: the current process does still see it.
    assert os.environ.get("SHOULD_NOT_LEAK") == "xxx"
