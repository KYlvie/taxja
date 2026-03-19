#!/bin/bash
# PostgreSQL automated backup with cloud storage upload
# Run via cron: 0 2 * * * /opt/taxja/docker/postgres/backup.sh
#
# Environment variables (set in /etc/environment or cron):
#   BACKUP_S3_BUCKET  - S3/MinIO bucket for remote backups (optional)
#   BACKUP_S3_ENDPOINT - S3 endpoint URL (optional, for non-AWS S3)
#   AWS_ACCESS_KEY_ID  - S3 credentials
#   AWS_SECRET_ACCESS_KEY - S3 credentials

set -euo pipefail

BACKUP_DIR="/backups/postgres"
RETENTION_DAYS=30
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/taxja_${TIMESTAMP}.dump"
LOG_FILE="${BACKUP_DIR}/backup.log"

mkdir -p "${BACKUP_DIR}"

log() {
  echo "$(date '+%Y-%m-%d %H:%M:%S') $1" | tee -a "${LOG_FILE}"
}

log "Starting backup..."

# Dump in custom format (compressed, supports parallel restore)
docker exec taxja-postgres pg_dump \
  -U taxja \
  -d taxja \
  --format=custom \
  --compress=9 \
  > "${BACKUP_FILE}" 2>>"${LOG_FILE}"

# Verify backup is not empty
if [ ! -s "${BACKUP_FILE}" ]; then
  log "ERROR: Backup file is empty!"
  rm -f "${BACKUP_FILE}"
  exit 1
fi

BACKUP_SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
log "Local backup completed: ${BACKUP_FILE} (${BACKUP_SIZE})"

# Upload to S3/MinIO if configured
if [ -n "${BACKUP_S3_BUCKET:-}" ]; then
  S3_PATH="s3://${BACKUP_S3_BUCKET}/postgres/taxja_${TIMESTAMP}.dump"

  S3_ARGS=""
  if [ -n "${BACKUP_S3_ENDPOINT:-}" ]; then
    S3_ARGS="--endpoint-url ${BACKUP_S3_ENDPOINT}"
  fi

  if aws s3 cp ${S3_ARGS} "${BACKUP_FILE}" "${S3_PATH}" 2>>"${LOG_FILE}"; then
    log "Uploaded to ${S3_PATH}"

    # Clean remote backups older than retention period
    CUTOFF_DATE=$(date -d "-${RETENTION_DAYS} days" +%Y%m%d 2>/dev/null || date -v-${RETENTION_DAYS}d +%Y%m%d)
    aws s3 ls ${S3_ARGS} "s3://${BACKUP_S3_BUCKET}/postgres/" 2>/dev/null | while read -r line; do
      FILE_DATE=$(echo "$line" | grep -oP 'taxja_\K\d{8}' || true)
      if [ -n "${FILE_DATE}" ] && [ "${FILE_DATE}" -lt "${CUTOFF_DATE}" ]; then
        FILE_NAME=$(echo "$line" | awk '{print $NF}')
        aws s3 rm ${S3_ARGS} "s3://${BACKUP_S3_BUCKET}/postgres/${FILE_NAME}" 2>>"${LOG_FILE}"
        log "Deleted old remote backup: ${FILE_NAME}"
      fi
    done
  else
    log "WARNING: S3 upload failed! Local backup preserved."
  fi
fi

# Clean local backups older than 7 days (keep remote for full retention)
find "${BACKUP_DIR}" -name "taxja_*.dump" -mtime +7 -delete
log "Cleaned local backups older than 7 days"

log "Backup process completed"
