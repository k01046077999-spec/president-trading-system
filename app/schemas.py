from typing import List, Literal, Optional
from pydantic import BaseModel, Field

StatusType = Literal["ok", "partial", "error"]
ModeType = Literal["main", "sub"]
StateType = Literal["ready", "watch", "reject"]
DirectionType = Literal["long", "short", "neutral"]

class HealthResponse(BaseModel):
    status: str = "ok"
    system: str = "president-trading-system"
    version: str

class ScanItem(BaseModel):
    symbol: str
    mode: ModeType
    passed: bool = False
    state: StateType = "reject"
    direction: DirectionType = "neutral"
    score: float = 0.0
    entry_reference_price: Optional[float] = None
    stop_pct: Optional[float] = None
    tp1_pct: Optional[float] = None
    tp2_pct: Optional[float] = None
    tp3_pct: Optional[float] = None
    rr1: Optional[float] = None
    rr2: Optional[float] = None
    rr3: Optional[float] = None
    message: str = ""
    reasons: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    rejected_by: List[str] = Field(default_factory=list)
    downgraded_by: List[str] = Field(default_factory=list)

class ScanResponse(BaseModel):
    status: StatusType
    mode: ModeType
    count: int
    candidate_pool: int
    stage1_checked: int
    stage2_checked: int
    scan_seconds: float
    stopped_reason: Optional[str] = None
    items: List[ScanItem] = Field(default_factory=list)
    message: str = ""
    errors: List[str] = Field(default_factory=list)
