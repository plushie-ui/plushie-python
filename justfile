# plushie-python - Development Tasks
#
# Run `just` to see available recipes.
# Run `just preflight` before pushing to catch CI failures locally.

set shell := ["bash", "-euo", "pipefail", "-c"]

default:
    @just --list

# Install dependencies
deps:
    uv sync --all-extras

# Run all CI checks locally (same as CI pipeline).
# Auto-detects ../plushie-rust as PLUSHIE_RUST_SOURCE_PATH when not set.
# Set PLUSHIE_RUST_SOURCE_PATH="" to force non-local (skip auto-detect).
preflight: deps
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -z "${PLUSHIE_RUST_SOURCE_PATH+x}" ]] && [[ -d "../plushie-rust" ]]; then
        export PLUSHIE_RUST_SOURCE_PATH="$(cd ../plushie-rust && pwd)"
        echo "==> auto: PLUSHIE_RUST_SOURCE_PATH=$PLUSHIE_RUST_SOURCE_PATH"
    fi
    ./bin/preflight

# Run tests
test:
    uv run pytest

# Check code formatting
fmt-check:
    uv run ruff format --check src tests examples

# Apply code formatting
fmt:
    uv run ruff format src tests examples

# Run linter
lint:
    uv run ruff check src tests examples

# Run type checker
typecheck:
    uv run pyright src tests examples

# Remove gitignored build artifacts
clean:
    git clean -fdX
