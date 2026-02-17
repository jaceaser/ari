#!/bin/bash
# Azure App Service startup script for the ARI API backend.
# Set as the Startup Command in App Service Configuration.
set -e

cd /home/site/wwwroot

# Install dependencies (cached by App Service between deploys)
pip install -r requirements.txt --quiet

# Start with Hypercorn (ASGI server for Quart)
exec hypercorn app:app \
  --bind 0.0.0.0:8000 \
  --workers 2 \
  --access-logfile - \
  --error-logfile -
