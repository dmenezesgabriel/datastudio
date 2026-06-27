# Data Studio

## Running

**Backend**
```sh
uv run uvicorn chat.infrastructure.api.app:create_app --factory --host 127.0.0.1 --port 8000 --reload
```

**Frontend dev server**
```sh
cd frontend && npm run dev
```

**Frontend build** (required for backend to serve the SPA)
```sh
cd frontend && npm run build
```

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
- https://medium.com/@sathishkraju/the-ai-agentic-workflow-patterns-that-actually-matter-in-2026-08955ac6f398
- https://docs.langchain.com/oss/python/langchain/frontend/generative-ui
- https://docs.langchain.com/oss/python/langgraph/graph-api
