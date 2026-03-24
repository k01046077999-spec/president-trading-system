from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(examples=['ok'])
    system: str = Field(examples=['president-trading-system'])
    version: str = Field(examples=['1.4.1'])


class EntryZone(BaseModel):
    lower: float
    upper: float
    mid: float
    distance_to_zone_pct: float
    in_zone: bool


class RiskBlock(BaseModel):
    stop_price: float
    stop_pct: float
    tp1_price: float
    tp1_pct: float
    tp2_price: float
    tp2_pct: float
    tp3_price: float
    tp3_pct: float
    rr1: float
    rr2: float
    rr3: float


class SignalBlock(BaseModel):
    linked_divergence: bool
    regular_divergence: bool
    rsi_at_trigger: float
    divergence_strength: float
    pivot_spacing_score: float | int
    confirm_30m: bool
    confirm_4h: bool


class MarketContextBlock(BaseModel):
    volume_ratio: float
    recent_pump_pct: float
    level_gap_pct: float
    quote_volume_usdt: float
    structure_score: float | int
    structure_noise_ratio: float
    structure_bars: int


class FilterBlock(BaseModel):
    stop_ok: bool
    rr_ok: bool
    liquidity_ok: bool
    pump_ok: bool
    level_gap_ok: bool
    structure_ok: bool


class ScanItem(BaseModel):
    status: Literal['ok', 'partial']
    symbol: str
    mode: Literal['main', 'sub']
    side: Optional[Literal['long', 'short']] = None
    status_label: Optional[Literal['ready', 'watch']] = None
    state: str
    trade_plan: Optional[str] = None
    passed: bool
    score: Optional[float] = None
    message: str
    current_price: Optional[float] = None
    entry_reference_price: Optional[float] = None
    entry_zone: Optional[EntryZone] = None
    risk: Optional[RiskBlock] = None
    signal: Optional[SignalBlock] = None
    market_context: Optional[MarketContextBlock] = None
    reasons: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    rejected_by: List[str] = Field(default_factory=list)
    downgraded_by: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    filters: Optional[FilterBlock] = None
    fib_levels: Optional[Dict[str, float]] = None


class ScanResponse(BaseModel):
    status: Literal['ok', 'partial', 'error']
    mode: Literal['main', 'sub']
    count: int
    candidate_pool: Optional[int] = None
    scanned: Optional[int] = None
    stopped_reason: Optional[str] = None
    scan_seconds: Optional[float] = None
    items: List[ScanItem] = Field(default_factory=list)
    message: str
    errors: List[str] = Field(default_factory=list)
