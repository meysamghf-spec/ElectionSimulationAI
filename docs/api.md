# API

Base path: `/api/v1`. Interactive schemas: `/docs`.

Errors use:

```json
{"error": {"code": "validation_error", "message": "...", "details": [{"field": "...", "message": "..."}]}}
```

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Process is up |
| GET | `/ready` | Database accepts a query |
| GET | `/meta` | Limits, persistence label, model configuration, disclaimer |
| GET | `/content/{methodology\|privacy}` | Methodology or privacy markdown |
| GET | `/examples` | Example prompts |
| GET | `/examples/datasets/regions.csv` | Example regional CSV |
| GET | `/imports/schemas` | Import column documentation |
| POST | `/interpret` | Prompt to specification |
| POST | `/simulations/validate` | Validation report |
| POST | `/simulations/preview` | Analytical expectations, not a Monte Carlo run |
| POST | `/simulations` | Create a draft |
| GET | `/simulations?limit&offset` | Paginated list |
| GET | `/simulations/{id}` | Specification, validation, results if completed, audit |
| PATCH | `/simulations/{id}` | Replace a configuration that is not queued or running |
| DELETE | `/simulations/{id}` | Delete a saved simulation |
| POST | `/simulations/{id}/duplicate` | Copy a specification into a new draft |
| POST | `/simulations/{id}/execute` | Queue a run. `wait: true` blocks up to 5,000 iterations |
| POST | `/simulations/{id}/cancel` | Cancel a queued run, or request cancellation of a running one |
| GET | `/simulations/{id}/status` | Status and progress |
| GET | `/simulations/{id}/results` | Computed `SimulationOutput` after completion |
| POST | `/simulations/{id}/compare` | Pairwise comparison of two stored scenarios |
| POST | `/simulations/{id}/sensitivity` | Capped one-at-a-time sweep |
| GET | `/simulations/{id}/export.csv?view=candidates\|regional` | CSV of computed results |
| GET | `/simulations/{id}/export.json` | Specification and results |
| GET | `/simulations/{id}/export.pdf` | PDF report of the computed run |
| GET | `/simulations/{id}/compare.csv?left&right` | Comparison CSV |
| POST | `/imports/csv` | Multipart regional CSV |
| POST | `/imports/json` | JSON specification |
| GET | `/projects` | Project names created with simulations |
| POST | `/auth/register` | Create an account when registration is open, then set the session cookie |
| POST | `/auth/login` | Set the session cookie. Wrong email and wrong password use the same message |
| POST | `/auth/logout` | Revoke the session. Requires the CSRF header |
| GET | `/auth/me` | `{authenticated, email, auth_mode, registration_open, csrf_token}` |

`GET /meta` includes `auth_mode` and `registration_open`. It does not include tokens, password hashes, or the language-model key.

Access depends on `AUTH_MODE`:

- `development`: open, unless `API_TOKEN` is set. A set token is required on data routes and is compared by SHA-256 digest. Public exceptions are `/health`, `/ready`, `/docs`, `/redoc`, and `/openapi.json`.
- `private`: the same token rule. `/auth/login` is not a user system in this mode.
- `accounts`: data and mutation routes require the `esim_session` cookie. Mutations also require `X-CSRF-Token`. Anonymous callers can use health, ready, meta, examples, content, import schemas, login, and registration. A resource owned by another user is HTTP 404.

Login and registration responses include `csrf_token` so the client can echo it. They do not include the session id. The Next.js proxy forwards each `Set-Cookie` header. In private mode it attaches `API_TOKEN` on the server and drops a browser-supplied `Authorization` header.

Request bodies are limited to `MAX_UPLOAD_BYTES` (default 2,000,000). Interpret, execute, import, and sensitivity routes are rate limited per client identity. Login and registration use `AUTH_RATE_LIMIT_PER_MINUTE` (default 10). The identity is the TCP peer unless `TRUSTED_PROXY_CIDRS` contains that peer and `X-Forwarded-For` is a single IP. The limiter is in-process memory, not a shared store. The Next.js proxy forwards that single IP and drops a multi-value or invalid header.
