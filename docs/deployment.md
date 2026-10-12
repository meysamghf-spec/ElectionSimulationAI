# Deployment

No public URL has been deployed from this repository. Nothing in this file creates a server, a DNS record, or a certificate. The commands below are what an operator runs on a machine they already control.

Account registration is not suitable for unrestricted public signup until email verification, password recovery, abuse prevention, and appropriate account-management workflows exist. Production startup rejects `ALLOW_REGISTRATION=true`.

## Modes

| `AUTH_MODE` | Who can read simulations | When to use it |
| --- | --- | --- |
| `development` | Anyone who can reach the API. One shared workspace. | A local machine only. Production startup rejects this mode. |
| `accounts` | The signed-in owner. Other users receive 404 for someone else's id. | A private multi-user deployment behind HTTPS. |
| `private` | Anyone who has the deployment token. One shared workspace. | A single-tenant host where the site itself is the trust boundary. |

`accounts` stores Argon2 password hashes and opaque session ids. The raw session id is only in an HttpOnly cookie. It is not returned in JSON and it is not stored in browser local storage. Changes require an `X-CSRF-Token` header that matches the server-side session. The session cookie is marked `Secure` only when `ENVIRONMENT=production`.

## Production environment

Copy `.env.example` to a file outside Git, or put the variables in the host's secret store. `docker compose` reads a `.env` file next to the Compose file for interpolation. Do not commit that file. Do not set `NEXT_PUBLIC_API_TOKEN` or `NEXT_PUBLIC_API_INTERNAL_URL`.

| Variable | Production value |
| --- | --- |
| `ENVIRONMENT` | `production`. The Compose file sets this on the API. |
| `AUTH_MODE` | `accounts` (the Compose default) or `private`. |
| `ALLOW_REGISTRATION` | `false`. Any other value fails startup. |
| `SITE_ADDRESS` | Bare hostname, such as `sim.example.com`. Not a URL. |
| `ACME_EMAIL` | Address for certificate expiry notices. |
| `CORS_ORIGINS` | Set by Compose to `https://SITE_ADDRESS`. |
| `POSTGRES_PASSWORD` | At least 16 characters. Not a placeholder. Avoid `@`, `:`, `/`, `?`, and `#`. |
| `DATABASE_URL` | Set by Compose to `postgresql+psycopg://election:<password>@db:5432/election`. |
| `TRUSTED_PROXY_CIDRS` | `172.28.10.10/32`. That is the fixed address of the `web` container. |
| `API_INTERNAL_URL` | `http://api:8000` on the `web` container. |
| `INITIAL_ADMIN_EMAIL` | First account. Required on an empty database. |
| `INITIAL_ADMIN_PASSWORD` | First account password, at least 12 characters. Remove it after the first boot. |
| `EXISTING_USERS` | `true` only for the config checker after the first account exists. |
| `API_TOKEN` | Empty in accounts mode. In private mode, at least 32 characters, set on both `api` and `web`. |
| `SESSION_HOURS` | `12` unless you change it. |
| `LLM_API_KEY` | Empty unless you deliberately enable a language-model parser. |

Check the variables before starting. The command prints variable names and failures. It does not print passwords, tokens, or the database URL.

```bash
set -a
. ./.env
set +a
python3 deploy/check_production_env.py
```

`ENVIRONMENT=development` and `ENVIRONMENT=test` skip the production checks so local work and the test suite keep their own settings.

Startup also refuses a known placeholder password: `change-me`, `change-me-local-only`, `password`, `postgres`, `election`, `secret`, `changeme`, `api-token`, `token`, `admin`. The GitHub Actions database password is public in the workflow. Do not reuse it here.

## DNS and firewall

Create these records at the DNS host for `SITE_ADDRESS` before the first boot. This repository does not create them.

- `A` record to the VM's IPv4 address, if the VM has one.
- `AAAA` record to the VM's IPv6 address, if the VM has one.

Open these ports on the VM firewall:

- TCP 22, or whichever port you use for your own SSH. Restrict it to your address.
- TCP 80, so Caddy can answer the HTTP-01 challenge and redirect to HTTPS.
- TCP 443, for the site.

Do not open TCP 8000, TCP 3000, or TCP 5432. The production Compose file does not publish them. PostgreSQL is on the `data` network. The API is on `data` and `internal`. Only Caddy is on the `edge` network and publishes 80 and 443.

Caddy requests a certificate from Let's Encrypt for `SITE_ADDRESS` and stores it in the `caddy_data` volume. There is no certificate in Git.

## Production Compose

From the repository root, with the variables above exported:

```bash
docker compose --profile production up -d --build
```

`docker compose up` without `--profile production` starts nothing. Do not merge `docker-compose.dev.yml` into this command. A file named `docker-compose.override.yml` would be merged automatically; do not add one that publishes 8000 or 5432.

Services:

- `db`: PostgreSQL 16 on the `data` network. No host port. Health check `pg_isready`.
- `api`: FastAPI on the `data` and `internal` networks. No host port. The image health check is `GET /api/v1/health` (process up, database not required). Compose replaces it with `GET /api/v1/ready` (`SELECT 1`) so the web container waits for the database.
- `web`: Next.js at `172.28.10.10` on the `internal` network, also attached to `edge`. No host port. Health check fetches `http://127.0.0.1:3000/`.
- `caddy`: profile `production`. Publishes `80:80` and `443:443`. Reverse-proxies to `web:3000` and replaces `X-Forwarded-For` with the connecting client. Health check requests the admin endpoint on `127.0.0.1:2019` inside the container. That port is not published.

