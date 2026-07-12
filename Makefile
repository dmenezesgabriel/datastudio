.PHONY: clean test-unit test-cov mutmut arch

test-unit:
	uv run pytest test/unit/ -q

arch:
	PYTHONPATH=src uv run lint-imports

test-cov:
	uv run pytest test/unit/ --cov=src --cov-report=term-missing -q

mutmut:
	uv run mutmut run
	uv run mutmut results

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
