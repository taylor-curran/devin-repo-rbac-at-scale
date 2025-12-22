#!/bin/bash
#
# test_user_sessions.sh - Track who logged in and what sessions they ran by org
#
# Uses:
#   - v3 API for audit logs (login events) and organizations - requires service account key
#   - v2 API for sessions (includes user_id, org_id) - requires admin user key
#
# Required:
#   - DEVIN_SERVICE_ACCOUNT_API_KEY (cog_*) - for v3 audit logs & orgs
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

# Configuration
N_ORGS=${N_ORGS:-4}  # Number of orgs to display (default: 4)

# Time window: last 2 days
TIME_BEFORE=$(date +%s)
TIME_AFTER=$((TIME_BEFORE - 2*24*60*60))

echo "========================================================================"
echo "User Login & Session Tracker by Organization (Top ${N_ORGS})"
echo "========================================================================"
echo ""
echo "Time window: $(date -r $TIME_AFTER) → $(date -r $TIME_BEFORE)"
echo "Showing top ${N_ORGS} organizations by session count"

# ========== FETCH ORGANIZATIONS (v3 API) ==========
echo ""
echo "[1/3] Fetching organizations from v3 API..."

ORGS=$(curl -s --request GET \
    --url "${API_V3}/enterprise/organizations?first=200" \
    --header "Authorization: Bearer ${DEVIN_SERVICE_ACCOUNT_API_KEY}")

ORG_COUNT=$(echo "$ORGS" | jq '.items | length')
echo "      Found ${ORG_COUNT} organizations"

# ========== FETCH LOGIN EVENTS (v3 API) ==========
echo ""
echo "[2/3] Fetching login events from v3 audit logs..."

LOGINS=$(curl -s --request GET \
    --url "${API_V3}/enterprise/audit-logs?action=login&time_after=${TIME_AFTER}&time_before=${TIME_BEFORE}&first=200" \
    --header "Authorization: Bearer ${DEVIN_SERVICE_ACCOUNT_API_KEY}")

LOGIN_COUNT=$(echo "$LOGINS" | jq '.items | length')
echo "      Found ${LOGIN_COUNT} login events"

# ========== FETCH SESSIONS (v2 API) ==========
echo ""
echo "[3/3] Fetching sessions from v2 enterprise API..."

SESSIONS=$(curl -s --request GET \
    --url "${API_V2}/enterprise/sessions?limit=200" \
    --header "Authorization: Bearer ${DEVIN_ADMIN_USER_API_KEY}")

SESSION_COUNT=$(echo "$SESSIONS" | jq '.items | length')
echo "      Found ${SESSION_COUNT} sessions"

# Build org_id -> org_name lookup
ORG_LOOKUP=$(echo "$ORGS" | jq -r '.items | map({(.org_id): .name}) | add')

echo ""
echo "========================================================================"
echo "LOGIN EVENTS (last 20)"
echo "========================================================================"

echo "$LOGINS" | jq -r '.items[:20][] | "[\(.created_at | todate)] \(.user_email // "N/A") (user_id: \(.user_id // "N/A"))"'

echo ""
echo "========================================================================"
echo "SESSIONS BY ORGANIZATION → USER"
echo "========================================================================"

# Group sessions by org_id, then by user_id within each org (limit to N_ORGS)
echo "$SESSIONS" | jq -r --argjson orgs "$ORG_LOOKUP" --argjson n "$N_ORGS" '
    .items 
    | group_by(.org_id) 
    | sort_by(-length)
    | .[:$n]
    | .[]
    | . as $org_sessions
    | ($orgs[.[0].org_id] // .[0].org_id) as $org_name
    | "\n================================================================================\n🏢 Organization: \($org_name)\n   Org ID: \(.[0].org_id)\n   Total Sessions: \(length)\n================================================================================",
    (
        $org_sessions 
        | group_by(.user_id) 
        | sort_by(-length)
        | .[] 
        | "\n  👤 User ID: \(.[0].user_id)\n     Sessions: \(length)",
        (.[0:3][] | "     - [\(.status)] \((.title // "N/A")[0:45])\n       Created: \(.created_at) | ACUs: \(.acus_consumed // 0)")
    )
'

echo ""
echo "========================================================================"
echo "SUMMARY BY ORGANIZATION (Top ${N_ORGS})"
echo "========================================================================"

echo "$SESSIONS" | jq -r --argjson orgs "$ORG_LOOKUP" --argjson n "$N_ORGS" '
    .items 
    | group_by(.org_id) 
    | sort_by(-length)
    | .[:$n]
    | .[] 
    | ($orgs[.[0].org_id] // .[0].org_id) as $org_name
    | "\($org_name): \(length) session(s), \(group_by(.user_id) | length) user(s)"
'

echo ""
echo "========================================================================"
echo "Done!"
