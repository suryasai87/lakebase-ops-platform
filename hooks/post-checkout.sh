#!/usr/bin/env bash
# ----------------------------------------------------------------------------
# post-checkout Git hook — Lakebase branch automation (GAP-037)
#
# Automatically creates or deletes a Lakebase database branch whenever
# a corresponding Git branch is checked out or deleted.
#
# Installation:
#   cp hooks/post-checkout.sh .git/hooks/post-checkout
#   chmod +x .git/hooks/post-checkout
#
# Required environment variables:
#   DATABRICKS_HOST   — Workspace URL
#   DATABRICKS_TOKEN  — PAT or OAuth token
#   LAKEBASE_PROJECT  — Lakebase project ID
#
# Optional:
#   LAKEBASE_SOURCE_BRANCH — Source branch for new branches (default: staging)
#   LAKEBASE_TTL           — TTL in seconds (default: 604800 = 7 days)
#   LAKEBASE_HOOK_ENABLED  — Set to "0" to disable (default: "1")
# ----------------------------------------------------------------------------
set -euo pipefail

# ---- Guard clauses --------------------------------------------------------

# $3 == 1 means branch checkout (not file checkout)
if [ "${3:-0}" != "1" ]; then
    exit 0
fi

# Allow disabling via env var
if [ "${LAKEBASE_HOOK_ENABLED:-1}" = "0" ]; then
    exit 0
fi

# Require Databricks credentials
if [ -z "${DATABRICKS_HOST:-}" ] || [ -z "${DATABRICKS_TOKEN:-}" ]; then
    echo "[lakebase-hook] DATABRICKS_HOST and DATABRICKS_TOKEN must be set. Skipping."
    exit 0
fi

if [ -z "${LAKEBASE_PROJECT:-}" ]; then
    echo "[lakebase-hook] LAKEBASE_PROJECT must be set. Skipping."
    exit 0
fi

# ---- Resolve refs ---------------------------------------------------------

PREV_REF="$1"
NEW_REF="$2"
GIT_BRANCH=$(git symbolic-ref --short HEAD 2>/dev/null || true)
GIT_USER=$(git config user.name 2>/dev/null | tr ' ' '-' | tr '[:upper:]' '[:lower:]' || echo "unknown")

if [ -z "$GIT_BRANCH" ]; then
    # Detached HEAD — nothing to do
    exit 0
fi

SOURCE_BRANCH="${LAKEBASE_SOURCE_BRANCH:-staging}"
TTL="${LAKEBASE_TTL:-604800}"

# Skip main/master/production/staging — these are managed separately
case "$GIT_BRANCH" in
    main|master|production|staging|development)
        exit 0
        ;;
esac

# ---- Sanitize branch name for Lakebase (RFC 1123) -------------------------

LAKEBASE_BRANCH=$(echo "$GIT_BRANCH" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9-]/-/g' | sed 's/--*/-/g' | cut -c1-63)

# ---- Create Lakebase branch -----------------------------------------------

echo "[lakebase-hook] Creating Lakebase branch: $LAKEBASE_BRANCH (from $SOURCE_BRANCH, TTL ${TTL}s)"
echo "[lakebase-hook] Git user: $GIT_USER"

API_URL="${DATABRICKS_HOST}/api/2.0/postgres/projects/${LAKEBASE_PROJECT}/branches"

RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$API_URL" \
    -H "Authorization: Bearer ${DATABRICKS_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{
        \"branch\": {
            \"spec\": {
                \"display_name\": \"${LAKEBASE_BRANCH}\",
                \"parent_branch\": \"projects/${LAKEBASE_PROJECT}/branches/${SOURCE_BRANCH}\"
            }
        },
        \"branch_id\": \"${LAKEBASE_BRANCH}\"
    }" 2>/dev/null || true)

HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')

case "$HTTP_CODE" in
    200|201)
        echo "[lakebase-hook] Branch '$LAKEBASE_BRANCH' created successfully."
        ;;
    409)
        echo "[lakebase-hook] Branch '$LAKEBASE_BRANCH' already exists. Skipping."
        ;;
    *)
        echo "[lakebase-hook] Warning: could not create branch (HTTP $HTTP_CODE). Continuing."
        echo "[lakebase-hook] Response: $BODY"
        ;;
esac

exit 0
