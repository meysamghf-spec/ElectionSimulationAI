# Privacy and limitations

ElectionSimulationAI is a neutral model of hypothetical elections. It is not a voter file, a targeting tool, or a persuasion system.

## Data the application stores

- Election specifications you submit: titles, candidate names, region names, aggregate counts, and probabilities.
- Monte Carlo summaries derived from those specifications.
- Dataset metadata for an import: filename, size, checksum, row count, and a short validation summary. The raw upload is not kept after parsing.
- Audit events such as created, updated, executed, and deleted.

The application does not ask for individual voter identities, contact details, ballots tied to a person, or demographic profiles of real individuals. Segment fields are aggregate shares inside a region. Do not upload personal data.

## Accounts and access

`AUTH_MODE=development` is one shared local workspace. Anyone who can call that API can read its simulations. Do not expose that mode.

`AUTH_MODE=accounts` stores an email and an Argon2 password hash. Simulations, projects, and dataset records are tied to that user. Another signed-in user cannot read or change them. The session id is an HttpOnly cookie. The browser does not keep an API token. There is no email verification and no self-service password reset.

`AUTH_MODE=private` uses one shared deployment token held by the server. Holders of the site share one workspace. Health checks stay open for load balancers.

Rows created in development have no owner. After switching the same database to accounts, those rows are hidden rather than given to the first user.

## Results are not official

Simulation output is hypothetical even when you import a dataset or set `empirical_data`. The flag only records that you supplied inputs. It does not turn the Monte Carlo output into an official return or an empirical forecast.

## Retention

Delete a simulation from the history page or `DELETE /api/v1/simulations/{id}` when it is not running. Deleting the database volume removes the remaining records. The application does not phone home.

## Limits of the model

See the methodology document. Independence, clipped turnout shocks, partial rankings, and inferred preferences are modeling choices. They are disclosed with each run. They are not hidden corrections of your inputs.
