# Security notes

- Specifications, prompts, and uploads are untrusted. The interpreter never executes model text. Imports are parsed as CSV or JSON.
- Pydantic rejects unknown fields. Probabilities outside their ranges and totals that are not 1 fail validation.
- CSV export prefixes text cells that start with `=`, `+`, `-`, `@`, tab, or carriage return so a spreadsheet does not treat them as formulas. Numbers stay numbers.
- Upload names are reduced to a basename. Bodies larger than the configured limit receive HTTP 413.
- Queries go through SQLAlchemy. There is no path that turns a prompt into SQL.
- CORS origins come from `CORS_ORIGINS`. Credentialed CORS is off. The UI does not use a cookie session, so browser calls to the same-origin proxy do not rely on cookie CSRF defenses. If you later add cookies, add a CSRF control with them.
- Optional `API_TOKEN` is compared by SHA-256 digest. It is not a user account. There is no per-simulation owner.
- Secrets are read from the environment. `.env.example` has placeholders only.
- The product stores aggregate inputs. Do not upload personal voter records. There is no targeting or persuasion feature.
- Response headers include `nosniff`, `DENY` framing, `no-referrer`, and `no-store`.

## Dependency audit status

Backend `pip-audit -r backend/requirements.txt` reported no known vulnerabilities after FastAPI 0.143.0, Starlette 1.7.0, and python-multipart 0.0.32.

Frontend `npm audit --omit=dev` reported no production advisories. The full tree still includes an unpatched `braces` advisory through `eslint-config-next` → `fast-glob` → `micromatch`. No fixed `braces` release is available. Those packages are not copied into the production image. `scripts/check_npm_audit.py` fails if any other advisory appears.

Starlette still warns that `httpx` with `starlette.testclient` is deprecated in favor of `httpx2`. Tests use FastAPI's `TestClient`. That warning is not a failed test.
