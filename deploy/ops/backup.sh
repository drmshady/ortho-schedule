#!/usr/bin/env bash
set -e

# Load environment variables
if [ -f "$(dirname "$0")/../.env" ]; then
  source "$(dirname "$0")/../.env"
fi

if [ -z "$BACKUP_AGE_RECIPIENT" ] || [ "$BACKUP_AGE_RECIPIENT" = "age1replacewithpublicrecipientkey" ]; then
  echo "Error: BACKUP_AGE_RECIPIENT is missing or invalid in .env" >&2
  exit 1
fi

if ! command -v age >/dev/null 2>&1; then
  echo "Error: 'age' is not installed." >&2
  exit 1
fi

BACKUP_DIR="/srv/clinic/backups"
mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date -u +"%Y%m%dT%H%M%SZ")
ARTIFACT_NAME="clinic-${TIMESTAMP}.dump.age"
ARTIFACT_PATH="${BACKUP_DIR}/${ARTIFACT_NAME}"

echo "Starting backup to ${ARTIFACT_PATH}..."

docker compose -f "$(dirname "$0")/../docker-compose.yml" exec -T db pg_dump -U postgres -Fc clinic | age -r "$BACKUP_AGE_RECIPIENT" > "$ARTIFACT_PATH"

echo "Backup complete: $ARTIFACT_PATH"
