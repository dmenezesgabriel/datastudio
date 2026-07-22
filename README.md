# Data Studio

## Running

**Backend**
```sh
PYTHONPATH=src uv run uvicorn bootstrap:create_app --factory --host 127.0.0.1 --port 8000 --reload
```

**Frontend dev server** (talks to the API via Vite's `/api` proxy)
```sh
cd frontend && npm run dev
```

**Frontend build** (the frontend deploys separately; the backend does not serve it)
```sh
cd frontend && npm run build
```

The frontend is a single-page app with real URLs (`/chat/<id>`, `/artifacts/<id>`), so
whatever serves `dist/` must rewrite unknown paths to `index.html` — otherwise a shared
link or a refresh 404s at the host. Vite's dev server and `vite preview` already do this.

**CLI** (direct graph invocation, no HTTP)
```sh
uv run python main.py -m "your question here"
```

**Tests**

`make test` is the everyday gate — the Python unit suite plus the frontend suite, the
two that run anywhere with no credentials. The `pytest-unit` pre-commit hook runs the
unit suite on every commit that touches Python.

```sh
make test              # unit + frontend (the everyday gate)
make test-unit         # uv run pytest test/unit/ -q
make test-frontend     # npm --prefix frontend test
make test-cov          # unit suite with coverage (fails under 80%)
make arch              # import-linter architecture contracts
```

These need a live LLM key in `.env` (see `.env.example`), so they are opt-in and are
not part of `make test`:

```sh
make test-integration  # pytest test/integration/ -m integration
uv run python scripts/run_eval.py
```

Mutation testing takes minutes — run it deliberately, not on every change:

```sh
make mutmut            # mutmut run, then mutmut results
```

Every static check (ruff, pyright, bandit, vulture, xenon, deptry, import-linter) runs
via pre-commit. Install the hooks once with `uv run pre-commit install`.

## References

- https://arxiv.org/html/2511.10192v1
- https://arxiv.org/html/2509.24403v6
- https://arxiv.org/html/2407.15186v5
- https://arxiv.org/html/2410.01066v2
- https://arxiv.org/html/2501.13594v1
- https://arxiv.org/html/2505.05286v1
- https://medium.com/@ranapratapdey/text2sql-architecture-empowered-by-knowledge-graphs-agentic-framework-and-semantic-memory-7d77fb7eef31
- https://docs.langchain.com/oss/python/langchain/frontend/generative-ui
- https://docs.langchain.com/oss/python/langgraph/graph-api
