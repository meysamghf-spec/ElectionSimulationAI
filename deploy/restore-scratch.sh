#!/bin/sh
# Restore a dump into a throwaway database, read one catalog row, then drop it.
# This does not replace the live "election" database.
# Usage: deploy/restore-scratch.sh /path/to/election.dump
set -eu

if [ "$#" -ne 1 ]; then
  echo "Usage: deploy/restore-scratch.sh /path/to/election.dump" >&2
  exit 2
fi

DUMP=$1
if [ ! -f "$DUMP" ]; then
  echo "Dump file not found." >&2
  exit 2
fi

ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
cd "$ROOT"

compose() {
  docker compose --profile production exec -T db "$@"
}

compose psql -U election -d postgres -v ON_ERROR_STOP=1 \
  -c "DROP DATABASE IF EXISTS election_restore_check;"
compose psql -U election -d postgres -v ON_ERROR_STOP=1 \
  -c "CREATE DATABASE election_restore_check;"
compose pg_restore -U election -d election_restore_check --no-owner --exit-on-error < "$DUMP"
compose psql -U election -d election_restore_check -v ON_ERROR_STOP=1 \
  -c "SELECT COUNT(*) FROM alembic_version;"
compose psql -U election -d postgres -v ON_ERROR_STOP=1 \
  -c "DROP DATABASE election_restore_check;"

echo "Restore validation finished against election_restore_check. The live election database was not replaced."
