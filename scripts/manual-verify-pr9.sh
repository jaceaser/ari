#!/bin/bash
#
# PR9 Manual Verification Script
# ================================
# Run this locally to verify all PR9 changes end-to-end.
#
# Prerequisites:
#   - Backend running:   cd apps/api && python app.py    (port 8000)
#   - Frontend running:  cd apps/web && pnpm dev          (port 3000)
#   - Environment vars set (see checklist below)
#
# Usage:
#   ./scripts/manual-verify-pr9.sh [API_URL] [WEB_URL]
#
set -uo pipefail

API="${1:-http://localhost:8000}"
WEB="${2:-http://localhost:3000}"

PASS=0
FAIL=0
WARN=0
MANUAL=0

green()  { printf "\033[32m%s\033[0m\n" "$*"; }
red()    { printf "\033[31m%s\033[0m\n" "$*"; }
yellow() { printf "\033[33m%s\033[0m\n" "$*"; }
bold()   { printf "\033[1m%s\033[0m\n" "$*"; }
cyan()   { printf "\033[36m%s\033[0m\n" "$*"; }

pass()   { PASS=$((PASS + 1)); green "  [PASS]  $1"; }
fail()   { FAIL=$((FAIL + 1)); red   "  [FAIL]  $1"; }
warn()   { WARN=$((WARN + 1)); yellow "  [WARN]  $1"; }
manual() { MANUAL=$((MANUAL + 1)); cyan "  [TODO]  $1"; }

hr() { echo "────────────────────────────────────────────────────"; }

# ============================================================================
bold ""
bold "╔══════════════════════════════════════════════════════╗"
bold "║        PR9 Manual Verification                       ║"
bold "╚══════════════════════════════════════════════════════╝"
bold ""
echo "API: $API"
echo "WEB: $WEB"
echo ""

# ============================================================================
hr
bold "PHASE 1: Service Health"
hr

# Check API is running
api_health=$(curl -s --max-time 5 "$API/health" 2>/dev/null || echo "UNREACHABLE")
if echo "$api_health" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['status']=='ok'" 2>/dev/null; then
  pass "API /health returns ok"
else
  fail "API not reachable at $API/health"
  echo "       Start the backend: cd apps/api && python app.py"
  echo "       Response: $api_health"
fi

# Check root listing includes new endpoints
root_resp=$(curl -s --max-time 5 "$API/" 2>/dev/null || echo "")
for ep in "magic-link" "billing" "webhooks" "data/messages"; do
  if echo "$root_resp" | grep -q "$ep"; then
    pass "Root listing includes $ep"
  else
    warn "Root listing missing $ep (may just need app restart)"
  fi
done

# Check frontend is running
web_status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$WEB/" 2>/dev/null || echo "000")
if [ "$web_status" = "200" ] || [ "$web_status" = "307" ] || [ "$web_status" = "302" ]; then
  pass "Frontend reachable ($web_status)"
else
  fail "Frontend not reachable at $WEB/ (got $web_status)"
  echo "       Start the frontend: cd apps/web && pnpm dev"
fi

# ============================================================================
hr
bold "PHASE 2: Magic Link Auth (PR9c)"
hr

echo ""
echo "  Testing magic link endpoints..."
echo ""

# 2a. Send without email → 400
status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 \
  -X POST -H "Content-Type: application/json" \
  -d '{}' "$API/auth/magic-link/send" 2>/dev/null || echo "000")
if [ "$status" = "400" ]; then
  pass "POST /auth/magic-link/send (no email) → 400"
else
  fail "POST /auth/magic-link/send (no email) → $status (expected 400)"
fi

# 2b. Send with invalid email → 400
status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 \
  -X POST -H "Content-Type: application/json" \
  -d '{"email":"not-valid"}' "$API/auth/magic-link/send" 2>/dev/null || echo "000")
if [ "$status" = "400" ]; then
  pass "POST /auth/magic-link/send (bad email) → 400"
else
  fail "POST /auth/magic-link/send (bad email) → $status (expected 400)"
fi

# 2c. Send with valid email → 200 (if Cosmos configured) or 500 (if not)
send_resp=$(curl -s --max-time 10 \
  -X POST -H "Content-Type: application/json" \
  -d '{"email":"test@example.com"}' "$API/auth/magic-link/send" 2>/dev/null || echo "")
send_status=$(echo "$send_resp" | python3 -c "import sys; print('200')" 2>/dev/null || echo "unknown")
send_http=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 \
  -X POST -H "Content-Type: application/json" \
  -d '{"email":"test-verify@example.com"}' "$API/auth/magic-link/send" 2>/dev/null || echo "000")

