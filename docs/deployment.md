# Deployment

No public URL has been deployed from this repository.

## Local processes

See the root README. Run Alembic yourself only if you want a migration before the API starts:

```bash
cd backend
alembic upgrade head
```

The API also upgrades on startup. Downgrade with `alembic downgrade base` only against a database you can discard.

## Docker Compose

```bash
docker compose up --build
```

Services:

- `db`: PostgreSQL 16, volume `pgdata`, health check `pg_isready`
- `api`: FastAPI on port 8000, non-root user, `DATABASE_URL` host `db`
- `web`: Next.js on port 3000, `API_INTERNAL_URL=http://api:8000`

Set `POSTGRES_PASSWORD` and `API_TOKEN` in the environment. Do not keep the placeholder password on a shared host. Do not put secrets in the image.

## A hosted path

A compatible layout is a container host for the two app images and a managed PostgreSQL database.

1. Build and push the images from `backend/Dockerfile` and `frontend/Dockerfile`, or run Compose on a single VM.
2. Set `DATABASE_URL` to the managed Postgres URL using the SQLAlchemy driver `postgresql+psycopg://`.
3. Set `API_INTERNAL_URL` on the web service to the API's private address.
4. Set `CORS_ORIGINS` to the public site origin if browsers call the API directly. The bundled UI uses the same-origin proxy and does not need a public API origin.
5. Set `API_TOKEN` if the API port is not private.
6. Leave `LLM_API_KEY` empty until you intend to call a model provider.
7. Confirm `GET /api/v1/ready` returns `{"status":"ok","database":"ok"}` before sending traffic.

Migrations run when the API process starts. The PostgreSQL volume or managed database must outlive the API container.

This document does not record a verified deployment.
