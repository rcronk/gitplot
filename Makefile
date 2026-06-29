init:
	pip install -e ".[dev]"

test:
	pytest tests/ -v

lint:
	ruff check visigit/ tests/

format:
	ruff format visigit/ tests/

.PHONY: init test lint format
