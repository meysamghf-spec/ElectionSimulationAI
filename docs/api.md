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

When `API_TOKEN` is set, send `Authorization: Bearer <token>` except for `/health`, `/ready`, `/docs`, `/redoc`, and `/openapi.json`.

Request bodies are limited to `MAX_UPLOAD_BYTES` (default 2,000,000). Interpret, execute, import, and sensitivity routes are rate limited per client address.
