#!/bin/bash
# PostgreSQL restore script
# Supports both local files and S3 downloads
#
# Usage:
#   ./restore.sh /backups/postgres/taxja_20260314_020000.dump
#   ./restore.sh s3://taxja-backups/postgres/taxja_20260314_020000.dump

set -euo pipefail

if [ $# -ne 1 ]; then
  echo "Usage: $0 <backup_file_or_s3_path>"
  echo ""
  echo "Examples:"
  echo "  $0 /backups/postgres/taxja_20260314_020000.dump"
  echo "  $0 s3://taxja-backups/postgres/taxja_20260314_020000.dump"
  exit 1
fi

SOURCE="$1"
RESTORE_FILE="${SOURCE}"

# Download from S3 if needed
if [[ "${SOURCE}" == s3://* ]]; then
  RESTORE_FILE="/tmp/taxja_restore_$(date +%s).dump"
  echo "Downloading from ${SOURCE}..."

  S3_ARGS=""
  if [ -n "${BACKUP_S3_ENDPOINT:-}" ]; then
    S3_ARGS="--endpoint-url ${BACKUP_S3_ENDPOINT}"
  fi

  aws s3 cp ${S3_ARGS} "${SOURCE}" "${RESTORE_FILE}"
  echo "Downloaded to ${RESTORE_FILE}"
fi

if [ ! -f "${RESTORE_FILE}" ]; then
  echo "ERROR: File not found: ${RESTORE_FILE}" >&2
  exit 1
fi

FILE_SIZE=$(du -h "${RESTORE_FILE}" | cut -f1)
echo ""
echo "============================================"
echo "  WARNING: This will REPLACE all data!"
echo "============================================"
echo "  Source: ${SOURCE}"
echo "  Size:   ${FILE_SIZE}"
echo ""
read -p "Type YES to continue: " CONFIRM

if [ "${CONFIRM}" != "YES" ]; then
  echo "Aborted."
  [ "${SOURCE}" != "${RESTORE_FILE}" ] && rm -f "${RESTORE_FILE}"
  exit 0
fi

echo "Restoring..."

cat "${RESTORE_FILE}" | docker exec -i taxja-postgres pg_restore \
  -U taxja \
  -d taxja \
  --clean \
  --if-exists \
  --single-transaction \
  --verbose 2>&1 | tail -5

echo ""
echo "Restore completed at $(date)"

# Verify row counts
echo ""
echo "Quick verification:"
docker exec taxja-postgres psql -U taxja -d taxja -c "
  SELECT 'users' as table_name, count(*) FROM users
  UNION ALL SELECT 'transactions', count(*) FROM transactions
  UNION ALL SELECT 'documents', count(*) FROM documents
  UNION ALL SELECT 'properties', count(*) FROM properties;
"

# Clean up temp file
[ "${SOURCE}" != "${RESTORE_FILE}" ] && rm -f "${RESTORE_FILE}"
