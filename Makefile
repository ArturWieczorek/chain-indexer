# Convenience targets for the course. Run `make help` to see them all.
# These assume a virtual environment. Create one with:
#   python3 -m venv .venv && source .venv/bin/activate

.PHONY: help install fmt lint type test check run api explorer live clean

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  %-14s %s\n", $$1, $$2}'

install:  ## Install the package and dev tools in editable mode
	pip install -e ".[chain,dev]"

fmt:  ## Format the code with ruff
	ruff format src tests

lint:  ## Lint the code with ruff (autofix where safe)
	ruff check --fix src tests

type:  ## Type-check with mypy
	mypy

test:  ## Run the test suite with coverage
	pytest

check: lint type test  ## Run lint, type check, and tests (what CI runs)

run:  ## Follow the chain and index it (available from chapter 09)
	python -m chainidx.follow

api:  ## Start the REST query API locally (available from chapter 13)
	uvicorn --factory chainidx.api:create_default_app --reload

explorer:  ## Serve the block explorer UI (available from chapter 15)
	python -m chainidx.explorer

live:  ## Follow a live chain and serve the live dashboard (available from chapter 16)
	python -m chainidx.live

clean:  ## Remove caches and local databases
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage coverage.xml
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -maxdepth 1 -name "*.db" -delete
