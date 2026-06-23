#!/usr/bin/env bash
set -e

ARTIFACT="$1"

if [ -z "$ARTIFACT" ] || [ ! -f "$ARTIFACT" ]; then
  echo "Usage: $0 <artifact>" >&2
  exit 1
fi

if ! command -v age >/dev/null 2>&1; then
  echo "Error: 'age' is not installed." >&2
  exit 1
fi

IDENTITY_FILE="${AGE_IDENTITY_FILE:-/srv/clinic/backup-key.txt}"

if [ ! -f "$IDENTITY_FILE" ]; then
  echo "Error: age identity file not found at $IDENTITY_FILE" >&2
  echo "Please place the private key there or set AGE_IDENTITY_FILE" >&2
  exit 1
fi

echo "Restoring from $ARTIFACT into a clean db..."

# Drop and recreate the clinic database to ensure a clean state
docker compose -f "$(dirname "$0")/../docker-compose.yml" exec -T db dropdb -U postgres --if-exists clinic
docker compose -f "$(dirname "$0")/../docker-compose.yml" exec -T db createdb -U postgres clinic

# Restore the dump
age -d -i "$IDENTITY_FILE" "$ARTIFACT" | docker compose -f "$(dirname "$0")/../docker-compose.yml" exec -T db pg_restore -U postgres -d clinic

echo "Restore complete."
