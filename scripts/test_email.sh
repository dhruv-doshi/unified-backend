#!/usr/bin/env bash
# Usage: bash scripts/test_email.sh [recipient@example.com]
# Sources .env.prod for SendGrid credentials and sends 2 test emails.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/../.env.prod"

if [[ ! -f "$ENV_FILE" ]]; then
    echo "ERROR: $ENV_FILE not found. Copy .env.prod.example and fill in SENDGRID values." >&2
    exit 1
fi

# shellcheck disable=SC1090
set -a; source "$ENV_FILE"; set +a

RECIPIENT="${1:-}"
if [[ -z "$RECIPIENT" ]]; then
    read -rp "Recipient email: " RECIPIENT
fi

if [[ -z "${SENDGRID_API_KEY:-}" || "$SENDGRID_API_KEY" == "CHANGE_ME"* ]]; then
    echo "ERROR: SENDGRID_API_KEY not configured in .env.prod." >&2
    exit 1
fi

if [[ -z "${SENDGRID_FROM_EMAIL:-}" ]]; then
    echo "ERROR: SENDGRID_FROM_EMAIL not configured in .env.prod." >&2
    exit 1
fi

send_email() {
    python3 - <<'PYEOF'
import json, sys, os
from urllib.request import Request, urlopen
from urllib.error import HTTPError

api_key    = os.environ["SENDGRID_API_KEY"]
from_email = os.environ["SENDGRID_FROM_EMAIL"]
from_name  = os.environ.get("SENDGRID_FROM_NAME", "Shoot Right")
recipient  = os.environ["_TEST_RECIPIENT"]
subject    = os.environ["_TEST_SUBJECT"]
html_body  = os.environ["_TEST_HTML"]

payload = json.dumps({
    "personalizations": [{"to": [{"email": recipient}]}],
    "from": {"email": from_email, "name": from_name},
    "subject": subject,
    "content": [{"type": "text/html", "value": html_body}],
}).encode()

req = Request(
    "https://api.sendgrid.com/v3/mail/send",
    data=payload,
    headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    },
    method="POST",
)

try:
    with urlopen(req) as resp:
        pass  # 202 Accepted = success
    print("OK")
except HTTPError as e:
    body = e.read().decode()
    print(f"FAIL ({e.code}): {body}", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"FAIL: {e}", file=sys.stderr)
    sys.exit(1)
PYEOF
}

FRONTEND_URL="${FRONTEND_URL:-https://example.com}"

echo ""
echo "Sending to:  $RECIPIENT"
echo "From:        ${SENDGRID_FROM_EMAIL}"
echo ""

# ── Test 1: verification email ────────────────────────────
export _TEST_RECIPIENT="$RECIPIENT"
export _TEST_SUBJECT="[TEST] Verify your Shoot Right account"
export _TEST_HTML="<h2>Welcome to Shoot Right, Test User!</h2>
<p>This is a test verification email.</p>
<a href=\"${FRONTEND_URL}/verify-email?token=test-token-12345\" style=\"background:#6366f1;color:white;padding:12px 24px;text-decoration:none;border-radius:6px;\">Verify Email</a>
<p>This link expires in 24 hours.</p>"

if send_email > /dev/null; then
    echo "✓ verification email sent"
else
    echo "✗ verification email FAILED"
fi

# ── Test 2: password reset email ─────────────────────────
export _TEST_SUBJECT="[TEST] Reset your Shoot Right password"
export _TEST_HTML="<h2>Password Reset Request</h2>
<p>Hi Test User, this is a test password reset email.</p>
<a href=\"${FRONTEND_URL}/reset-password?token=test-token-67890\" style=\"background:#6366f1;color:white;padding:12px 24px;text-decoration:none;border-radius:6px;\">Reset Password</a>
<p>This link expires in 1 hour.</p>"

if send_email > /dev/null; then
    echo "✓ password reset email sent"
else
    echo "✗ password reset email FAILED"
fi

echo ""
echo "Done. Check $RECIPIENT inbox."
