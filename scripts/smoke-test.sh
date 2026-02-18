#!/bin/bash
#
# Smoke test for ARI services.
# Usage: ./scripts/smoke-test.sh [API_URL] [MCP_URL] [WEB_URL]
#
# Defaults to localhost ports.
set -euo pipefail

API_URL="${1:-http://localhost:8000}"
MCP_URL="${2:-http://localhost:8100}"
WEB_URL="${3:-http://localhost:3000}"

PASS=0
FAIL=0

check() {
  local label="$1"
  local url="$2"
  local expected_status="${3:-200}"

  status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$url" 2>/dev/null || echo "000")

  if [ "$status" = "$expected_status" ]; then
    echo "  PASS  $label ($status)"
    PASS=$((PASS + 1))
  else
    echo "  FAIL  $label (got $status, expected $expected_status)"
    FAIL=$((FAIL + 1))
  fi
}

check_json() {
  local label="$1"
  local url="$2"
  local key="$3"

  body=$(curl -s --max-time 10 "$url" 2>/dev/null || echo "")
  if echo "$body" | python3 -c "import sys,json; d=json.load(sys.stdin); assert '$key' in d" 2>/dev/null; then
    echo "  PASS  $label (key '$key' present)"
    PASS=$((PASS + 1))
  else
    echo "  FAIL  $label (key '$key' missing in response)"
    FAIL=$((FAIL + 1))
  fi
}

echo "=== ARI Smoke Tests ==="
echo ""
echo "API: $API_URL"
echo "MCP: $MCP_URL"
echo "WEB: $WEB_URL"
echo ""

# ── API Health ──
echo "--- API Backend ---"
check "GET /health" "$API_URL/health"
check_json "Health response has 'status'" "$API_URL/health" "status"
check "GET / (root)" "$API_URL/"

# ── /v1/chat/completions requires auth — should return 401 when API_KEYS set, or 400 for missing body ──
# We just check it's reachable (not 404/500)
status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 \
  -X POST -H "Content-Type: application/json" \
  -d '{}' "$API_URL/v1/chat/completions" 2>/dev/null || echo "000")
if [ "$status" = "400" ] || [ "$status" = "401" ]; then
  echo "  PASS  POST /v1/chat/completions reachable ($status)"
  PASS=$((PASS + 1))
else
  echo "  FAIL  POST /v1/chat/completions unexpected ($status)"
  FAIL=$((FAIL + 1))
fi

# ── Magic link send (no body → 400) ──
check "POST /auth/magic-link/send (no body)" "$API_URL/auth/magic-link/send" "400"

# ── Magic link verify (no body → 400) ──
status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 \
  -X POST -H "Content-Type: application/json" \
  -d '{}' "$API_URL/auth/magic-link/verify" 2>/dev/null || echo "000")
if [ "$status" = "400" ]; then
  echo "  PASS  POST /auth/magic-link/verify (empty → 400)"
  PASS=$((PASS + 1))
else
  echo "  FAIL  POST /auth/magic-link/verify (got $status, expected 400)"
  FAIL=$((FAIL + 1))
fi

# ── Billing status (no auth → 401) ──
check "GET /billing/status (no auth)" "$API_URL/billing/status" "401"

# ── Stripe webhook (no signature → 400 or 500) ──
status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 \
  -X POST -H "Content-Type: application/json" \
  -d '{"type":"test"}' "$API_URL/webhook/stripe" 2>/dev/null || echo "000")
if [ "$status" = "400" ] || [ "$status" = "500" ]; then
  echo "  PASS  POST /webhook/stripe reachable ($status)"
  PASS=$((PASS + 1))
else
  echo "  FAIL  POST /webhook/stripe unexpected ($status)"
  FAIL=$((FAIL + 1))
fi

echo ""

# ── MCP Health ──
echo "--- MCP Server ---"
check "GET /health" "$MCP_URL/health"

echo ""

# ── Web Frontend ──
echo "--- Web Frontend ---"
check "GET / (homepage)" "$WEB_URL/"

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="

if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
