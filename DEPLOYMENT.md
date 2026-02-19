# ARI Azure Deployment Guide

## Architecture

```
Internet
  |
  v
Azure App Service (ari-web) — Next.js frontend, port 3000
  |  JWT auth
  v
Azure App Service (ari-api) — Python/Quart API, port 8000
  |  Internal HTTP
  v
Azure App Service (ari-mcp) — Python/Quart MCP tool server, port 8100
  |
  v
Azure Cosmos DB, Blob Storage, OpenAI, AI Search
```

## Prerequisites

- Azure CLI installed (`az login`)
- Node.js 20+ with pnpm
- Python 3.12+

## Step 1: Create Azure Resources

```bash
# Resource group
az group create --name rg-ari-prod --location eastus

# Shared Linux App Service Plan (B2 minimum for 3 apps)
az appservice plan create \
  --name plan-ari-prod \
  --resource-group rg-ari-prod \
  --sku B2 \
  --is-linux

# Frontend (Node.js 20)
az webapp create \
  --name ari-web \
  --resource-group rg-ari-prod \
  --plan plan-ari-prod \
  --runtime "NODE:20-lts"

# API backend (Python 3.12)
az webapp create \
  --name ari-api \
  --resource-group rg-ari-prod \
  --plan plan-ari-prod \
  --runtime "PYTHON:3.12"

# MCP tool server (Python 3.12)
az webapp create \
  --name ari-mcp \
  --resource-group rg-ari-prod \
  --plan plan-ari-prod \
  --runtime "PYTHON:3.12"
```

## Step 2: Configure Startup Commands

```bash
# API — uses apps/api/startup.sh (Hypercorn on port 8000)
az webapp config set --name ari-api \
  --resource-group rg-ari-prod \
  --startup-file startup.sh

# MCP — uses apps/mcp/startup.sh (Hypercorn on port 8100)
az webapp config set --name ari-mcp \
  --resource-group rg-ari-prod \
  --startup-file startup.sh

# MCP listens on 8100, tell App Service to route there
az webapp config appsettings set --name ari-mcp \
  --resource-group rg-ari-prod \
  --settings WEBSITES_PORT=8100
```

## Step 3: Set Environment Variables

### ari-api

Copy all values from `apps/api/.env`. The critical ones:

```bash
az webapp config appsettings set --name ari-api \
  --resource-group rg-ari-prod \
  --settings \
    JWT_SECRET="<must match ari-web>" \
    MCP_BASE_URL="https://ari-mcp.azurewebsites.net" \
    MCP_ENABLED="True" \
    FRONTEND_URL="https://ari-web.azurewebsites.net" \
    ALLOWED_ORIGINS="https://ari-web.azurewebsites.net" \
    AZURE_OPENAI_KEY="<your-key>" \
    AZURE_OPENAI_ENDPOINT="https://rei-labs-ari.openai.azure.com/" \
    AZURE_OPENAI_DEPLOYMENT="gpt-5.2-chat" \
    AZURE_OPENAI_API_VERSION="2024-12-01-preview" \
    AZURE_COSMOSDB_ACCOUNT="db-uc-ai" \
    AZURE_COSMOSDB_ACCOUNT_KEY="<your-key>" \
    AZURE_COSMOSDB_DATABASE="db_conversation_history" \
    AZURE_COSMOSDB_SESSIONS_CONTAINER="sessions" \
    AZURE_BLOB_ACCOUNT_NAME="reilabsexternalstorage" \
    AZURE_BLOB_ACCOUNT_KEY="<your-key>" \
    AZURE_BLOB_CUSTOM_DOMAIN="data.reilabs.ai" \
    AZURE_SEARCH_SERVICE="uc-ai-search" \
    AZURE_SEARCH_KEY="<your-key>" \
    AZURE_SEARCH_INDEX="uc-ai-kb-index" \
    STRIPE_SECRET_KEY="<your-key>" \
    STRIPE_WEBHOOK_SECRET="<your-key>"
```

Plus all the system message env vars (`AZURE_OPENAI_SYSTEM_MESSAGE`, `AZURE_OPENAI_BUYERS_SYSTEM_MESSAGE`, etc.) from your `.env`.

