# Troubleshooting

## The page says the API is not reachable

Start the backend from the `backend` directory on port 8000, or set `API_INTERNAL_URL` to the address the Next.js server can use. Inside Compose that address is `http://api:8000`, not `localhost`.

## Ready check returns 503

The database URL is wrong, the database is down, or the process cannot write `backend/data` for SQLite. `/health` can still be ok.

## A prompt did not use a language model

`LLM_API_KEY` is empty, or the provider failed. The response field `interpreter_mode` is `deterministic` or `deterministic_fallback`. Edit the specification before running. The engine does not treat the prompt text as a result.

## Validation rejected the configuration

Probability totals, blank plus invalid above 1, duplicate ids, plurality with more than one seat, and D'Hondt without seats are rejected on purpose. The editor does not rescale preferences. Change the values and validate again.

## Results are unavailable

`GET /results` returns 409 until status is `completed`. Start the run from the execution page. A restart while a job is queued or running marks it failed with an interruption message. Retry from that page.

## Cancel does nothing before Start

Cancellation applies only after the simulation is queued or running. The button stays disabled until then.

## SQLite versus PostgreSQL

`GET /api/v1/meta` reports `persistence`. `sqlite` means the local file. Set `DATABASE_URL` to PostgreSQL before treating the deployment as production.

## Large iteration counts

`wait: true` stops at 5,000 iterations. The UI always queues and polls. The schema cap is 100,000 and the server setting `MAX_ITERATIONS` defaults to 50,000.
