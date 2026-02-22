# MCP Tooling Design

## Principles
- Tools are deterministic
- Tools do one thing well
- Tools return data, not narratives
- Model decides which tools to call
- Tools may be chained

## Tool Layers
### Atomic Tools
- leads.search
- property.get
- comps.find
- valuation.estimate_arv
- buyers.match
- contracts.generate

### Workflow Tools (optional)
- workflow.find_deals
- workflow.comps_and_arv
- workflow.offer_and_terms

## Tool Constraints
- Max tool calls per turn: 5
- Expensive tools require confirmation
- Tool access gated by Stripe tier
    