### ari-mcp

Copy all values from `apps/mcp/.env` (shares many with API):

```bash
az webapp config appsettings set --name ari-mcp \
  --resource-group rg-ari-prod \
  --settings \
    WEBSITES_PORT=8100 \
    AZURE_COSMOSDB_ACCOUNT="db-uc-ai" \
    AZURE_COSMOSDB_ACCOUNT_KEY="<your-key>" \
    AZURE_COSMOSDB_BUYERS_DATABASE="db_buyers" \
    AZURE_COSMOSDB_NATIONWIDE_BUYERS_CONTAINER="nationwide_buyers" \
    AZURE_COSMOSDB_LEADGEN_DATABASE="db_leads_history" \
    AZURE_COSMOSDB_LEADGEN_CONTAINER="lead_gen" \
    AZURE_BLOB_ACCOUNT_NAME="reilabsexternalstorage" \
    AZURE_BLOB_ACCOUNT_KEY="<your-key>" \
    AZURE_SEARCH_SERVICE="uc-ai-search" \
    AZURE_SEARCH_KEY="<your-key>" \
    AZURE_SEARCH_INDEX="uc-ai-kb-index" \
    SCRAPING_BEE_API_KEY="<your-key>" \
    BRICKED_API_KEY="<your-key>"
```

Plus all the system message env vars from your `.env`.

### ari-web

```bash
az webapp config appsettings set --name ari-web \
  --resource-group rg-ari-prod \
  --settings \
    NEXT_PUBLIC_API_URL="https://ari-api.azurewebsites.net" \
    JWT_SECRET="<must match ari-api>" \
    AUTH_SECRET="<your-secret>"
```

## Step 4: Deploy Code

### API

```bash
cd apps/api
zip -r /tmp/api.zip . \
  -x "venv/*" "__pycache__/*" ".env" ".env.local" "*.pyc" ".pytest_cache/*" "tests/*"

az webapp deploy --name ari-api \
  --resource-group rg-ari-prod \
  --src-path /tmp/api.zip --type zip
```

### MCP

```bash
cd apps/mcp
zip -r /tmp/mcp.zip . \
  -x "venv/*" "__pycache__/*" ".env" ".env.local" "*.pyc" ".pytest_cache/*" "tests/*"

az webapp deploy --name ari-mcp \
  --resource-group rg-ari-prod \
  --src-path /tmp/mcp.zip --type zip
```

### Web (build first)

```bash
cd apps/web
pnpm install
pnpm build

# Package the standalone output
cd .next/standalone
cp -r ../.next/static .next/static
cp -r ../../public ./public
zip -r /tmp/web.zip .

az webapp deploy --name ari-web \
  --resource-group rg-ari-prod \
  --src-path /tmp/web.zip --type zip
```

Set the startup command for Next.js standalone:
```bash
az webapp config set --name ari-web \
  --resource-group rg-ari-prod \
  --startup-file "node server.js"
```

## Step 5: Configure Stripe Webhook

In the Stripe Dashboard, add a webhook endpoint:
- URL: `https://ari-api.azurewebsites.net/webhook/stripe`
- Events: `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.payment_succeeded`, `invoice.payment_failed`

## Step 6: Custom Domains (optional)

```bash
# Frontend
az webapp config hostname add \
  --webapp-name ari-web \
  --resource-group rg-ari-prod \
  --hostname app.reilabs.ai

# API
az webapp config hostname add \
  --webapp-name ari-api \
  --resource-group rg-ari-prod \
  --hostname api.reilabs.ai

# Enable managed SSL certificates
az webapp config ssl create \
  --name ari-web \
  --resource-group rg-ari-prod \
  --hostname app.reilabs.ai

az webapp config ssl create \
  --name ari-api \
  --resource-group rg-ari-prod \
  --hostname api.reilabs.ai
```

After custom domains, update env vars:
- `ari-api`: `FRONTEND_URL=https://app.reilabs.ai`, `ALLOWED_ORIGINS=https://app.reilabs.ai`
- `ari-api`: `MCP_BASE_URL=https://ari-mcp.azurewebsites.net` (keep internal, no custom domain needed)
- `ari-web`: `NEXT_PUBLIC_API_URL=https://api.reilabs.ai`

