from __future__ import annotations

from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    system: str = "president-trading-system"
    version: str


class ScanItem(BaseModel):
    symbol: str
    state: Literal["ready", "watch", "rejected"] = "watch"
    direction: Literal["long", "short", "neutral"] = "long"
    stop_pct: Optional[float] = None
    tp1_pct: Optional[float] = None
    tp2_pct: Optional[float] = None
    rr1: Optional[float] = None
    rr2: Optional[float] = None
    score: float = 0.0
    reason_summary: str = ""
    warnings: List[str] = Field(default_factory=list)
    rejected_by: List[str] = Field(default_factory=list)
    downgraded_by: List[str] = Field(default_factory=list)


class ScanResponse(BaseModel):
    status: Literal["ok", "partial", "refreshing", "error"]
    mode: Literal["main", "sub"]
    count: int
    candidate_pool: int = 0
    stage1_checked: int = 0
    stage2_checked: int = 0
    refreshed_at: Optional[str] = None
    age_seconds: Optional[float] = None
    cache_status: Optional[Literal["fresh", "stale", "empty"]] = None
    items: List[ScanItem] = Field(default_factory=list)
    message: str
    errors: List[str] = Field(default_factory=list)


class RefreshResponse(BaseModel):
    status: str
    mode: Literal["main", "sub"]
    message: str
