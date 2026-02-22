# ARI – BMAD Architecture

## Goal
Rebuild ARI as an agentic, tool-using system where:
- The model reasons and chooses MCP tools
- MCP is never exposed to the frontend
- All system prompts and orchestration live server-side
- Frontend uses Vercel AI Chatbot
- Deployed on Azure (no Docker)

## Components
1. Frontend: Vercel ai-chatbot (Next.js)
2. Application Layer: Flask or Quart API
3. Tool Layer: MCP Server (Python)

## Request Flow
User → ai-chatbot → API (/v1/chat/completions) → GPT-5.2 → MCP tools → API → UI

## Non-Negotiables
- OpenAI-compatible streaming endpoint
- Model chooses tools (no hard classifier)
- Deterministic MCP tools
- Stripe subscription gating
- Azure-native deployment
