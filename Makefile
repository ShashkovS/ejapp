# Makefile for the ejapp project

# --- Variables ---
# Use bash for better scripting capabilities
SHELL := /bin/bash

# Directories
BACKEND_DIR := backend
FRONTEND_DIR := frontend

# Python specific variables
VENV_DIR := $(BACKEND_DIR)/.venv
PYTHON := $(VENV_DIR)/bin/python
PIP := $(VENV_DIR)/bin/pip
RUFF := $(VENV_DIR)/bin/ruff
PYTEST := $(VENV_DIR)/bin/pytest
ALEMBIC := $(VENV_DIR)/bin/alembic
ALEMBIC_CONFIG := $(BACKEND_DIR)/alembic.ini

# Default message for new migrations
m ?= "New migration"

# --- Main Targets ---
.PHONY: help
help: ## ✨ Show this help message
	@echo "Usage: make <target>"
	@echo ""
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help

# --- Setup & Installation ---
.PHONY: setup
setup: setup-frontend setup-backend install-hooks ## 🚀 Install all dependencies for frontend and backend

.PHONY: setup-backend
setup-backend: $(VENV_DIR)/bin/activate ## 🐍 Create virtual env and install Python dependencies
$(VENV_DIR)/bin/activate: $(BACKEND_DIR)/pyproject.toml
	@echo "--- Setting up Python backend ---"
	@if [ ! -d "$(VENV_DIR)" ]; then \
		echo "Creating Python virtual environment in $(VENV_DIR)..."; \
		python3 -m venv $(VENV_DIR); \
	fi
	$(PIP) install -U pip
	echo "Installing Python dependencies..."
	$(PIP) install -e "./$(BACKEND_DIR)[dev]"
	@touch $(VENV_DIR)/bin/activate

.PHONY: setup-frontend
setup-frontend: ## 📦 Install Node.js dependencies
	@echo "--- Setting up Node.js frontend ---"
	(cd $(FRONTEND_DIR) && npm install)

.PHONY: install-hooks
install-hooks: $(VENV_DIR)/bin/pre-commit ## 🔧 Install git pre-commit hooks
	@echo "--- Installing pre-commit hooks ---"
	$(VENV_DIR)/bin/pre-commit install

# --- Development ---
.PHONY: run
run: ## 🏃 Run both dev servers (use two separate terminals)
	@echo "--- Starting development servers ---"
	@echo "Run 'make run-backend' in one terminal."
	@echo "Run 'make run-frontend' in another terminal."

.PHONY: run-backend
run-backend: ## FastAPI: Run backend dev server with auto-reload
	@echo "--- Starting backend server at http://localhost:8000 ---"
	$(VENV_DIR)/bin/uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

.PHONY: run-frontend
run-frontend: ## Vite: Run frontend dev server with auto-reload
	@echo "--- Starting frontend server at http://localhost:5173 ---"
	(cd $(FRONTEND_DIR) && npm run dev)

# --- Code Quality ---
.PHONY: format
format: format-backend format-frontend ## 💅 Format all code (Python & Frontend)

.PHONY: format-backend
format-backend: ## Format Python code with Ruff
	@echo "--- Formatting backend code ---"
	$(RUFF) format $(BACKEND_DIR)

.PHONY: format-frontend
format-frontend: ## Format frontend code with Prettier
	@echo "--- Formatting frontend code ---"
	(cd $(FRONTEND_DIR) && npx prettier --write .)

.PHONY: lint
lint: lint-backend lint-frontend ## 🔍 Lint all code (Python & Frontend)

.PHONY: lint-backend
lint-backend: ## Lint Python code with Ruff
	@echo "--- Linting backend code ---"
	$(RUFF) check --fix $(BACKEND_DIR)

.PHONY: lint-frontend
lint-frontend: ## Lint frontend code with Prettier
	@echo "--- Linting frontend code ---"
	(cd $(FRONTEND_DIR) && npx prettier --check .)

.PHONY: hooks
hooks: ## Git: Run all pre-commit hooks on all files
	@echo "--- Running pre-commit hooks on all files ---"
	$(VENV_DIR)/bin/pre-commit run --all-files

# --- Testing ---
.PHONY: test
test: test-backend test-frontend-unit ## ✅ Run backend tests and frontend unit tests

.PHONY: test-all
test-all: test-backend test-frontend-unit test-e2e ## ✅ Run ALL tests (backend, frontend unit, and e2e)

.PHONY: test-backend
test-backend: ## Run backend tests with Pytest
	@echo "--- Running backend tests ---"
	PYTHONPATH=. $(PYTEST) $(BACKEND_DIR)/tests

.PHONY: test-frontend-unit
test-frontend-unit: ## Run frontend unit tests with Vitest
	@echo "--- Running frontend unit tests ---"
	(cd $(FRONTEND_DIR) && npm run test)

.PHONY: test-e2e
test-e2e: ## Run frontend E2E tests with Playwright (headless)
	@echo "--- Running frontend E2E tests (headless) ---"
	(cd $(FRONTEND_DIR) && npm run e2e)

.PHONY: test-e2e-headed
test-e2e-headed: ## Run frontend E2E tests with Playwright (in a browser)
	@echo "--- Running frontend E2E tests (headed) ---"
	(cd $(FRONTEND_DIR) && npm run e2e:headed)

.PHONY: test-e2e-ui
test-e2e-ui: ## Open Playwright UI for interactive E2E tests
	@echo "--- Opening Playwright UI ---"
	(cd $(FRONTEND_DIR) && npm run e2e:ui)

# --- Database Migrations ---
.PHONY: migrate-new
migrate-new: ## 📜 Create a new Alembic migration. Usage: make migrate-new m="description"
	@echo "--- Creating new database migration: $(m) ---"
	PYTHONPATH=. $(ALEMBIC) -c $(ALEMBIC_CONFIG) revision --autogenerate -m "$(m)"

.PHONY: migrate-up
migrate-up: ## ⬆️ Apply all outstanding database migrations
	@echo "--- Upgrading database to the latest version ---"
	PYTHONPATH=. $(ALEMBIC) -c $(ALEMBIC_CONFIG) upgrade head

.PHONY: migrate-down
migrate-down: ## ⬇️ Revert the last database migration
	@echo "--- Downgrading database by one revision ---"
	PYTHONPATH=. $(ALEMBIC) -c $(ALEMBIC_CONFIG) downgrade -1

# --- Cleaning ---
.PHONY: clean
clean: ## 🧹 Remove temporary files (caches, build artifacts, test dbs)
	@echo "--- Cleaning up temporary files ---"
	find . -type f -name '*.pyc' -delete
	find . -type d -name '__pycache__' -exec rm -rf {} +
	rm -rf ./.ruff_cache
	rm -rf $(BACKEND_DIR)/.ruff_cache
	rm -rf $(BACKEND_DIR)/.pytest_cache
	rm -f $(BACKEND_DIR)/*.db
	rm -rf $(BACKEND_DIR)/.e2e-db
	rm -rf $(FRONTEND_DIR)/dist
	rm -rf $(FRONTEND_DIR)/test-results

.PHONY: deep-clean
deep-clean: clean ## 💣 Remove all temporary files AND installed dependencies
	@echo "--- Performing deep clean ---"
	rm -rf $(VENV_DIR)
	rm -rf $(FRONTEND_DIR)/node_modules
	rm -f .env