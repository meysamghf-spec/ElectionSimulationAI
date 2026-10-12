# Testing

Backend tests live in `backend/tests`. They cover hand-checked plurality, D'Hondt, ranked-choice, and two-round results; zero voters; all-invalid ballots; segment sizes; probability totals; scenario comparison; the deterministic parser; sensitivity; CSV import; formula-injection prefixes on export; API authentication; and the body size limit.

Frontend tests live in `frontend/tests`. They check formatters, placeholder specifications, the configuration editor, navigation, validation errors, and that the results view renders the vote totals passed into it.

## Commands

From `backend`, with the dev requirements installed:

```bash
ruff check app tests
mypy
pytest
```

From `frontend`:

```bash
npm run lint
npm run typecheck
npm test
npm run build
```

`pytest -m postgres` runs only the PostgreSQL migration test. It skips unless `DATABASE_URL` starts with `postgresql`.

## Measured runtime

On 12 October 2026, in this development environment, one plurality simulation of 1,000 iterations, 5 regions, 20,000 eligible voters per region, and 4 candidates finished in 0.059 seconds. The automated test only asserts that the same workload finishes in under 15 seconds. This is one measurement, not a capacity claim for other hardware.
