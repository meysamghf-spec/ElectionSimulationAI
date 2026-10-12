# Backups

The production database is the PostgreSQL volume `pgdata` on one VM. The application does not ship a hosted backup product. These steps use `pg_dump` inside the database container. The database password is not placed on the command line. Official PostgreSQL images trust local sockets for the database user, so `pg_dump -U election` from inside the container does not prompt.

Keep dump files out of Git. `.gitignore` ignores `backups/` and `*.dump`.

A backup that exists only on the same disk as the database is not a recovery plan. Copy each dump to storage that is not this VM. That copy is an operator step. This repository does not configure an external backup vendor.

## Manual dump

From the repository root, with the production project running:

```bash
BACKUP_DIR=/var/backups/electionsim ./deploy/backup.sh
```

The script writes `/var/backups/electionsim/election-<UTC timestamp>.dump` in custom format and deletes files in that directory older than 14 days. It then tells you to copy the file off the VM. `BACKUP_DIR` can point somewhere else.

## Daily timer

The unit files assume the checkout lives at `/opt/electionsim`. Change both paths if it does not.

```bash
sudo cp deploy/electionsim-backup.service deploy/electionsim-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now electionsim-backup.timer
systemctl list-timers electionsim-backup.timer
```

The timer fires at 02:30 UTC and runs `deploy/backup.sh`. It does not upload the dump. After it runs, copy the new file off the VM. `journalctl -u electionsim-backup.service` shows the byte count, not the database password.

## Restore validation

`deploy/restore-scratch.sh` loads a dump into a database named `election_restore_check`, reads `alembic_version`, and drops that database. It does not replace the live `election` database.

```bash
./deploy/restore-scratch.sh /var/backups/electionsim/election-TIMESTAMP.dump
```

Stop the API before a restore into the live database, or the API can write during the load. A live restore is a separate decision. The scratch script is the validation procedure.

The same `pg_dump`, `pg_restore`, `SELECT` on `alembic_version`, and `DROP DATABASE` sequence was run once against a local PostgreSQL 16 container that published no host ports. `deploy/restore-scratch.sh` itself was not run, because it targets `docker compose --profile production`, and that project was not started. The systemd timer was not installed. No dump was copied off a VM.

To replace the live database, stop the stack, restore into an empty database you have chosen, and start the stack again. Confirm `GET /api/v1/ready` returns 200 before opening the site to users. Practice that on a copy first.

SQLite files under `backend/data/` are for local development. Copy `elections.db` only while the API is stopped. That file is not the production database.

Switching a database from development to accounts hides rows whose `owner_id` is null. Those rows remain until an operator deletes them.
