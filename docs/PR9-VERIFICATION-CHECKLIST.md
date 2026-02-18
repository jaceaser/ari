# PR9 Verification Checklist

## What's Tested Automatically (94 pytest tests — all pass)

These use **mocks** — they verify route logic, not real services:

| Area | Tests | What's Covered |
|------|-------|----------------|
| Magic link send | 5 | Email validation, rate limiting, Cosmos storage, 500 on no Cosmos |
| Magic link verify | 5 | Token validation, JWT issuance, single-use delete, no-auth bypass |
| Billing status | 3 | JWT required, active/inactive/canceled subscriptions |
| Stripe checkout | 2 | JWT required, 500 when Stripe not configured |
| Stripe webhook | 4 | No auth required, no rate limit, signature validation |
| Frontend data (CRUD) | 12 | Auth required, messages/documents/votes/suggestions save/get |
| Sessions + JWT + API auth | 62 | All pre-existing tests still pass |

**Run:** `cd apps/api && python -m pytest tests/ -v`

## What's NOT Tested (requires manual verification)

### Required Environment Variables

```bash
# Backend (.env.local in apps/api)
COSMOS_ENDPOINT=<your-cosmos-endpoint>
COSMOS_KEY=<your-cosmos-key>
COSMOS_DATABASE=<your-database>
JWT_SECRET=<shared-secret-min-32-chars>
FRONTEND_URL=http://localhost:3000

# For magic link email (optional — logs link if not set):
AZURE_COMMUNICATION_ENDPOINT=<connection-string>

# For Stripe (optional — disables billing if not set):
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_ID=price_...

# Frontend (.env.local in apps/web)
NEXT_PUBLIC_API_URL=http://localhost:8000
API_JWT_SECRET=<same as backend JWT_SECRET>
AUTH_SECRET=<random-string>
# Optional:
STRIPE_PRICE_ID=price_...    # enables paywall enforcement
```

---

## Manual Verification Steps

### 1. Magic Link — Dev Mode (no Azure email)

- [ ] Start backend: `cd apps/api && python app.py`
- [ ] Start frontend: `cd apps/web && pnpm dev`
- [ ] Open http://localhost:3000/login
- [ ] Enter any email, click "Send magic link"
- [ ] Check **backend terminal** for log: `Magic link for <email>: http://localhost:3000/auth/verify?token=...`
- [ ] Copy that URL and open in browser
- [ ] Verify: redirects to `/` and you're logged in
- [ ] Copy the same URL and open again → should show "Invalid or expired" error

### 2. Magic Link — With Real Email

- [ ] Set `AZURE_COMMUNICATION_ENDPOINT` in backend env
- [ ] Restart backend
- [ ] Enter your real email at /login
- [ ] Check inbox for email from `DoNotReply@reilabs.ai`
- [ ] Click the link → should authenticate
- [ ] Second send within 60s → should show "wait" message (rate limited)

### 3. Stripe — Billing Status

- [ ] After logging in via magic link, get your JWT from the response or cookies
- [ ] `curl -H "Authorization: Bearer <jwt>" http://localhost:8000/billing/status`
- [ ] Expected: `{"active": false}` for a new user

### 4. Stripe — Checkout Flow

- [ ] Set `STRIPE_SECRET_KEY` and `STRIPE_PRICE_ID` in backend env
- [ ] Restart backend
- [ ] `curl -X POST -H "Authorization: Bearer <jwt>" http://localhost:8000/billing/create-checkout`
- [ ] Expected: `{"url": "https://checkout.stripe.com/c/pay/..."}`
- [ ] Open the URL → Stripe Checkout page loads
- [ ] Use test card: `4242 4242 4242 4242`, any future exp, any CVC
- [ ] After payment: `GET /billing/status` → `{"active": true, "plan": "pro", ...}`

### 5. Stripe — Webhook (via Stripe CLI)

```bash
# Terminal 1: Forward webhooks
brew install stripe/stripe-cli/stripe
stripe login
stripe listen --forward-to http://localhost:8000/webhook/stripe

# Terminal 2: Trigger test event
stripe trigger checkout.session.completed
```

- [ ] Check backend logs: webhook received and processed
- [ ] Check Cosmos DB: user document updated with `subscription_status`

### 6. Frontend — Paywall Enforcement

- [ ] Set `STRIPE_PRICE_ID` in **frontend** env, restart frontend
- [ ] Login as user with no subscription
- [ ] Try sending a chat message → should see paywall/subscribe prompt
- [ ] Remove `STRIPE_PRICE_ID` from frontend env → paywall disabled, chat works

### 7. Frontend — Guest Mode

- [ ] Open http://localhost:3000 in incognito
- [ ] Should auto-login as guest (no login page)
- [ ] Send a message → streaming works
- [ ] Guests should NOT see paywall even if `STRIPE_PRICE_ID` is set

### 8. Frontend — Data Persistence

- [ ] Login as authenticated user
- [ ] Start a new chat, send 2-3 messages
- [ ] Refresh page → chat history should reload
- [ ] Open DevTools → Network tab → look for:
  - `POST /data/messages` (saving)
  - `GET /data/messages/<id>` (loading)

### 9. Standalone Build

```bash
cd apps/web
pnpm build
ls -la .next/standalone/server.js   # should exist
PORT=3000 node .next/standalone/server.js
# Open http://localhost:3000 → should load
```

- [ ] Build succeeds
- [ ] `server.js` exists in `.next/standalone/`
- [ ] Standalone server starts and serves the app

### 10. Backward Compatibility

- [ ] `POST /v1/chat/completions` with API key → streaming works (unchanged)
- [ ] `GET /sessions` with JWT → returns sessions list (unchanged)
- [ ] `GET /health` → `{"status": "ok", ...}` (unchanged)

---

## Automated Script

Run the automated portion (phases 1-6):
```bash
./scripts/manual-verify-pr9.sh
```

This checks all endpoint status codes, auth enforcement, file existence, and config.
The manual items (phases 7+) are printed as a checklist at the end.
