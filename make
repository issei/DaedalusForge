PY := python
PIP := pip
VENV := .venv
ACT := . $(VENV)/bin/activate

.PHONY: venv install install-dev lint format typecheck test run clean

venv:
	$(PY) -m venv $(VENV)

install: venv
	$(ACT) && $(PIP) install -U pip && $(PIP) install -r requirements.txt

install-dev: venv
	$(ACT) && $(PIP) install -U pip && $(PIP) install -r requirements-dev.txt && pre-commit install

lint:
	$(ACT) && ruff check .

format:
	$(ACT) && black .

typecheck:
	$(ACT) && mypy .

test:
	$(ACT) && pytest -q

run:
	$(ACT) && $(PY) main.py --process process_config.yaml

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage dist build **/__pycache__
