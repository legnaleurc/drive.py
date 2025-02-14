RM := rm -rf
PYTHON := uv run
RUFF := uvx ruff

PKG_FILES := pyproject.toml
PKG_LOCK := uv.lock
ENV_DIR := .venv
ENV_LOCK := $(ENV_DIR)/pyvenv.cfg

MODULE_LIST := src/app

.PHONY: all format lint clean purge test

all: venv

format: venv
	$(RUFF) check --fix
	$(RUFF) format

lint: venv
	$(RUFF) check
	$(RUFF) format --check

clean:
	$(RM) ./src/*.egg-info

purge: clean
	$(RM) $(ENV_DIR) .ruff_cache

test: venv
	$(PYTHON) -m compileall $(MODULE_LIST)

venv: $(ENV_LOCK)

$(ENV_LOCK): $(PKG_LOCK)
	uv sync --frozen
	touch $@

$(PKG_LOCK): $(PKG_FILES)
	uv lock
	touch $@
