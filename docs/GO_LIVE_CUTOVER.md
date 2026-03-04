# Go-Live Cutover: chat.reilabs.ai + api.reilabs.ai

**Downtime:** None — DNS cutover is gradual; old URLs keep working throughout
**Rollback:** Revert DNS CNAMEs in SiteGround (takes effect within TTL)

---

## Current Status (2026-03-03)

| Task | Status |
|------|--------|
| Redis → Cosmos migration (46 users) | ✅ Done |
| All apps rebuilt with production URLs | ✅ Done |
| `api.reilabs.ai` CNAME + TXT in SiteGround | ✅ Done |
| `api.reilabs.ai` bound to Azure + SSL live | ✅ Done |
| `asuid.chat` TXT in SiteGround | ✅ Done |
| `chat.reilabs.ai` bound to Azure (pending CNAME) | ✅ Done |
| `chat.reilabs.ai` SSL cert — provisioning | ⏳ Needs CNAME to complete |
| `chat` CNAME in SiteGround | ⏳ **You need to add this** |
| Bind `chat.reilabs.ai` SSL cert | ⏳ After CNAME is live |
| Smoke tests | ⏳ Pending |

**One thing left to do in SiteGround:**

| Type | Name | Value | TTL |
|------|------|-------|-----|
| CNAME | `chat` | `ari-web.azurewebsites.net` | 3600 |

---

## Finishing the Cutover (once CNAME is added)

### 1. Verify DNS is live

```bash
dig CNAME chat.reilabs.ai +short
# Should return: ari-web.azurewebsites.net.
```

### 2. Bind the SSL cert

```bash
THUMBPRINT=$(az webapp config ssl list -g rg-ari-prod \
  --query "[?subjectName=='chat.reilabs.ai'].thumbprint" -o tsv)

az webapp config ssl bind \
  --resource-group rg-ari-prod \
  --name ari-web \
  --certificate-thumbprint "$THUMBPRINT" \
  --ssl-type SNI
```

### 3. Verify HTTPS

```bash
curl -sI https://chat.reilabs.ai | head -5
# Should return HTTP/2 200 or redirect to /login
curl -s https://api.reilabs.ai/health | jq
```

---

## Smoke Tests

Run after restart settles (~60 seconds).

### Auth
- [ ] `https://chat.reilabs.ai` → redirects to login
- [ ] Enter email, receive magic link — URL says `https://chat.reilabs.ai/verify?token=...`
- [ ] Click link → lands back on `https://chat.reilabs.ai` logged in
- [ ] Billing page shows "ARI Elite" (not "ari_elite")

### Chat
- [ ] Send a message — response streams back
- [ ] Buyers query (e.g. "find buyers in Houston TX") — returns results + Excel link
- [ ] Comps query — returns Bricked data or Zillow fallback

### API
- [ ] `https://api.reilabs.ai/health` returns `{"status":"ok"}`

### Stripe
- [ ] `https://chat.reilabs.ai/billing` shows active subscription

---

## Current Production Config

| App | Custom Domain | Old URL (still works) |
|-----|---------------|-----------------------|
| Web | `https://chat.reilabs.ai` | `https://ari-web.azurewebsites.net` |
| API | `https://api.reilabs.ai` | `https://reilabs-ari-api.azurewebsites.net` |
| MCP | (internal only) | `https://reilabs-ari-mcp.azurewebsites.net` |

### Env vars (current)

| App | Var | Value |
|-----|-----|-------|
| `ari-web` | `AUTH_URL` | `https://chat.reilabs.ai` |
| `ari-web` | `NEXT_PUBLIC_API_URL` | `https://api.reilabs.ai` (baked at build) |
| `reilabs-ari-api` | `FRONTEND_URL` | `https://chat.reilabs.ai` |
| `reilabs-ari-api` | `ALLOWED_ORIGINS` | `https://chat.reilabs.ai` |

### Rebuild commands (current)

```bash
# API
cd apps/api && az acr build -r ariprodacr -t ari-api:latest --file Dockerfile .

# MCP
cd apps/mcp && az acr build -r ariprodacr -t ari-mcp:latest --file Dockerfile .

# Web (NEXT_PUBLIC vars are baked in at build time)
cd apps/web && az acr build -r ariprodacr -t ari-web:latest \
  --build-arg NEXT_PUBLIC_API_URL=https://api.reilabs.ai \
  --build-arg NEXT_PUBLIC_APP_URL=https://chat.reilabs.ai \
  --file Dockerfile .
```

---

## Rollback

1. Delete the `CNAME chat → ari-web.azurewebsites.net` record in SiteGround
2. `https://ari-web.azurewebsites.net` continues to work (never taken down)
3. Revert env vars:

```bash
az webapp config appsettings set -g rg-ari-prod -n ari-web \
  --settings AUTH_URL=https://ari-web.azurewebsites.net

az webapp config appsettings set -g rg-ari-prod -n reilabs-ari-api \
  --settings \
  FRONTEND_URL=https://ari-web.azurewebsites.net \
  ALLOWED_ORIGINS=https://ari-web.azurewebsites.net

az webapp restart -g rg-ari-prod -n ari-web
az webapp restart -g rg-ari-prod -n reilabs-ari-api
```

---

## Post-Cutover Cleanup (after 24–48 hrs stable)

- [ ] Update Stripe webhook URL to `https://api.reilabs.ai/webhook/stripe` (optional — old URL still works)
- [ ] Update any marketing links, onboarding emails, docs referencing the old `.azurewebsites.net` URLs
- [ ] Consider a redirect from `ari-web.azurewebsites.net` → `chat.reilabs.ai`

---

## Redis Migration History

| Run | Date | Result |
|-----|------|--------|
| Initial | 2026-02-28 | 41 migrated, 0 errors |
| Re-sync | 2026-03-03 | 5 new (4mario, amxcinc, arelys, quentinbuyshouses, thunderchicken6632) |

To re-run if new Redis subscribers appear:

```bash
cd /Users/joshuaceaser/Development/ari
python3 -c "
import os
from dotenv import load_dotenv
load_dotenv('apps/api/.env', override=False)
os.environ['REDIS_HOST'] = 'ari-production.redis.cache.windows.net'
os.environ['REDIS_PORT'] = '6380'
os.environ['REDIS_PASSWORD'] = '<REDIS_PASSWORD_FROM_ENV>'
import runpy
runpy.run_path('scripts/migrate_redis_to_cosmos.py', run_name='__main__')
"
```
