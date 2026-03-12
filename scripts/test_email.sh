#!/usr/bin/env bash
# Usage: bash scripts/test_email.sh [recipient@example.com]
# Sources .env.prod for SMTP credentials and sends 2 test emails.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/../.env.prod"

if [[ ! -f "$ENV_FILE" ]]; then
    echo "ERROR: $ENV_FILE not found. Copy .env.prod.example and fill in SMTP values." >&2
    exit 1
fi

# shellcheck disable=SC1090
set -a; source "$ENV_FILE"; set +a

RECIPIENT="${1:-}"
if [[ -z "$RECIPIENT" ]]; then
    read -rp "Recipient email: " RECIPIENT
fi

if [[ -z "$SMTP_USERNAME" || "$SMTP_PASSWORD" == "CHANGE_ME_APP_PASSWORD" ]]; then
    echo "ERROR: SMTP_USERNAME / SMTP_PASSWORD not configured in .env.prod." >&2
    exit 1
fi

send_email() {
    python3 - <<'PYEOF'
import smtplib, sys, os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

smtp_host = os.environ["SMTP_HOST"]
smtp_port = int(os.environ["SMTP_PORT"])
smtp_user = os.environ["SMTP_USERNAME"]
smtp_pass = os.environ["SMTP_PASSWORD"]
from_name = os.environ.get("SMTP_FROM_NAME", "Shoot Right")
recipient = os.environ["_TEST_RECIPIENT"]
subject   = os.environ["_TEST_SUBJECT"]
html_body = os.environ["_TEST_HTML"]

msg = MIMEMultipart("alternative")
msg["Subject"] = subject
msg["From"]    = f"{from_name} <{smtp_user}>"
msg["To"]      = recipient
msg.attach(MIMEText(html_body, "html"))

try:
    if smtp_port == 465:
        with smtplib.SMTP_SSL(smtp_host, smtp_port) as s:
            s.login(smtp_user, smtp_pass)
            s.sendmail(smtp_user, [recipient], msg.as_string())
    else:
        with smtplib.SMTP(smtp_host, smtp_port) as s:
            s.starttls()
            s.login(smtp_user, smtp_pass)
            s.sendmail(smtp_user, [recipient], msg.as_string())
    print("OK")
except Exception as e:
    print(f"FAIL: {e}", file=sys.stderr)
    sys.exit(1)
PYEOF
}

FRONTEND_URL="${FRONTEND_URL:-https://example.com}"

echo ""
echo "Sending to: $RECIPIENT"
echo "SMTP: ${SMTP_USERNAME}@${SMTP_HOST}:${SMTP_PORT}"
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
