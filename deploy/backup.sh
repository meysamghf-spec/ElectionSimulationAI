#!/bin/sh
# Dump the Compose PostgreSQL database to a local file.
# This does not copy the dump off the VM. Do that as a separate step.
# The database password is not passed on the command line and is not printed.
set -eu

ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
cd "$ROOT"

BACKUP_DIR=${BACKUP_DIR:-/var/backups/electionsim}
mkdir -p "$BACKUP_DIR"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
OUT="$BACKUP_DIR/election-$STAMP.dump"

docker compose --profile production exec -T db \
  pg_dump -U election -d election -Fc > "$OUT"

find "$BACKUP_DIR" -type f -name 'election-*.dump' -mtime +14 -delete

BYTES=$(wc -c < "$OUT" | tr -d ' ')
echo "Wrote election-$STAMP.dump ($BYTES bytes)."
echo "Copy this dump off the VM. A copy that exists only on this disk is not a recovery plan."