if [ "$send_http" = "200" ]; then
  pass "POST /auth/magic-link/send (valid email) → 200"
  echo "       Magic link email sent (check logs for link if no AZURE_COMMUNICATION_ENDPOINT)"
elif [ "$send_http" = "500" ]; then
  warn "POST /auth/magic-link/send → 500 (Cosmos DB likely not configured)"
  echo "       This is expected if COSMOS_ENDPOINT is not set"
else
  fail "POST /auth/magic-link/send → $send_http (expected 200 or 500)"
fi

# 2d. Rate limit: second send to same email → 429
if [ "$send_http" = "200" ]; then
  rate_status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 \
    -X POST -H "Content-Type: application/json" \
    -d '{"email":"test-verify@example.com"}' "$API/auth/magic-link/send" 2>/dev/null || echo "000")
  if [ "$rate_status" = "429" ]; then
    pass "Rate limit: second send to same email → 429"
  else
    warn "Rate limit not triggered ($rate_status) — may have been >60s delay"
  fi
fi

# 2e. Verify without token → 400
status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 \
  -X POST -H "Content-Type: application/json" \
  -d '{}' "$API/auth/magic-link/verify" 2>/dev/null || echo "000")
if [ "$status" = "400" ]; then
  pass "POST /auth/magic-link/verify (no token) → 400"
else
  fail "POST /auth/magic-link/verify (no token) → $status (expected 400)"
fi

# 2f. Verify with fake token → 401
status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 \
  -X POST -H "Content-Type: application/json" \
  -d '{"token":"fake-invalid-token"}' "$API/auth/magic-link/verify" 2>/dev/null || echo "000")
if [ "$status" = "401" ] || [ "$status" = "500" ]; then
  pass "POST /auth/magic-link/verify (bad token) → $status"
else
  fail "POST /auth/magic-link/verify (bad token) → $status (expected 401 or 500)"
fi

# 2g. No JWT required for magic link endpoints
echo ""
echo "  Verifying no JWT required for magic link endpoints..."
for ep in "/auth/magic-link/send" "/auth/magic-link/verify"; do
  body=$(curl -s --max-time 5 \
    -X POST -H "Content-Type: application/json" \
    -d '{}' "$API$ep" 2>/dev/null || echo "")
  if echo "$body" | grep -qi "bearer"; then
    fail "$ep blocked by JWT auth middleware"
  else
    pass "$ep not blocked by JWT middleware"
  fi
done

# ============================================================================
hr
bold "PHASE 3: Stripe Billing (PR9d)"
hr

echo ""

# 3a. Billing status without auth → 401
status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 \
  "$API/billing/status" 2>/dev/null || echo "000")
if [ "$status" = "401" ]; then
  pass "GET /billing/status (no auth) → 401"
else
  fail "GET /billing/status (no auth) → $status (expected 401)"
fi

# 3b. Create checkout without auth → 401
status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 \
  -X POST "$API/billing/create-checkout" 2>/dev/null || echo "000")
if [ "$status" = "401" ]; then
  pass "POST /billing/create-checkout (no auth) → 401"
else
  fail "POST /billing/create-checkout (no auth) → $status (expected 401)"
fi

# 3c. Webhook endpoint (no auth required, no Stripe-Signature → 400 or 500)
status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 \
  -X POST -H "Content-Type: application/json" \
  -d '{"type":"test"}' "$API/webhook/stripe" 2>/dev/null || echo "000")
if [ "$status" = "400" ] || [ "$status" = "500" ]; then
  pass "POST /webhook/stripe (no signature) → $status (expected 400 or 500)"
elif [ "$status" = "401" ]; then
  fail "POST /webhook/stripe blocked by auth middleware (should be exempt)"
elif [ "$status" = "429" ]; then
  fail "POST /webhook/stripe rate limited (should be exempt)"
else
  warn "POST /webhook/stripe → $status (unexpected)"
fi

# 3d. Webhook not rate limited
echo ""
echo "  Testing webhook rate limit exemption (5 rapid requests)..."
all_ok=true
for i in 1 2 3 4 5; do
  s=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 \
    -X POST -H "Content-Type: application/json" \
    -d "{\"type\":\"test_$i\"}" "$API/webhook/stripe" 2>/dev/null || echo "000")
  if [ "$s" = "429" ]; then
    all_ok=false
    break
  fi
