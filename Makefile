# Makefile for a uv-managed Python repo
# Assumes:
#  - pyproject.toml defines dependencies + optional extras (e.g. "parquet")
#  - you want a local virtualenv at .venv/
#  - commands are run via `uv run ...` (no manual activation required)

SHELL := /bin/bash
PYTHON := python3
VENV := .venv

# Default extra set (override like: make sync EXTRAS="parquet")
EXTRAS ?=
UV_SYNC_FLAGS ?=

# If you want reproducible installs, create uv.lock and use --frozen in CI
FROZEN ?= 0

ifeq ($(FROZEN),1)
  UV_SYNC_FLAGS += --frozen
endif

.PHONY: help venv sync sync-parquet lock fmt lint test run-pack run-qc run-inspect build clean distclean ci

help:
	@echo "Targets:"
	@echo "  venv            Create .venv (uv venv)"
	@echo "  sync            Install deps into .venv (uv sync)"
	@echo "  sync-parquet    Install deps + parquet extra (uv sync --extra parquet)"
	@echo "  lock            Generate/refresh uv.lock (uv lock)"
	@echo "  fmt             Format (ruff format) [if configured]"
	@echo "  lint            Lint (ruff) [if configured]"
	@echo "  test            Run tests (pytest) [if configured]"
	@echo "  run-pack        Example: build a .hfx archive"
	@echo "  run-qc          Example: compute QC stats"
	@echo "  run-inspect     Example: inspect .hfx or metadata.json"
	@echo "  build           Build wheel/sdist (uv build)"
	@echo "  clean           Remove build artifacts"
	@echo "  distclean       clean + remove .venv"
	@echo "  ci              Typical CI sequence (sync -> lint -> test -> build)"

venv:
	uv venv $(VENV)

# Install project deps (and the project itself) into .venv
# Use EXTRAS="parquet" to include optional extras
sync: venv
	uv sync $(UV_SYNC_FLAGS) $(if $(EXTRAS),--extra $(EXTRAS),)

sync-parquet:
	$(MAKE) sync EXTRAS="parquet"

# Create or update uv.lock
lock:
	uv lock

# ---- Quality targets (only work if you add these tools to pyproject dependencies) ----
fmt: sync
	uv run ruff format .

lint: sync
	uv run ruff check .

test: sync
	uv run pytest -q

# ---- Example run targets (adjust paths as needed) ----
# Usage:
#   make run-pack META=examples/metadata.json OUT=dist/example.hfx
META ?= metadata.json
OUT ?= dist/example.hfx
HFX ?= dist/example.hfx

run-pack: sync
	uv run hfx-pack pack $(META) -o $(OUT) --manifest --hash sha256

run-qc: sync
	uv run hfx-qc qc $(META) --index-row

run-inspect: sync
	uv run hfx-inspect inspect $(HFX)

# ---- Build ----
build: sync
	uv build

clean:
	rm -rf build/ dist/ *.egg-info .pytest_cache .ruff_cache .mypy_cache

distclean: clean
	rm -rf $(VENV)

ci:
	$(MAKE) sync FROZEN=1
	-$(MAKE) lint FROZEN=1
	-$(MAKE) test FROZEN=1
	$(MAKE) build FROZEN=1

