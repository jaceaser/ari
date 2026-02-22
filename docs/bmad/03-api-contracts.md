# API Contracts

## Chat Endpoint
POST /v1/chat/completions

### Compatible With
- OpenAI Chat Completions
- Vercel AI SDK

### Requirements
- SSE streaming
- Accepts messages[]
- Supports tool calling
- Auth via Bearer token

### Forbidden
- Frontend cannot see MCP endpoints
- Frontend cannot pass system prompt