done
if $all_ok; then
  pass "Webhook endpoint not rate limited (5 rapid requests OK)"
else
  fail "Webhook endpoint got 429 (should be exempt from rate limiting)"
fi

# ============================================================================
hr
bold "PHASE 4: Frontend Data Endpoints (PR9a)"
hr

echo ""
echo "  These endpoints require JWT. Testing auth enforcement..."
echo ""

data_endpoints=(
  "POST:/data/messages"
  "GET:/data/messages/test-id"
  "GET:/data/messages/count?hours=24"
  "POST:/data/documents"
  "GET:/data/documents/test-id"
  "POST:/data/suggestions"
  "GET:/data/suggestions?documentId=test"
  "POST:/data/votes"
  "GET:/data/votes?chatId=test"
)

for entry in "${data_endpoints[@]}"; do
  method="${entry%%:*}"
  path="${entry#*:}"
  if [ "$method" = "GET" ]; then
    s=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$API$path" 2>/dev/null || echo "000")
  else
    s=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 \
      -X "$method" -H "Content-Type: application/json" \
      -d '{}' "$API$path" 2>/dev/null || echo "000")
  fi
  if [ "$s" = "401" ]; then
    pass "$method $path requires auth (401)"
  else
    fail "$method $path → $s (expected 401 without auth)"
  fi
done

# ============================================================================
hr
bold "PHASE 5: Backward Compatibility"
hr

echo ""

# 5a. /v1/chat/completions still reachable
status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 \
  -X POST -H "Content-Type: application/json" \
  -d '{}' "$API/v1/chat/completions" 2>/dev/null || echo "000")
if [ "$status" = "400" ] || [ "$status" = "401" ]; then
  pass "POST /v1/chat/completions reachable ($status)"
else
  fail "POST /v1/chat/completions → $status (expected 400 or 401)"
fi

# 5b. /sessions requires JWT
status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 \
  "$API/sessions" 2>/dev/null || echo "000")
if [ "$status" = "401" ]; then
  pass "GET /sessions requires JWT (401)"
else
  fail "GET /sessions → $status (expected 401)"
fi

# 5c. /lead-runs requires JWT
status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 \
  "$API/lead-runs" 2>/dev/null || echo "000")
if [ "$status" = "401" ]; then
  pass "GET /lead-runs requires JWT (401)"
else
  fail "GET /lead-runs → $status (expected 401)"
fi

# ============================================================================
hr
bold "PHASE 6: Static File Checks"
hr

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
echo ""

# Check deleted files
for f in "apps/web/lib/db/queries.ts" "apps/web/lib/db/migrate.ts" "apps/web/drizzle.config.ts"; do
  if [ -f "$REPO_ROOT/$f" ]; then
    fail "Should be deleted: $f"
  else
    pass "Deleted: $f"
  fi
done

# Check new files
for f in \
  "apps/api/routes/magic_link.py" \
  "apps/api/routes/billing.py" \
  "apps/api/routes/stripe_webhook.py" \
  "apps/api/routes/frontend_data.py" \
  "apps/api/startup.sh" \
  "apps/web/startup.sh" \
  "apps/web/lib/billing.ts" \
  "apps/web/components/paywall.tsx" \
  "apps/web/app/(auth)/verify/page.tsx" \
  "apps/web/app/billing/page.tsx" \
  "scripts/smoke-test.sh" \
; do
  if [ -f "$REPO_ROOT/$f" ]; then
    pass "Exists: $f"
  else
    fail "Missing: $f"
  fi
done

# Startup scripts executable
for f in apps/api/startup.sh apps/web/startup.sh scripts/smoke-test.sh; do
  if [ -x "$REPO_ROOT/$f" ]; then
    pass "Executable: $f"
  else
    warn "Not executable: $f  (run: chmod +x $f)"
  fi
done

# next.config standalone
if grep -q 'output.*standalone' "$REPO_ROOT/apps/web/next.config.ts" 2>/dev/null; then
  pass "next.config.ts has output: standalone"
else
  fail "next.config.ts missing output: standalone"
fi

# requirements.txt
for dep in hypercorn azure-communication-email stripe; do
  if grep -qi "$dep" "$REPO_ROOT/apps/api/requirements.txt" 2>/dev/null; then
    pass "requirements.txt has $dep"
  else
    fail "requirements.txt missing $dep"
  fi
done

# ============================================================================
hr
bold "PHASE 7: Manual Testing Checklist"
bold "  (items you must verify yourself)"
hr

