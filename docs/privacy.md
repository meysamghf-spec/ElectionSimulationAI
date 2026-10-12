# Privacy and limitations

ElectionSimulationAI is a neutral model of hypothetical elections. It is not a voter file, a targeting tool, or a persuasion system.

## Data the application stores

- Election specifications you submit: titles, candidate names, region names, aggregate counts, and probabilities.
- Monte Carlo summaries derived from those specifications.
- Dataset metadata for an import: filename, size, checksum, row count, and a short validation summary. The raw upload is not kept after parsing.
- Audit events such as created, updated, executed, and deleted.

The application does not ask for individual voter identities, contact details, ballots tied to a person, or demographic profiles of real individuals. Segment fields are aggregate shares inside a region. Do not upload personal data.

## Accounts and access

This version has no user accounts and no per-user ownership. Stored simulations are visible to anyone who can call the API.

Set `API_TOKEN` to require `Authorization: Bearer <token>` on data routes. Health checks stay open for load balancers. The token is a shared deployment secret, not a personal login. Holders of the token can read and delete simulations on that instance.

There is no cookie session. Browser token entry, if you use the settings page, is stored in local storage for that browser.

## Results are not official

Simulation output is hypothetical even when you import a dataset or set `empirical_data`. The flag only records that you supplied inputs. It does not turn the Monte Carlo output into an official return or an empirical forecast.

## Retention

Delete a simulation from the history page or `DELETE /api/v1/simulations/{id}` when it is not running. Deleting the database volume removes the remaining records. The application does not phone home.

## Limits of the model

See the methodology document. Independence, clipped turnout shocks, partial rankings, and inferred preferences are modeling choices. They are disclosed with each run. They are not hidden corrections of your inputs.
