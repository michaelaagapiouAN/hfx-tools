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

.PHONY: help venv sync sync-parquet sync-streamlit lock fmt lint test build clean distclean ci streamlit activate

help:
	@echo "Targets:"
	@echo "  venv            Create .venv (uv venv)"
	@echo "  sync            Install deps into .venv (uv sync)"
	@echo "  activate        Print the activate command for this venv (usage: eval \$$(make activate))"
	@echo "  sync-streamlit  Install deps + streamlit extra"
	@echo "  streamlit       Launch the Streamlit web UI"
	@echo "  lock            Generate/refresh uv.lock"
	@echo "  fmt             Format code (ruff format)"
	@echo "  lint            Lint code (ruff check)"
	@echo "  test            Run tests (pytest)"
	@echo "  build           Build wheel/sdist"
	@echo "  clean           Remove build artifacts"
	@echo "  distclean       clean + remove .venv"
	@echo "  ci              CI sequence (sync -> lint -> test -> build)"

venv:
	uv venv $(VENV)

# Install project deps (and the project itself) into .venv
# Use EXTRAS="parquet" to include optional extras
sync: venv
	uv sync $(UV_SYNC_FLAGS) $(if $(EXTRAS),--extra $(EXTRAS),)

sync-parquet:
	$(MAKE) sync EXTRAS="parquet"

activate:
	@echo 'source $(CURDIR)/$(VENV)/bin/activate'

sync-streamlit:
	$(MAKE) sync EXTRAS="streamlit"

streamlit: sync-streamlit
	uv run streamlit run hfx_tools/streamlit_app.py

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