echo ""
yellow "  The following require manual browser testing or real credentials."
yellow "  Mark each as done after you verify."
echo ""

manual "MAGIC LINK — Full flow with real email"
echo "       1. Open $WEB/login"
echo "       2. Enter your real email address"
echo "       3. Click 'Send magic link'"
echo "       4. Check email inbox for the magic link"
echo "       5. Click the link → should redirect to $WEB/auth/verify?token=..."
echo "       6. Should auto-authenticate and redirect to /"
echo "       7. Try using the link again → should show error (single-use)"
echo ""

manual "MAGIC LINK — Without Azure email (dev mode)"
echo "       1. Make sure AZURE_COMMUNICATION_ENDPOINT is NOT set"
echo "       2. POST to /auth/magic-link/send with a valid email"
echo "       3. Check the API server console logs for 'Magic link for ...: <url>'"
echo "       4. Copy the URL from logs and open in browser"
echo "       5. Should authenticate successfully"
echo ""

manual "STRIPE — Billing status with JWT"
echo "       1. Get a JWT: authenticate via magic link, check browser cookies/storage"
echo "       2. curl -H 'Authorization: Bearer <jwt>' $API/billing/status"
echo "       3. Should return {\"active\": false} for new user"
echo ""

manual "STRIPE — Checkout flow (requires STRIPE_SECRET_KEY + STRIPE_PRICE_ID)"
echo "       1. Set STRIPE_SECRET_KEY and STRIPE_PRICE_ID in backend env"
echo "       2. curl -X POST -H 'Authorization: Bearer <jwt>' $API/billing/create-checkout"
echo "       3. Should return {\"url\": \"https://checkout.stripe.com/...\"}"
echo "       4. Open the URL → Stripe Checkout page should load"
echo "       5. Use test card 4242 4242 4242 4242, any future date, any CVC"
echo "       6. After payment, check /billing/status → should show active"
echo ""

manual "STRIPE — Webhook (requires STRIPE_WEBHOOK_SECRET)"
echo "       1. Install Stripe CLI: brew install stripe/stripe-cli/stripe"
echo "       2. stripe login"
echo "       3. stripe listen --forward-to $API/webhook/stripe"
echo "       4. In another terminal: stripe trigger checkout.session.completed"
echo "       5. Check API logs for webhook processing"
echo "       6. Verify user subscription updated in Cosmos DB"
echo ""

manual "FRONTEND — Chat with subscription enforcement"
echo "       1. Set STRIPE_PRICE_ID in frontend env"
echo "       2. Login as a user with NO subscription"
echo "       3. Try to send a message → should see paywall/subscribe prompt"
echo "       4. Subscribe (or remove STRIPE_PRICE_ID to disable enforcement)"
echo "       5. Try to send a message → should work"
echo ""

manual "FRONTEND — Guest mode still works"
echo "       1. Open $WEB in incognito"
echo "       2. Should auto-login as guest"
echo "       3. Send a message → should stream normally"
echo "       4. Guest users should NOT hit paywall"
echo ""

manual "FRONTEND — Data persistence"
echo "       1. Login as authenticated user"
echo "       2. Start a chat, send a few messages"
echo "       3. Refresh the page → chat history should persist"
echo "       4. Check browser DevTools Network tab:"
echo "          - Messages saved via POST /data/messages"
echo "          - Chat loaded via GET /data/messages/<id>"
echo ""

manual "DEPLOYMENT — Standalone build"
echo "       1. cd apps/web && pnpm build"
echo "       2. Check .next/standalone/server.js exists"
echo "       3. PORT=3000 node .next/standalone/server.js"
echo "       4. Open http://localhost:3000 → should load"
echo ""

# ============================================================================
hr
bold "SUMMARY"
hr

echo ""
green "  Automated Checks Passed:  $PASS"
if [ "$FAIL" -gt 0 ]; then
  red   "  Automated Checks Failed:  $FAIL"
fi
if [ "$WARN" -gt 0 ]; then
  yellow "  Warnings:                 $WARN"
fi
cyan   "  Manual Items Remaining:   $MANUAL"
echo ""

if [ "$FAIL" -gt 0 ]; then
  red "STATUS: SOME AUTOMATED CHECKS FAILED — fix these first"
  exit 1
elif [ "$WARN" -gt 0 ]; then
  yellow "STATUS: All automated checks passed with warnings. $MANUAL manual items to verify."
  exit 0
else
  green "STATUS: All automated checks passed. $MANUAL manual items to verify."
  exit 0
fi
