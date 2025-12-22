#!/bin/bash
#
# test_user_sessions.sh - Track who logged in and what sessions they ran
#
# Uses:
#   - v3 API for audit logs (login events) - requires service account key
#   - v2 API for sessions (includes user_id) - requires admin user key
#
# Required:
#   - DEVIN_SERVICE_ACCOUNT_API_KEY (cog_*) - for v3 audit logs
#   - DEVIN_ADMIN_USER_API_KEY (apk_user_*) - for v2 sessions
#   - jq (for JSON parsing)
#
# Usage:
#   export DEVIN_SERVICE_ACCOUNT_API_KEY='cog_...'
#   export DEVIN_ADMIN_USER_API_KEY='apk_user_...'
#   ./test_user_sessions.sh

set -e

# Check dependencies
if ! command -v jq &> /dev/null; then
    echo "ERROR: jq is required. Install with: brew install jq"
    exit 1
fi

# Check env vars
if [[ -z "$DEVIN_SERVICE_ACCOUNT_API_KEY" ]]; then
    echo "ERROR: Set DEVIN_SERVICE_ACCOUNT_API_KEY environment variable"
    exit 1
fi

if [[ -z "$DEVIN_ADMIN_USER_API_KEY" ]]; then
    echo "ERROR: Set DEVIN_ADMIN_USER_API_KEY environment variable"
    exit 1
fi

# API endpoints
API_V3="https://api.devin.ai/v3beta1"
API_V2="https://api.devin.ai/v2"

# Time window: last 2 days
TIME_BEFORE=$(date +%s)
TIME_AFTER=$((TIME_BEFORE - 2*24*60*60))

echo "========================================================================"
echo "User Login & Session Tracker (Shell Version)"
echo "========================================================================"
echo ""
echo "Time window: $(date -r $TIME_AFTER) → $(date -r $TIME_BEFORE)"

# ========== FETCH LOGIN EVENTS (v3 API) ==========
echo ""
echo "[1/2] Fetching login events from v3 audit logs..."

LOGINS=$(curl -s --request GET \
    --url "${API_V3}/enterprise/audit-logs?action=login&time_after=${TIME_AFTER}&time_before=${TIME_BEFORE}&first=200" \
    --header "Authorization: Bearer ${DEVIN_SERVICE_ACCOUNT_API_KEY}")

LOGIN_COUNT=$(echo "$LOGINS" | jq '.items | length')
echo "      Found ${LOGIN_COUNT} login events"

# ========== FETCH SESSIONS (v2 API) ==========
echo ""
echo "[2/2] Fetching sessions from v2 enterprise API..."

SESSIONS=$(curl -s --request GET \
    --url "${API_V2}/enterprise/sessions?limit=200" \
    --header "Authorization: Bearer ${DEVIN_ADMIN_USER_API_KEY}")

SESSION_COUNT=$(echo "$SESSIONS" | jq '.items | length')
echo "      Found ${SESSION_COUNT} sessions"

# ========== DISPLAY RESULTS ==========
echo ""
echo "Correlating logins to sessions..."
echo ""
echo "========================================================================"
echo "LOGIN EVENTS"
echo "========================================================================"

echo "$LOGINS" | jq -r '.items[] | "[\(.created_at | todate)] \(.user_email // "N/A") (user_id: \(.user_id // "N/A"))"' | head -20

echo ""
echo "========================================================================"
echo "SESSIONS BY USER"
echo "========================================================================"

# Get unique user_ids and their sessions
echo "$SESSIONS" | jq -r '
    .items 
    | group_by(.user_id) 
    | .[] 
    | "
👤 User ID: \(.[0].user_id // "unknown")
   Sessions: \(length)
\(.[0:5] | .[] | "   - [\(.status)] \(.title // "N/A" | .[0:50])
     Created: \(.created_at) | ACUs: \(.acus_consumed // 0)")"
'

echo ""
echo "========================================================================"
echo "SUMMARY: Users who logged in and their session counts"
echo "========================================================================"

# Create a summary combining logins and sessions
echo ""
echo "Recent logins:"
echo "$LOGINS" | jq -r '.items | group_by(.user_email) | .[] | "\(.[-1].user_email): \(length) login(s), user_id=\(.[-1].user_id)"'

echo ""
echo "Sessions per user_id:"
echo "$SESSIONS" | jq -r '.items | group_by(.user_id) | .[] | "user_id=\(.[0].user_id): \(length) session(s)"'

echo ""
echo "========================================================================"
echo "Done!"
