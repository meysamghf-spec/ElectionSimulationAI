# Deployment

No public URL has been deployed from this repository. The checks below are what the code and the automated tests cover. They are not a claim that a hosted environment has been exercised.

## Modes

| `AUTH_MODE` | Who can read simulations | When to use it |
| --- | --- | --- |
| `development` | Anyone who can reach the API. One shared workspace. | A local machine only. Production startup rejects this mode. |
| `accounts` | The signed-in owner. Other users receive 404 for someone else's id. | A private multi-user deployment behind HTTPS. |
| `private` | Anyone who has the deployment token. One shared workspace. | A single-tenant host where the site itself is the trust boundary. |

`accounts` stores Argon2 password hashes and opaque session ids. The raw session id is only in an HttpOnly cookie. It is not returned in JSON and it is not stored in browser local storage. Changes require an `X-CSRF-Token` header that matches the server-side session. Registration is closed unless `ALLOW_REGISTRATION=true`. There is no email verification and no self-service password reset, so this is not a public-internet identity system.

## Environment

Copy `.env.example` and replace placeholders. Do not commit the filled file.

Production (`ENVIRONMENT=production`) refuses to start unless all of these hold:

- `AUTH_MODE` is `accounts` or `private`.
- `DATABASE_URL` starts with `postgresql`.
- The database password is at least 16 characters and is not a known placeholder (`change-me`, `change-me-local-only`, `password`, `postgres`, `election`, `secret`, `changeme`, `api-token`, `token`, `admin`).
- `CORS_ORIGINS` is a comma-separated list of `https://` origins. `*` is rejected.
- In private mode, `API_TOKEN` is at least 32 characters and is not one of those placeholders.
- In accounts mode, if registration is closed and the user table is empty, `INITIAL_ADMIN_EMAIL` and `INITIAL_ADMIN_PASSWORD` are set. The password must be at least 12 characters.

`ENVIRONMENT=development` and `ENVIRONMENT=test` skip those checks so local work and the test suite keep the open workspace.

The session cookie is marked `Secure` only when `ENVIRONMENT=production`. Browsers will not store it on plain HTTP. Terminate TLS at a reverse proxy and serve the site on HTTPS before treating accounts mode as usable.

## First account

On an empty accounts database, set both variables and start the API once:

```bash
INITIAL_ADMIN_EMAIL=operator@example.com
INITIAL_ADMIN_PASSWORD='replace-with-a-long-passphrase'
```

The log line names the email and tells you to remove `INITIAL_ADMIN_PASSWORD`. A second boot does not reset that password.

To add or reset a password later, from the `backend` directory, without putting the password in the command line:

```bash
CREATE_USER_EMAIL=person@example.com CREATE_USER_PASSWORD='replace-with-a-long-passphrase' \
  python -m app.auth.cli
```

The command applies migrations, then creates the user or replaces the hash and clears the disabled flag. Disabling a user is a database change: set `users.disabled` to true. There is no admin screen for that.

## Local processes

See the root README. The API applies Alembic migrations on startup, including `0002_accounts`. Run them yourself only if you want a migration before the process starts:

```bash
cd backend
alembic upgrade head
```

Downgrade with `alembic downgrade base` only against a database you can discard.

## Docker Compose

```bash
docker compose up --build
```

Services:

- `db`: PostgreSQL 16, volume `pgdata`, health check `pg_isready`
- `api`: FastAPI on port 8000, non-root user, image health check `GET /api/v1/health`
- `web`: Next.js on port 3000, `API_INTERNAL_URL=http://api:8000`

Compose defaults `ENVIRONMENT` to `development` and `POSTGRES_PASSWORD` to `change-me-local-only`. That combination is for a laptop. It will not pass the production checks. Secrets are read from the environment at runtime. The Dockerfiles do not copy `.env`.

For a private Compose host, set at least:

```bash
ENVIRONMENT=production
AUTH_MODE=accounts
POSTGRES_PASSWORD='replace-with-a-long-password'
CORS_ORIGINS=https://sim.example.com
INITIAL_ADMIN_EMAIL=operator@example.com
INITIAL_ADMIN_PASSWORD='replace-with-a-long-passphrase'
ALLOW_REGISTRATION=false
```

Put the site behind HTTPS. Do not publish the API port to the internet if the browser is meant to use the Next.js proxy. In private mode, set the same `API_TOKEN` on `api` and `web`. The web process adds it on the server side. Do not set `NEXT_PUBLIC_API_TOKEN`.

The image build is part of GitHub Actions. This workspace did not run Docker itself during the accounts work.

## PostgreSQL backups

The application does not ship a backup scheduler. For the Compose volume, a consistent copy is:

```bash
docker compose exec db pg_dump -U election -d election -Fc -f /tmp/election.dump
docker compose cp db:/tmp/election.dump ./election.dump
```

Restore into an empty database with `pg_restore`. Stop the API while restoring so it does not write during the load. Managed PostgreSQL should use that provider's backup and point-in-time recovery instead. Test a restore before relying on it. This repository has not executed a dump or restore.

SQLite development data lives in `backend/data/elections.db`. Copy that file only while the API is stopped. It is not the production database.

Switching a database from development to accounts hides rows whose `owner_id` is null. Those rows remain in the table until an operator deletes them. Account-owned rows stay hidden in development mode.

## Monitoring

`GET /api/v1/health` answers before the database. `GET /api/v1/ready` runs `SELECT 1` and returns 503 when the database is down. Responses include `X-Request-ID`. The API logs interrupted jobs and the initial account email. It does not log passwords, session ids, or the API token. There is no metrics endpoint in this version.

A process restart marks queued and running simulations failed with the message `Interrupted by process restart`. Submit the simulation again. Jobs are not resumed, and there is no separate worker queue.

## What was verified

- Production settings that miss a required control raise `RuntimeError` before serving traffic. Covered by unit tests, not by a live production boot.
- Account registration, login, logout, CSRF, cross-user 404s, and Argon2 storage are covered by `backend/tests/test_accounts.py` against SQLite.
- Alembic revision `0002_accounts` runs on startup in those tests. The PostgreSQL round-trip test runs in GitHub Actions when `DATABASE_URL` is set. It was skipped in this workspace because no local PostgreSQL was used for the new tests.
- Dependency audit commands are in the workflow. Re-run them after changing pins. The result at the time of this change is recorded in `docs/security.md`.
