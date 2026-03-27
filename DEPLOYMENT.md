# ARI Azure Deployment Guide

## Architecture

```
Internet
  |
  v
Azure App Service (web) — Next.js frontend, port 3000
  |  JWT auth
  v
Azure App Service (api) — Python/Quart API, port 8000
  |  Internal HTTP
  v
Azure App Service (mcp) — Python/Quart MCP tool server, port 8100
  |
  v
Azure Cosmos DB, Blob Storage, OpenAI, AI Search
```

All apps run as **Docker containers** pulled from ACR via managed identity.
Never use zip deploy — Oryx interferes with both the Next.js standalone build and Python startup times.

---

## Environments

| | **Production** | **Dev** |
|---|---|---|
| Resource Group | `rg-ari-prod` | `rg-ari-dev` |
| App Service Plan | `plan-ari-prod` (B2 Linux) | `plan-ari-dev` (B1 Linux) |
| Web app | `ari-web` | `ari-web-dev` |
| API app | `reilabs-ari-api` | `ari-api-dev` |
| MCP app | `reilabs-ari-mcp` | `ari-mcp-dev` |
| ACR image — web | `ariprodacr.azurecr.io/ari-web:latest` | `ariprodacr.azurecr.io/ari-web:dev` |
| ACR image — api | `ariprodacr.azurecr.io/ari-api:latest` | `ariprodacr.azurecr.io/ari-api:dev` |
| ACR image — mcp | `ariprodacr.azurecr.io/ari-mcp:latest` | `ariprodacr.azurecr.io/ari-mcp:dev` |
| Cosmos DB | `db-uc-ai` | `db-uc-ai-dev` |
| Stripe | Live keys | Test keys (`sk_test_...`) |
| Web URL | https://chat.reilabs.ai | https://ari-web-dev.azurewebsites.net |
| API URL | https://reilabs-ari-api.azurewebsites.net | https://ari-api-dev.azurewebsites.net |
| MCP URL | https://reilabs-ari-mcp.azurewebsites.net | https://ari-mcp-dev.azurewebsites.net |

Shared across both environments: ACR (`ariprodacr`), Blob Storage, Azure OpenAI, AI Search.

---

## Day-to-day: Rebuild & Deploy

Run these from the relevant `apps/<service>` directory.

### API

```bash
# Production
cd apps/api
az acr build -r ariprodacr -t ari-api:latest .
az webapp restart -g rg-ari-prod -n reilabs-ari-api

# Dev
cd apps/api
az acr build -r ariprodacr -t ari-api:dev .
az webapp restart -g rg-ari-dev -n ari-api-dev
```

### MCP

```bash
# Production
cd apps/mcp
az acr build -r ariprodacr -t ari-mcp:latest .
az webapp restart -g rg-ari-prod -n reilabs-ari-mcp

# Dev
cd apps/mcp
az acr build -r ariprodacr -t ari-mcp:dev .
az webapp restart -g rg-ari-dev -n ari-mcp-dev
```

### Web

