#!/usr/bin/env bash
set -euo pipefail

# delete_user.sh — Delete a user and all their data by email
# Run from /srv/app/unified-backend on the server:
#   bash scripts/delete_user.sh user@example.com

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$APP_DIR"

DC="docker compose -f docker-compose.prod.yml --env-file .env.prod"
PSQL="$DC exec -T db psql -U postgres -d unified_backend"

EMAIL="${1:-}"

if [[ -z "$EMAIL" ]]; then
    echo "Usage: bash scripts/delete_user.sh <email>"
    exit 1
fi

echo "==> Looking up user: $EMAIL"

# Dry-run: show what will be deleted
DRY_RUN=$($PSQL <<SQL
SELECT
    u.id,
    u.name,
    u.email,
    u.is_verified,
    u.created_at,
    (SELECT COUNT(*) FROM analyses        WHERE user_id = u.id) AS analyses,
    (SELECT COUNT(*) FROM email_verifications WHERE user_id = u.id) AS email_verifications,
    (SELECT COUNT(*) FROM password_resets WHERE user_id = u.id) AS password_resets
FROM users u
WHERE u.email = '$EMAIL';
SQL
)

echo "$DRY_RUN"

# Check if user exists
ROW_COUNT=$(echo "$DRY_RUN" | grep -c "^[[:space:]]*[0-9a-f-]\{36\}" || true)
if [[ "$ROW_COUNT" -eq 0 ]]; then
    echo "ERROR: No user found with email '$EMAIL'."
    exit 1
fi

echo ""
echo "WARNING: This will permanently delete the user and all their data"
echo "         (analyses, email verifications, password resets)."
echo "         R2/storage files are NOT removed by this script."
echo ""
read -r -p "Type 'yes' to confirm deletion: " CONFIRM

if [[ "$CONFIRM" != "yes" ]]; then
    echo "Aborted."
    exit 0
fi

echo ""
echo "==> Deleting user '$EMAIL'..."

$PSQL <<SQL
DELETE FROM users WHERE email = '$EMAIL';
SQL

echo "==> Done. User '$EMAIL' and all associated records have been deleted."