Inspect health:

```bash
docker compose --profile production ps
docker inspect --format '{{.Name}} {{.State.Health.Status}}' \
  $(docker compose --profile production ps -q)
```

`healthy` means the check command exited 0. `starting` means the start period has not elapsed. `unhealthy` means the retries are exhausted.

The public origin is `https://SITE_ADDRESS`. Browsers talk to Caddy. Caddy talks to Next.js. Next.js talks to the API at `http://api:8000`. The API trusts `X-Forwarded-For` only from `172.28.10.10`.

## Local Compose

```bash
docker compose -f docker-compose.dev.yml up --build
```

This publishes `127.0.0.1:3000`, `127.0.0.1:8000`, and `127.0.0.1:5432`. `ENVIRONMENT` defaults to `development`, `AUTH_MODE` defaults to `development`, and `TRUSTED_PROXY_CIDRS` is empty, so a client cannot choose its rate-limit identity by sending `X-Forwarded-For`. Requests that go through the Next.js dev proxy therefore share the proxy's address. That is acceptable on one laptop. It is not the production behavior.

The placeholder database password `change-me-local-only` is rejected when `ENVIRONMENT=production`.

Running the API and Next.js directly, without Docker, is still the path in the root README.

## First account

On an empty accounts database, set both variables and start the API once:

```bash
INITIAL_ADMIN_EMAIL=operator@example.com
INITIAL_ADMIN_PASSWORD='replace-with-a-long-passphrase'
```

The log line names the email and tells you to remove `INITIAL_ADMIN_PASSWORD`. A second boot does not reset that password. After that, the config checker needs `EXISTING_USERS=true` if the password variable is gone.

To add or reset a password later, from the `backend` directory, without putting the password in the command line:

```bash
CREATE_USER_EMAIL=person@example.com CREATE_USER_PASSWORD='replace-with-a-long-passphrase' \
  python -m app.auth.cli
```

Inside the running production stack:

```bash
docker compose --profile production exec -T \
  -e CREATE_USER_EMAIL=person@example.com \
  -e CREATE_USER_PASSWORD \
  api python -m app.auth.cli
```

Type the password into the environment of that command. Do not put it in the shell history if you can avoid it. The command applies migrations, then creates the user or replaces the hash and clears the disabled flag. Disabling a user is a database change: set `users.disabled` to true. There is no admin screen for that.

## Rate limits

`AUTH_RATE_LIMIT_PER_MINUTE` defaults to 10. The general limit defaults to 60 per minute. Both counters live in the API process. They reset on restart and are not shared with another process. Run one API replica.

A direct caller is limited by its TCP address. In production the only trusted TCP peer is the web container. Caddy sets one client IP, and the Next.js proxy forwards that single value. A comma-separated list or an invalid value falls back to the web container's address, so those requests share one bucket. A container other than `web` cannot make the API attribute the limit to an arbitrary client. The database is on a different network and is not in `TRUSTED_PROXY_CIDRS`.

## Backups

Backup and restore steps are in [Backups](backup.md). A dump that stays on the same VM is not a recovery copy. Copy it off the machine.

## Monitoring

`GET /api/v1/health` answers before the database. `GET /api/v1/ready` runs `SELECT 1` and returns 503 when the database is down. From the VM, the public check is:

```bash
curl --fail https://SITE_ADDRESS/api/v1/ready
```

That request goes through Caddy and Next.js. Responses include `X-Request-ID`. The API logs interrupted jobs and the initial account email. It does not log passwords, session ids, or the API token. There is no metrics endpoint in this version.

A process restart marks queued and running simulations failed with the message `Interrupted by process restart`. Submit the simulation again. Jobs are not resumed, and there is no separate worker queue. Cancellation applies only to a job this process has already accepted.

## What was verified

- Production settings that miss a required control raise `RuntimeError` before serving traffic. Covered by unit tests, including open registration, a missing proxy list, and `0.0.0.0/0`.
- The production environment checker rejects missing variables, a public token variable, and a world-wide proxy network without putting secret values in its messages. Covered by unit tests.
- Account registration, login, logout, CSRF, cross-user 404s, Argon2 storage, and auth rate limits are covered by tests against SQLite. The rate-limit tests include an untrusted peer ignoring `X-Forwarded-For` and a trusted peer getting one bucket per single client IP.
- Compose source checks reject a production file that publishes 8000 or 5432. A rendered-config checker covers the same rules. `docker compose --profile production config` was checked locally, and the API, web, and Caddy images were built. Each image became healthy: the API image check is `/api/v1/health`, an exec of `/api/v1/ready` returned 200, the web check fetched `/`, and the Caddy check fetched its local admin endpoint. Those containers were attached to no network and were removed afterward. GitHub Actions repeats the Compose check and the image build.
- The `pg_dump` and scratch-database `pg_restore` commands were run against a local PostgreSQL 16 container with no published ports. The Compose wrapper `deploy/restore-scratch.sh` and the systemd timer were not started. No dump was copied off a VM, and the production Compose project was not started.
