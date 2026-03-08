#!/usr/bin/env bash
# brain_sync.sh — Rotating backup of SQLite database for claude-brain.
#
# Rotation: max 2 copies. .bak2 deleted, .bak1 renamed to .bak2, new copy to .bak1.
# Verifies backup with sqlite3 integrity_check if available.
#
# Usage:  bash brain_sync.sh
# Exit codes: 0 = success, 1 = failure

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOSTNAME=$(hostname)
LOG_DIR="${ROOT}/logs/${HOSTNAME}"
LOG_FILE="${LOG_DIR}/brain_sync.log"

# Source: read DB path from config.yaml
CONFIG_FILE="${ROOT}/config.yaml"
if [ -f "${CONFIG_FILE}" ]; then
    DB_SOURCE=$(python3 -c "
import yaml
with open('${CONFIG_FILE}') as f:
    c = yaml.safe_load(f)
mode = c.get('storage', {}).get('mode', 'local')
if mode == 'synced':
    print(c['storage']['local_db_path'])
else:
    import os
    print(os.path.join(c['storage']['root_path'], 'claude-brain.db'))
" 2>/dev/null)
else
    echo "Error: config.yaml not found at ${CONFIG_FILE}" >&2
    exit 1
fi
BACKUP_DIR="${ROOT}/db-backup"
DB_NAME="$(basename "${DB_SOURCE}")"
BAK1="${BACKUP_DIR}/${DB_NAME}.bak1"
BAK2="${BACKUP_DIR}/${DB_NAME}.bak2"

# Ensure directories exist
mkdir -p "${LOG_DIR}"
mkdir -p "${BACKUP_DIR}"

log() {
    local level="$1"
    shift
    local msg="$*"
    local ts
    ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    echo "${ts} [${level}] ${msg}" >> "${LOG_FILE}"
    if [ "${level}" = "ERROR" ]; then
        echo "${ts} [${level}] ${msg}" >&2
    fi
}

# Check source exists
if [ ! -f "${DB_SOURCE}" ]; then
    log "ERROR" "Source database not found: ${DB_SOURCE}"
    echo "Error: Source database not found: ${DB_SOURCE}" >&2
    exit 1
fi

# Rotate backups
if [ -f "${BAK2}" ]; then
    rm -f "${BAK2}"
fi
if [ -f "${BAK1}" ]; then
    mv "${BAK1}" "${BAK2}"
fi

# Copy
cp -p "${DB_SOURCE}" "${BAK1}"

# Verify size > 0
BACKUP_SIZE=$(stat -c%s "${BAK1}" 2>/dev/null || stat -f%z "${BAK1}" 2>/dev/null || echo "0")
if [ "${BACKUP_SIZE}" = "0" ]; then
    log "ERROR" "Backup file is empty: ${BAK1}"
    echo "Error: Backup file is empty" >&2
    exit 1
fi

# Verify integrity if sqlite3 CLI is available
if command -v sqlite3 &>/dev/null; then
    INTEGRITY=$(sqlite3 "${BAK1}" "PRAGMA integrity_check;" 2>&1)
    if [ "${INTEGRITY}" != "ok" ]; then
        log "ERROR" "Integrity check failed: ${INTEGRITY}"
        echo "Error: Integrity check failed" >&2
        exit 1
    fi
    log "INFO" "Integrity check passed"
else
    # Use Python as fallback for integrity check
    INTEGRITY=$(python3 -c "
import sqlite3
conn = sqlite3.connect('${BAK1}')
result = conn.execute('PRAGMA integrity_check;').fetchone()[0]
conn.close()
print(result)
" 2>&1)
    if [ "${INTEGRITY}" != "ok" ]; then
        log "ERROR" "Integrity check failed (python): ${INTEGRITY}"
        echo "Error: Integrity check failed" >&2
        exit 1
    fi
    log "INFO" "Integrity check passed (python fallback)"
fi

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
log "INFO" "Backup complete: ${BAK1} (${BACKUP_SIZE} bytes) at ${TIMESTAMP}"

# Output to stdout
echo "Backup complete: ${BAK1} (${BACKUP_SIZE} bytes) at ${TIMESTAMP}"

exit 0
