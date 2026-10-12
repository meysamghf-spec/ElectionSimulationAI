# Security notes

- Specifications, prompts, and uploads are untrusted. The interpreter never executes model text. Imports are parsed as CSV or JSON.
- Pydantic rejects unknown fields. Probabilities outside their ranges and totals that are not 1 fail validation.
- CSV export prefixes text cells that start with `=`, `+`, `-`, `@`, tab, or carriage return so a spreadsheet does not treat them as formulas. Numbers stay numbers.
- Upload names are reduced to a basename. Bodies larger than the configured limit receive HTTP 413.
- Queries go through SQLAlchemy. There is no path that turns a prompt into SQL.
- CORS origins come from `CORS_ORIGINS`. Credentialed CORS is on so a browser can call the API directly with the session cookie. Origins stay explicit. Production rejects `*` and non-HTTPS origins.
- `AUTH_MODE=accounts` uses Argon2 password hashes, an HttpOnly `esim_session` cookie, and a server-side CSRF token. The raw session id is not in JSON or local storage. A missing or mismatched `X-CSRF-Token` on a cookie mutation returns 403. Login and registration are rate limited separately from the general API limit. Unknown users and wrong passwords return the same message. A disabled user cannot sign in. Production startup rejects `ALLOW_REGISTRATION=true`. Account registration is not suitable for unrestricted public signup until email verification, password recovery, abuse prevention, and appropriate account-management workflows exist.
- Ownership is checked on the server for reads, updates, deletes, execution, cancellation, exports, comparisons, and imports. A simulation owned by someone else is a 404. `API_TOKEN` does not bypass that check in accounts mode.
- `AUTH_MODE=private` compares `API_TOKEN` by SHA-256 digest. The Next.js proxy can attach that token from its own environment and strips any `Authorization` header sent by the browser. Private mode is one shared workspace.
- `AUTH_MODE=development` is open unless `API_TOKEN` is also set. Production startup rejects it.
- Cancellation signals only a job the current process has already accepted, and only after the simulation is visible to the caller.
- Secrets are read from the environment. `.env.example` has placeholders only. Production startup fails when the database password or private-mode token is missing, short, or a known placeholder. It also fails when `TRUSTED_PROXY_CIDRS` is empty, invalid, or a world-wide network (`0.0.0.0/0`, `::/0`).
- Rate limits are counted in memory in the API process. A restart clears them. A second API process would not share them. Do not run more than one API replica. The key is the TCP peer address, unless that peer is inside `TRUSTED_PROXY_CIDRS` and `X-Forwarded-For` is exactly one IP. The production Compose file trusts only `172.28.10.10/32`, the fixed address of the Next.js container. Caddy replaces `X-Forwarded-For` with the immediate client. The Next.js proxy deletes `X-Forwarded-For`, `X-Real-IP`, and `Forwarded`, then forwards a single IP only. A browser-supplied chain is not a separate client. This is not a distributed limiter.
- The product stores aggregate inputs. Do not upload personal voter records. There is no targeting or persuasion feature.
- Response headers include `nosniff`, `DENY` framing, `no-referrer`, and `no-store`.

## Dependency audit status

Backend `pip-audit -r backend/requirements.txt` reported no known vulnerabilities after FastAPI 0.143.0, Starlette 1.7.0, python-multipart 0.0.32, and argon2-cffi 25.1.0. That audit was run in this workspace after the account changes. It is not a continuous scan.

Frontend `npm audit --omit=dev` reported no production advisories. The full tree still includes an unpatched `braces` advisory through `eslint-config-next` → `fast-glob` → `micromatch`. No fixed `braces` release is available. Those packages are not copied into the production image. `scripts/check_npm_audit.py` fails if any other advisory appears.

Starlette still warns that `httpx` with `starlette.testclient` is deprecated in favor of `httpx2`. Tests use FastAPI's `TestClient`. That warning is not a failed test.