The web image must be built with `NEXT_PUBLIC_API_URL` as a build arg (it's baked into the JS bundle).

```bash
# Production
cd apps/web
az acr build -r ariprodacr -t ari-web:latest \
  --build-arg NEXT_PUBLIC_API_URL=https://reilabs-ari-api.azurewebsites.net .
az webapp restart -g rg-ari-prod -n ari-web

# Dev
cd apps/web
az acr build -r ariprodacr -t ari-web:dev \
  --build-arg NEXT_PUBLIC_API_URL=https://ari-api-dev.azurewebsites.net .
az webapp restart -g rg-ari-dev -n ari-web-dev
```

---

## Logs

### Live tail

```bash
# Production
az webapp log tail --name reilabs-ari-api --resource-group rg-ari-prod
az webapp log tail --name reilabs-ari-mcp --resource-group rg-ari-prod
az webapp log tail --name ari-web          --resource-group rg-ari-prod

# Dev
az webapp log tail --name ari-api-dev --resource-group rg-ari-dev
az webapp log tail --name ari-mcp-dev --resource-group rg-ari-dev
az webapp log tail --name ari-web-dev --resource-group rg-ari-dev
```

### Docker container logs (Python stdout)

```bash
# Enable filesystem logging first (one-time per app)
az webapp log config --docker-container-logging filesystem \
  --name reilabs-ari-api --resource-group rg-ari-prod     # or ari-api-dev / rg-ari-dev

# Download logs — look for *_default_docker.log inside the zip
az webapp log download --name reilabs-ari-api --resource-group rg-ari-prod --log-file /tmp/api-logs.zip
```

---

## Environment Variables

Key differences between environments — everything else is the same.

| Variable | Production | Dev |
|---|---|---|
| `FRONTEND_URL` | `https://chat.reilabs.ai` | `https://ari-web-dev.azurewebsites.net` |
| `ALLOWED_ORIGINS` | `https://chat.reilabs.ai` | `https://ari-web-dev.azurewebsites.net` |
| `MCP_BASE_URL` | `https://reilabs-ari-mcp.azurewebsites.net` | `https://ari-mcp-dev.azurewebsites.net` |
| `NEXT_PUBLIC_API_URL` | `https://reilabs-ari-api.azurewebsites.net` | `https://ari-api-dev.azurewebsites.net` |
| `AUTH_URL` | `https://chat.reilabs.ai` | `https://ari-web-dev.azurewebsites.net` |
| `AZURE_COSMOSDB_ACCOUNT` | `db-uc-ai` | `db-uc-ai-dev` |
| `STRIPE_SECRET_KEY` | `sk_live_...` | `sk_test_...` |
| `STRIPE_WEBHOOK_SECRET` | live secret | test secret |
| `ENVIRONMENT` | `production` | `development` |

To update a single variable:
```bash
# Production
az webapp config appsettings set -g rg-ari-prod -n reilabs-ari-api \
  --settings SOME_VAR="new-value"

# Dev
az webapp config appsettings set -g rg-ari-dev -n ari-api-dev \
  --settings SOME_VAR="new-value"
```

To copy all settings from prod to dev (with URL overrides), run the script at `scripts/sync-dev-settings.py`.

---

## Stripe Webhooks

Add webhook endpoints in the Stripe Dashboard pointing to the API `/webhook/stripe` route.

| Environment | Dashboard | Endpoint URL |
|---|---|---|
| Production | [Live mode](https://dashboard.stripe.com/webhooks) | `https://reilabs-ari-api.azurewebsites.net/webhook/stripe` |
| Dev | [Test mode](https://dashboard.stripe.com/test/webhooks) | `https://ari-api-dev.azurewebsites.net/webhook/stripe` |

Events to subscribe: `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.payment_succeeded`, `invoice.payment_failed`

---

## First-Time Setup (new environment)

Only needed when creating a brand-new environment from scratch. The dev environment was created on 2026-03-24 and is already running.

### 1. Create resources

```bash
ENV=dev   # or prod
RG=rg-ari-$ENV
PLAN=plan-ari-$ENV
SKU=B1    # B2 for prod

az group create --name $RG --location eastus
az appservice plan create --name $PLAN --resource-group $RG --sku $SKU --is-linux

# Create 3 container apps
for app in ari-web ari-api ari-mcp; do
  az webapp create --name ${app}-${ENV} --resource-group $RG --plan $PLAN \
    --deployment-container-image-name ariprodacr.azurecr.io/${app}:${ENV}
done
```

### 2. Managed identity for ACR pulls

```bash
ACR_ID=$(az acr show --name ariprodacr --query id -o tsv)

for app in ari-web ari-api ari-mcp; do
  az webapp identity assign --name ${app}-${ENV} --resource-group $RG -o none
  PRINCIPAL=$(az webapp identity show --name ${app}-${ENV} --resource-group $RG \
    --query principalId -o tsv)
  az role assignment create --assignee $PRINCIPAL --role AcrPull --scope $ACR_ID -o none
  az webapp update --name ${app}-${ENV} --resource-group $RG \
    --set siteConfig.acrUseManagedIdentityCreds=true -o none
done
```

### 3. Critical settings (apply before first start)

```bash
# All apps — prevents stale home volume issues
for app in ari-web ari-api ari-mcp; do
  az webapp config appsettings set --name ${app}-${ENV} --resource-group $RG \
    --settings WEBSITES_ENABLE_APP_SERVICE_STORAGE=false -o none
done

# MCP needs a non-default port
az webapp config appsettings set --name ari-mcp-${ENV} --resource-group $RG \
  --settings WEBSITES_PORT=8100 -o none
```

### 4. Copy settings from prod and apply overrides

```bash
python3 scripts/sync-dev-settings.py
```

### 5. Build and push images, then restart

```bash
cd apps/api  && az acr build -r ariprodacr -t ari-api:${ENV} .
cd apps/mcp  && az acr build -r ariprodacr -t ari-mcp:${ENV} .
cd apps/web  && az acr build -r ariprodacr -t ari-web:${ENV} \
  --build-arg NEXT_PUBLIC_API_URL=https://ari-api-${ENV}.azurewebsites.net .

for app in ari-web ari-api ari-mcp; do
  az webapp restart --name ${app}-${ENV} --resource-group $RG
done
```

---

## Azure Services Inventory

| Service | Resource | Purpose |
|---|---|---|
| ACR | `ariprodacr` | Docker image registry (shared prod + dev) |
| App Service Plan (prod) | `plan-ari-prod` | B2 Linux — hosts prod apps |
| App Service Plan (dev) | `plan-ari-dev` | B1 Linux — hosts dev apps |
| Cosmos DB (prod) | `db-uc-ai` | Sessions, messages, users, subscriptions |
| Cosmos DB (dev) | `db-uc-ai-dev` | Dev data (isolated from prod) |
| Blob Storage | `reilabsexternalstorage` | DOCX/Excel exports (`data.reilabs.ai`) |
| Azure OpenAI | `rei-labs-ari` | GPT-5.2 chat + GPT-5-mini classification |
| AI Search | `uc-ai-search` | Knowledge base, leads, contracts indices |
| Communication Services | `reilabs-communication-services` | Magic link emails |

### Cosmos DB Databases & Containers

| Database | Container | Data |
|---|---|---|
| `db_conversation_history` | `sessions` | Chat sessions, messages, users, subscriptions |
| `db_leads_history` | `lead_gen` | Cached lead scrape results (24h TTL) |
| `db_buyers` | `nationwide_buyers` | Nationwide cash buyer database |

### Blob Storage Containers

| Container | Content | SAS Expiry |
|---|---|---|
| `documents` | DOCX exports, buyer Excel files | 30 min (DOCX), 9 days (Excel) |
| `leads-test` | Lead/attorney Excel exports | 9 days |

---

## Troubleshooting

**API returns 401 on chat**
`JWT_SECRET` must match between `ari-web` and `ari-api` (or their dev counterparts).

**MCP tools not working**
Check `MCP_BASE_URL` points to the correct MCP URL for the environment. Tail the API logs for `[MCP]` messages.

**`ModuleNotFoundError` on startup despite package being in image**
`WEBSITES_ENABLE_APP_SERVICE_STORAGE` is `true` — Azure is mounting a stale `/home` volume over the image. Set it to `false` and restart.

**Manage Subscription button stuck on "Redirecting..."**
The API returned an error without a `url` field. Check API logs for the actual error — common causes: `stripe_customer_id` missing from Cosmos user doc, or Stripe Customer Portal not configured in the Stripe Dashboard.

**Magic links going to wrong environment**
`FRONTEND_URL` on the API app controls where magic link emails point. Prod should be `https://chat.reilabs.ai`, dev should be `https://ari-web-dev.azurewebsites.net`.

**Buyers returns educational content**
User needs `subscription_status: "active"` in their Cosmos user doc. Check API logs for `guest tools` messages.

**"Loading Chats..." spinner stuck**
Check API logs for auth errors on the `/sessions` endpoint.

**Blob uploads fail**
Verify `AZURE_BLOB_ACCOUNT_NAME` and `AZURE_BLOB_ACCOUNT_KEY` are set on both the API and MCP apps.
