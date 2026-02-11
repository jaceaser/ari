"""Pydantic request/response schemas for Phase 2 API endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── Auth ──

class AuthExchangeResponse(BaseModel):
    token: str
    user_id: str
    email: str


# ── Sessions ──

class SessionResponse(BaseModel):
    id: str
    created_at: str


class SessionListItem(BaseModel):
    id: str
    title: Optional[str] = None
    status: str
    created_at: str
    sealed_at: Optional[str] = None


class SessionDetail(SessionListItem):
    pass


# ── Messages ──

class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=32000)


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    created_at: str


# ── Lead Runs ──

class LeadRunListItem(BaseModel):
    id: str
    summary: str
    location: str
    strategy: str
    result_count: int
    created_at: str


class LeadRunDetail(LeadRunListItem):
    file_url: str
    filters: Optional[dict] = None
