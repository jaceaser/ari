#!/bin/bash
#
# PR9 Verification Script
# Run from repo root: ./scripts/verify-pr9.sh
#
# Checks:
#   1. Static: removed deps are gone, no stale imports
#   2. TypeScript: zero errors
#   3. Backend pytest: all API tests pass (mocked, no Azure/Cosmos needed)
#   4. Frontend build: next build succeeds with output: standalone
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PASS=0
FAIL=0
SKIP=0

green()  { printf "\033[32m%s\033[0m\n" "$*"; }
red()    { printf "\033[31m%s\033[0m\n" "$*"; }
yellow() { printf "\033[33m%s\033[0m\n" "$*"; }
bold()   { printf "\033[1m%s\033[0m\n" "$*"; }

pass() { PASS=$((PASS + 1)); green "  PASS  $1"; }
fail() { FAIL=$((FAIL + 1)); red   "  FAIL  $1"; }
skip() { SKIP=$((SKIP + 1)); yellow "  SKIP  $1"; }

# ============================================================================
bold ""
bold "========================================"
bold " PR9 Verification: Static Analysis"
bold "========================================"
bold ""

# ── 1a. No dead package imports (PR9a removals) ──
echo "--- Checking removed dependencies are not imported ---"

dead_imports=(
  "from resumable-stream"
  "from \"resumable-stream\""
  "from \"redis\""
  "import.*redis"
  "from \"better-sqlite3\""
  "from \"drizzle-orm\""
  "from \"drizzle-kit\""
  "from \"@vercel/analytics\""
  "from \"@vercel/blob\""
  "from \"@vercel/functions\""
  "from \"@vercel/otel\""
  "from.*@/lib/db/queries"
)

for pattern in "${dead_imports[@]}"; do
  # Search only in source files, skip node_modules and build artifacts
  hits=$(grep -rn --include='*.ts' --include='*.tsx' --include='*.js' \
    -E "$pattern" "$REPO_ROOT/apps/web/app" "$REPO_ROOT/apps/web/lib" \
    "$REPO_ROOT/apps/web/components" 2>/dev/null || true)
  if [ -n "$hits" ]; then
    fail "Stale import found: $pattern"
    echo "       $hits" | head -3
  else
    pass "No imports of: $pattern"
  fi
done

# ── 1b. Deleted files are actually gone ──
echo ""
echo "--- Checking deleted files are gone ---"

deleted_files=(
  "apps/web/lib/db/queries.ts"
  "apps/web/lib/db/migrate.ts"
  "apps/web/drizzle.config.ts"
)

for f in "${deleted_files[@]}"; do
  if [ -f "$REPO_ROOT/$f" ]; then
    fail "File should be deleted: $f"
  else
    pass "Deleted: $f"
  fi
done

# ── 1c. New files exist ──
echo ""
echo "--- Checking new files exist ---"

new_files=(
  "apps/web/lib/api-client.ts"
  "apps/web/lib/billing.ts"
  "apps/web/app/(auth)/verify/page.tsx"
  "apps/web/components/paywall.tsx"
  "apps/web/app/billing/page.tsx"
  "apps/web/app/api/billing/create-checkout/route.ts"
  "apps/api/routes/magic_link.py"
  "apps/api/routes/stripe_webhook.py"
  "apps/api/routes/billing.py"
  "apps/api/routes/frontend_data.py"
  "apps/api/startup.sh"
  "apps/mcp/startup.sh"
  "apps/web/startup.sh"
  "scripts/smoke-test.sh"
)

for f in "${new_files[@]}"; do
  if [ -f "$REPO_ROOT/$f" ]; then
    pass "Exists: $f"
  else
    fail "Missing: $f"
  fi
done

# ── 1d. Startup scripts are executable ──
echo ""
echo "--- Checking startup scripts are executable ---"

for f in apps/api/startup.sh apps/mcp/startup.sh apps/web/startup.sh scripts/smoke-test.sh; do
  if [ -x "$REPO_ROOT/$f" ]; then
    pass "Executable: $f"
  else
    fail "Not executable: $f"
  fi
done

# ── 1e. Package.json has no removed deps ──
echo ""
echo "--- Checking package.json dependencies ---"

removed_pkgs=(
  '"better-sqlite3"'
  '"drizzle-orm"'
  '"drizzle-kit"'
  '"redis"'
  '"resumable-stream"'
  '"@vercel/analytics"'
  '"@vercel/blob"'
  '"@vercel/functions"'
  '"@vercel/otel"'
)

pkg_json="$REPO_ROOT/apps/web/package.json"
for pkg in "${removed_pkgs[@]}"; do
  if grep -q "$pkg" "$pkg_json" 2>/dev/null; then
    fail "package.json still has $pkg"
  else
    pass "package.json clean of $pkg"
  fi
done

# ── 1f. next.config has standalone output ──
echo ""
echo "--- Checking next.config.ts ---"

if grep -q 'output.*standalone' "$REPO_ROOT/apps/web/next.config.ts" 2>/dev/null; then
  pass "next.config.ts has output: standalone"
else
  fail "next.config.ts missing output: standalone"
fi

# ── 1g. Requirements.txt has new deps ──
echo ""
echo "--- Checking Python requirements ---"

