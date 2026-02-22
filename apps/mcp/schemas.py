"""
Pydantic request/response models for all 16 MCP tool endpoints.

The API layer sends this envelope to each tool:
    {"prompt": "string", "messages": [...], "arguments": {...}}

And expects back:
    {"ok": true, "tool": "tool_name", "data": {...}}
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Shared request envelope
# ---------------------------------------------------------------------------

class ToolRequest(BaseModel):
    """Inbound envelope from the API layer."""
    prompt: str = ""
    messages: list[dict[str, Any]] = Field(default_factory=list)
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolResponse(BaseModel):
    """Standard outbound envelope."""
    ok: bool = True
    tool: str
    result: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Per-tool argument models (extracted from arguments dict)
# ---------------------------------------------------------------------------

class ClassifyResult(BaseModel):
    route: str
    scores: dict[str, int] = Field(default_factory=dict)
    explanation: str = ""
    route_system_prompt_available: bool = False
    classification_prompt: str = ""


class EducationResult(BaseModel):
    route: str = "Education"
    retrieval_query: str = ""
    subtopics: list[str] = Field(default_factory=list)
    route_system_prompt: str = ""
    context_hint: str = ""


class LeadsArguments(BaseModel):
    url: Optional[str] = None
    filename: Optional[str] = None
    max_pages: int = Field(default=5, ge=1, le=10)


class LeadsResult(BaseModel):
    route: str = "Leads"
    detected_url: Optional[str] = None
    lead_type: str = "Unknown"
    status: str = "pending"
    message: str = ""
    preview: Optional[str] = None
    excel_link: Optional[str] = None
    properties_count: int = 0
    retrieval_query: str = ""
    route_system_prompt: str = ""
    lead_link_prompt: str = ""
    context_hint: str = ""


class BrickedCompsArguments(BaseModel):
    address: Optional[str] = None
    max_comps: int = Field(default=12, ge=1, le=50)


class BrickedCompsResult(BaseModel):
    route: str = "Comps"
    subject_address: str = ""
    max_comps: int = 12
    data_source: str = "bricked"
    status: str = "pending"
    message: str = ""
    bricked: Optional[dict[str, Any]] = None
    arv: Optional[Any] = None
    cmv: Optional[Any] = None
    comps_count: int = 0
    retrieval_query: str = ""
    route_system_prompt: str = ""
    comp_link_prompt: str = ""
    context_hint: str = ""


class BuyersSearchArguments(BaseModel):
    city: Optional[str] = None
    state: Optional[str] = None
    max_results: int = Field(default=50, ge=1, le=100)


class BuyersResult(BaseModel):
    route: str = "Buyers"
    city: Optional[str] = None
    state: Optional[str] = None
    location_source: str = "not_found"
    status: str = "pending"
    message: str = ""
    data_source: str = "cosmos"
    buyers_preview: list[dict[str, Any]] = Field(default_factory=list)
    buyers_sample: list[dict[str, Any]] = Field(default_factory=list)
    buyers_count: int = 0
    max_results: int = 50
    retrieval_query: str = ""
    route_system_prompt: str = ""
    context_hint: str = ""


class AttorneysArguments(BaseModel):
    url: Optional[str] = None
    filename: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None


class AttorneysResult(BaseModel):
    route: str = "Attorneys"
    city: Optional[str] = None
    state: Optional[str] = None
    status: str = "pending"
    message: str = ""
    preview: Optional[str] = None
    excel_link: Optional[str] = None
    attorneys_count: int = 0
    retrieval_query: str = ""
    route_system_prompt: str = ""
    attorney_link_prompt: str = ""
    city_state_prompt: str = ""
    context_hint: str = ""


class StrategyResult(BaseModel):
    route: str = "Strategy"
    retrieval_query: str = ""
    route_system_prompt: str = ""
    context_hint: str = ""


class ContractsResult(BaseModel):
    route: str = "Contracts"
    retrieval_query: str = ""
    route_system_prompt: str = ""
    contracts_expansion_prompt: str = ""
    expanded_prompt: str = ""
    context_hint: str = ""


class OfftopicResult(BaseModel):
    route: str = "Offtopic"
    route_system_prompt: str = ""
    context_hint: str = ""
    timestamp: str = ""
    prompt: str = ""


class ExtractCityStateResult(BaseModel):
    city: Optional[str] = None
    state: Optional[str] = None
    location_source: str = "not_found"
    prompt: str = ""


class ExtractAddressResult(BaseModel):
    address: Optional[str] = None
    address_source: str = "prompt"
    address_candidates: list[str] = Field(default_factory=list)


class BuildRetrievalQueryResult(BaseModel):
    retrieval_query: str = ""
    prompt: str = ""


class InferLeadTypeResult(BaseModel):
    url: Optional[str] = None
    lead_type: str = "Unknown"


class IntegrationConfigResult(BaseModel):
    azure_openai: bool = False
    azure_search: bool = False
    azure_cosmos: bool = False
    azure_cosmos_buyers: bool = False
    bricked: bool = False
    stripe: bool = False
