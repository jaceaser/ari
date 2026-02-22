# ARI MCP Server

Python MCP-style tool server for route-oriented tools inspired by legacy `ChatHandler`.

## Run

```bash
cd apps/mcp
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

Runs on `http://localhost:8100`.

## Smoke Test Script

From `apps/mcp`:

```bash
python3 test_mcp_server.py
```

Options:

- `--skip-live` skips Cosmos/Bricked live checks
- `--strict` fails if live checks return warning statuses
- `--base-url http://localhost:8100` to target another MCP host
- `--skip-assertions` runs transport/shape smoke checks only
- `--show-fail-json` prints response snippets when assertions fail

## Endpoints

- `GET /health`
- `GET /tools`
- `POST /tools/integration-config`
- `POST /tools/classify`
- `POST /tools/education`
- `POST /tools/comps`
- `POST /tools/leads`
- `POST /tools/attorneys`
- `POST /tools/strategy`
- `POST /tools/contracts`
- `POST /tools/buyers`
- `POST /tools/offtopic`
- `POST /tools/build-retrieval-query`
- `POST /tools/infer-lead-type`
- `POST /tools/extract-city-state`
- `POST /tools/extract-address`
- `POST /tools/buyers-search`
- `POST /tools/bricked-comps`

## Notes

- `tools/buyers` and `tools/buyers-search` call Azure Cosmos DB (buyers container).
- `tools/comps` and `tools/bricked-comps` call Bricked API and return trimmed comps payload.
- Tools do not write to legacy stores; they only read/query external systems.
- `apps/api` calls this service via OpenAI tool-calling orchestration.
- Frontend never calls MCP directly.
- Env loading precedence is: process env > `apps/mcp/.env`.

## Required Env (for live tools)

- `AZURE_COSMOSDB_ACCOUNT`
- `AZURE_COSMOSDB_ACCOUNT_KEY`
- `AZURE_COSMOSDB_BUYERS_DATABASE`
- `AZURE_COSMOSDB_NATIONWIDE_BUYERS_CONTAINER`
- `BRICKED_API_KEY`
