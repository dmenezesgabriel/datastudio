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
```sh
uv run pytest test/unit/ -q
uv run pytest test/unit/ --cov=src --cov-report=term-missing -q
```

**Eval**
```sh
uv run python scripts/run_eval.py
```

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