## Viewing Logs

```bash
# Live tail (like running locally)
az webapp log tail --name ari-api --resource-group rg-ari-prod
az webapp log tail --name ari-mcp --resource-group rg-ari-prod
az webapp log tail --name ari-web --resource-group rg-ari-prod

# Or in Azure Portal: App Service > Log stream
```

Enable application logging:
```bash
az webapp log config --name ari-api \
  --resource-group rg-ari-prod \
  --application-logging filesystem \
  --level information

az webapp log config --name ari-mcp \
  --resource-group rg-ari-prod \
  --application-logging filesystem \
  --level information
```

## Redeploying After Code Changes

```bash
# Redeploy API
cd apps/api
zip -r /tmp/api.zip . -x "venv/*" "__pycache__/*" ".env" ".env.local" "*.pyc" ".pytest_cache/*" "tests/*"
az webapp deploy --name ari-api --resource-group rg-ari-prod --src-path /tmp/api.zip --type zip

# Redeploy MCP
cd apps/mcp
zip -r /tmp/mcp.zip . -x "venv/*" "__pycache__/*" ".env" ".env.local" "*.pyc" ".pytest_cache/*" "tests/*"
az webapp deploy --name ari-mcp --resource-group rg-ari-prod --src-path /tmp/mcp.zip --type zip

# Redeploy Web
cd apps/web && pnpm build
cd .next/standalone && cp -r ../.next/static .next/static && cp -r ../../public ./public
zip -r /tmp/web.zip . && az webapp deploy --name ari-web --resource-group rg-ari-prod --src-path /tmp/web.zip --type zip
```

## Azure Services Inventory

| Service | Resource Name | Purpose |
|---------|--------------|---------|
| App Service Plan | `plan-ari-prod` | Hosts all 3 apps (B2 Linux) |
| App Service | `ari-web` | Next.js frontend |
| App Service | `ari-api` | Python API backend |
| App Service | `ari-mcp` | Python MCP tool server |
| Cosmos DB | `db-uc-ai` | Sessions, messages, users, buyers, leads cache |
| Blob Storage | `reilabsexternalstorage` | Document/Excel exports (`data.reilabs.ai`) |
| Azure OpenAI | `rei-labs-ari` | GPT-5.2 chat + GPT-5-mini classification |
| AI Search | `uc-ai-search` | Knowledge base, leads, contracts indices |
| Communication Services | `reilabs-communication-services` | Magic link emails |
| Redis Cache | `ari-production` | Rate limiting (has in-memory fallback) |

## Cosmos DB Databases & Containers

| Database | Container | Partition Key | Data |
|----------|-----------|---------------|------|
| `db_conversation_history` | `sessions` | `/userId` | Chat sessions, messages, users, documents, votes |
| `db_leads_history` | `lead_gen` | — | Cached lead scrape results (24h TTL) |
| `db_buyers` | `nationwide_buyers` | — | Nationwide cash buyer database |

## Blob Storage Containers

| Container | Content | SAS Expiry |
|-----------|---------|------------|
| `documents` | DOCX exports, buyer Excel files | 30 min (DOCX), 9 days (Excel) |
| `leads-test` | Lead/attorney Excel exports | 9 days |

## Troubleshooting

**API returns 401 on chat**: `JWT_SECRET` must match between `ari-web` and `ari-api`.

**MCP tools not working**: Check `MCP_BASE_URL` points to `https://ari-mcp.azurewebsites.net` and that `ari-mcp` is running. Tail `ari-api` logs for `[MCP]` messages.

**Buyers returns educational content**: User needs `subscription_status: "active"` in Cosmos user doc. Check `ari-api` logs for `guest tools` messages.

**"Loading Chats..." spinner stuck**: Check `ari-api` logs for auth errors on `/sessions` endpoint.

**Blob uploads fail**: Verify `AZURE_BLOB_ACCOUNT_NAME` and `AZURE_BLOB_ACCOUNT_KEY` are set on both `ari-api` and `ari-mcp`.
