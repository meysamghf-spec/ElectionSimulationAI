# Architecture

```mermaid
flowchart LR
  browser[Browser]
  web[Next.js UI]
  api[FastAPI]
  parser[Prompt interpreter]
  engine[Simulation engine]
  db[(SQLite or PostgreSQL)]

  browser --> web
  web -->|/api/v1 proxy| api
  api --> parser
  api --> engine
  api --> db
  parser -->|optional| llm[OpenAI-compatible API]
```

The browser talks only to the Next.js origin. `frontend/app/api/v1/[...path]/route.ts` forwards requests to `API_INTERNAL_URL` at runtime, so the API address is not baked in at build time.

The interpreter returns an `ElectionSpecification`. Validation rejects inconsistent probabilities, populations, and method combinations instead of repairing them. `app/engine/simulate.py` draws binomial turnout and multinomial ballots with NumPy's PCG64 generator. Summaries, comparisons, and sensitivity reports are computed from those draws.

Persistence uses SQLAlchemy models in `backend/app/db/models.py` and Alembic revision `0001_initial`. Startup runs `upgrade head`. The default URL is `sqlite:///./data/elections.db` relative to the backend working directory. A `postgresql+psycopg://` URL uses PostgreSQL and a connection pool.

Execution is an in-process `ThreadPoolExecutor` with two workers. Cancellation is checked between iterations. This is not a distributed queue.

Charts on the results and comparison pages read fields from the simulation response. They do not contain a built-in election dataset.
