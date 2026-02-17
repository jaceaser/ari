#!/bin/bash
# Azure App Service startup script for the ARI Next.js frontend.
# Set as the Startup Command in App Service Configuration.
# Requires: output: "standalone" in next.config.ts
set -e

cd /home/site/wwwroot

# Next.js standalone mode outputs server.js
exec node server.js
