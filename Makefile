.PHONY: clean test test-unit test-integration test-frontend test-cov mutmut arch

# The everyday gate: everything that runs without a live LLM key.
test: test-unit test-frontend

test-unit:
	uv run pytest test/unit/ -q

test-frontend:
	npm --prefix frontend test

# Hits a real LLM API — needs OPENAI_API_KEY in .env.
test-integration:
	uv run pytest test/integration/ -m integration -q

arch:
	PYTHONPATH=src uv run lint-imports

test-cov:
	uv run pytest test/unit/ --cov=src --cov-report=term-missing -q

# Minutes-long; run it deliberately, not on every change.
mutmut:
	uv run mutmut run
	uv run mutmut results

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