api_reqs="$REPO_ROOT/apps/api/requirements.txt"
for dep in hypercorn azure-communication-email stripe; do
  if grep -qi "$dep" "$api_reqs" 2>/dev/null; then
    pass "requirements.txt has $dep"
  else
    fail "requirements.txt missing $dep"
  fi
done

# ── 1h. Auth middleware skips magic-link and webhook paths ──
echo ""
echo "--- Checking auth middleware skip paths ---"

auth_file="$REPO_ROOT/apps/api/middleware/auth.py"
if grep -q 'magic-link' "$auth_file" 2>/dev/null; then
  pass "Auth middleware skips magic-link paths"
else
  fail "Auth middleware does not skip magic-link paths"
fi

if grep -q 'webhooks/stripe' "$auth_file" 2>/dev/null; then
  pass "Auth middleware skips webhook path"
else
  fail "Auth middleware does not skip webhook path"
fi

# ── 1i. Rate limiter skips webhook ──
rate_file="$REPO_ROOT/apps/api/middleware/rate_limit.py"
if grep -q 'webhooks/stripe' "$rate_file" 2>/dev/null; then
  pass "Rate limiter skips webhook path"
else
  fail "Rate limiter does not skip webhook path"
fi

# ── 1j. Cookie domain config in auth.ts ──
echo ""
echo "--- Checking cookie domain config ---"

auth_ts="$REPO_ROOT/apps/web/app/(auth)/auth.ts"
if grep -q 'COOKIE_DOMAIN' "$auth_ts" 2>/dev/null; then
  pass "auth.ts reads COOKIE_DOMAIN"
else
  fail "auth.ts missing COOKIE_DOMAIN config"
fi

if grep -q 'magic-link' "$auth_ts" 2>/dev/null; then
  pass "auth.ts has magic-link provider"
else
  fail "auth.ts missing magic-link provider"
fi

# ============================================================================
bold ""
bold "========================================"
bold " PR9 Verification: TypeScript"
bold "========================================"
bold ""

echo "--- Running tsc --noEmit ---"
cd "$REPO_ROOT/apps/web"

ts_output=$(npx tsc --noEmit 2>&1 || true)
ts_errors=$(echo "$ts_output" | grep -c "error TS" 2>/dev/null || echo "0")

if [ "$ts_errors" = "0" ]; then
  pass "TypeScript: zero errors"
else
  fail "TypeScript: $ts_errors error(s)"
  echo "$ts_output" | grep "error TS" | head -10
fi

cd "$REPO_ROOT"

# ============================================================================
bold ""
bold "========================================"
bold " PR9 Verification: Backend pytest"
bold "========================================"
bold ""

echo "--- Running backend tests ---"
cd "$REPO_ROOT/apps/api"

# Check if pytest is available
if python3 -m pytest --version >/dev/null 2>&1; then
  pytest_output=$(python3 -m pytest tests/ -v --tb=short 2>&1 || true)
  pytest_failed=$(echo "$pytest_output" | grep -cE "FAILED|ERROR" 2>/dev/null || echo "0")
  pytest_passed=$(echo "$pytest_output" | grep -oP '\d+ passed' 2>/dev/null || echo "0 passed")

  if [ "$pytest_failed" = "0" ]; then
    pass "Backend pytest: $pytest_passed"
  else
    fail "Backend pytest: $pytest_failed failure(s)"
    echo "$pytest_output" | grep -E "FAILED|ERROR" | head -10
  fi
else
  skip "Backend pytest: pytest not installed"
fi

cd "$REPO_ROOT"

# ============================================================================
bold ""
bold "========================================"
bold " PR9 Verification: Frontend Build"
bold "========================================"
bold ""

echo "--- Running next build (standalone) ---"
echo "    (this may take 1-2 minutes)"
cd "$REPO_ROOT/apps/web"

# We only verify the build succeeds, not run the output
build_output=$(pnpm build 2>&1 || true)

if echo "$build_output" | grep -q "Build error\|Failed to compile\|Module not found"; then
  fail "next build failed"
  echo "$build_output" | grep -E "Build error|Failed to compile|Module not found" | head -5
elif echo "$build_output" | grep -qi "Generating static pages\|Collecting page data\|Route.*Size"; then
  pass "next build succeeded (standalone)"
else
  # Check if .next/standalone was created
  if [ -f "$REPO_ROOT/apps/web/.next/standalone/server.js" ]; then
    pass "next build succeeded (.next/standalone/server.js exists)"
  else
    fail "next build: could not confirm success"
    echo "$build_output" | tail -10
  fi
fi

cd "$REPO_ROOT"

# ============================================================================
bold ""
bold "========================================"
bold " Summary"
bold "========================================"
bold ""

green "  Passed: $PASS"
if [ "$FAIL" -gt 0 ]; then
  red   "  Failed: $FAIL"
fi
if [ "$SKIP" -gt 0 ]; then
  yellow "  Skipped: $SKIP"
fi
bold ""

if [ "$FAIL" -gt 0 ]; then
  red "RESULT: SOME CHECKS FAILED"
  exit 1
else
  green "RESULT: ALL CHECKS PASSED"
fi
