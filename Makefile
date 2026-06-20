init:
	pip install -e ".[dev]"

test:
	pytest tests/ -v

lint:
	ruff check gitplot/ tests/

format:
	ruff format gitplot/ tests/

.PHONY: init test lint format
