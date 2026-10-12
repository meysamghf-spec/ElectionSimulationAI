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

Local development binds the API, the site, and PostgreSQL to `127.0.0.1` only:

```bash
docker compose -f docker-compose.dev.yml up --build
```

The production file does not publish those ports. On a VM it starts only with the production profile, and only Caddy listens on ports 80 and 443:

```bash
docker compose --profile production up -d --build
```

That command needs `SITE_ADDRESS`, `ACME_EMAIL`, and `POSTGRES_PASSWORD` in the environment. It does not deploy this repository by itself. The web container calls the API at `http://api:8000` on the Docker network. See [Deployment](docs/deployment.md) and [Backups](docs/backup.md).

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
- [Backups](docs/backup.md)
- [Security](docs/security.md)
- [Privacy and limitations](docs/privacy.md)
- [Troubleshooting](docs/troubleshooting.md)

## Access

Local development uses `AUTH_MODE=development`. That mode is one shared workspace with no login. Do not expose it on a network.

`AUTH_MODE=accounts` gives each user their own simulations. Passwords are stored as Argon2 hashes. The browser gets an HttpOnly session cookie and must send the matching `X-CSRF-Token` on changes. Registration stays closed. Production startup rejects `ALLOW_REGISTRATION=true`. Create the first account with `INITIAL_ADMIN_EMAIL` and `INITIAL_ADMIN_PASSWORD` when the user table is empty, then remove the password from the environment. Later accounts can be created with `CREATE_USER_EMAIL` and `CREATE_USER_PASSWORD` through `python -m app.auth.cli` from the `backend` directory. Account registration is not suitable for unrestricted public signup until email verification, password recovery, abuse prevention, and appropriate account-management workflows exist.

`AUTH_MODE=private` is one shared workspace protected by `API_TOKEN`. The Next.js server can hold that token. The browser does not. Everyone who can open the site shares the same simulations. This is not multi-user isolation.

Neither accounts mode nor private mode has been deployed to a public host from this repository.

## Assumptions that affect use

- SQLite is durable local storage. It is not the production database. Production must set `DATABASE_URL` to PostgreSQL or the process will not start.
- No language-model key is required. Interpretation then stays on the deterministic parser, and the UI says so.
- Long runs use an in-process thread pool, not a separate worker queue. A process restart marks queued or running jobs failed. Cancellation is checked only for a job this process already accepted, and only after the caller is allowed to see that simulation.
- `wait=true` is limited to 5,000 iterations. Larger runs return HTTP 202 and are polled.
