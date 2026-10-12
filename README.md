# ElectionSimulationAI

Hypothetical election simulation and statistical analysis. A written prompt becomes a validated specification. A Monte Carlo engine produces the numbers. A language model, when configured, only proposes a specification. It never produces vote totals.

Every result is a model output. It is not an official return, a poll, or an empirical forecast.

## What you can do

- Interpret an election description, or edit the specification directly.
- Run plurality, two-round, ranked-choice, or D'Hondt simulations.
- Compare scenarios and run a capped sensitivity sweep.
- Import a regional CSV or a JSON specification.
- Export candidate CSV, regional CSV, JSON, and a PDF built from the computed run.
- Save runs in SQLite for local development or PostgreSQL when `DATABASE_URL` points there.

## Run it locally

Requirements: Python 3.12, Node.js 22, and npm.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cd backend
uvicorn app.main:app --reload --port 8000
```

In another shell:

```bash
cd frontend
npm ci
npm run dev
```

Open http://localhost:3000. The Next.js server proxies `/api/v1` to `API_INTERNAL_URL` (default `http://127.0.0.1:8000`). The API creates `backend/data/elections.db` and applies Alembic migrations on startup.

Interactive API docs: http://localhost:8000/docs.

## Docker

Docker was not available in the environment that produced this repository, so the image build has not been executed here. The Compose file is the intended path:

```bash
docker compose up --build
```

The web container calls the API at `http://api:8000`. PostgreSQL data stays in the `pgdata` volume. The default database password is a local placeholder in `.env.example`. Change `POSTGRES_PASSWORD` before any shared deployment.

## Tests

```bash
cd backend
pip install -r requirements.txt -r requirements-dev.txt
ruff check app tests
mypy
pytest
```

```bash
cd frontend
npm ci
npm run lint
npm run typecheck
npm test
npm run build
```

PostgreSQL tests run when `DATABASE_URL` starts with `postgresql`. Without it, that test is skipped. GitHub Actions starts PostgreSQL 16 and sets the URL.

## Documentation

- [Architecture](docs/architecture.md)
- [API](docs/api.md)
- [Methodology](docs/methodology.md)
- [Examples](docs/examples.md)
- [Testing](docs/testing.md)
- [Deployment](docs/deployment.md)
- [Security](docs/security.md)
- [Privacy and limitations](docs/privacy.md)
- [Troubleshooting](docs/troubleshooting.md)

## Assumptions that affect use

- There are no user accounts. Set `API_TOKEN` if the API is reachable by more than one trusted operator. Everyone who has the token can read the stored simulations.
- SQLite is durable local storage. It is not the production database. Production should set `DATABASE_URL` to PostgreSQL.
- No language-model key is required. Interpretation then stays on the deterministic parser, and the UI says so.
- Long runs use an in-process thread pool, not a separate worker queue. A process restart marks queued or running jobs failed.
- `wait=true` is limited to 5,000 iterations. Larger runs return HTTP 202 and are polled.
