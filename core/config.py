from dataclasses import dataclass, field
from typing import List

EXCLUDED_KEYWORDS = ("UP", "DOWN", "BULL", "BEAR", "USD_", "USDC", "FDUSD", "TUSD", "BUSD", "DAI", "PAXG")
EXCLUDED_EXACT = {
    "USDC/USDT", "FDUSD/USDT", "TUSD/USDT", "BUSD/USDT", "DAI/USDT", "USDP/USDT",
    "USDCUSDT", "FDUSDUSDT", "TUSDUSDT", "BUSDUSDT", "DAIUSDT", "USDPUSDT"
}

@dataclass
class ScanProfile:
    mode: str
    pool_size: int
    stage1_limit: int
    stage2_limit: int
    time_budget_sec: float
    result_limit: int
    min_quote_volume: float
    stage1_rsi_low: float
    stage1_rsi_high: float
    stage1_score_min: float
    final_score_min: float
    allow_watch: bool = True

MAIN_PROFILE = ScanProfile(
    mode="main",
    pool_size=260,
    stage1_limit=80,
    stage2_limit=24,
    time_budget_sec=22.0,
    result_limit=10,
    min_quote_volume=3_000_000,
    stage1_rsi_low=22.0,
    stage1_rsi_high=58.0,
    stage1_score_min=2.0,
    final_score_min=6.0,
)

SUB_PROFILE = ScanProfile(
    mode="sub",
    pool_size=360,
    stage1_limit=140,
    stage2_limit=48,
    time_budget_sec=32.0,
    result_limit=14,
    min_quote_volume=1_500_000,
    stage1_rsi_low=18.0,
    stage1_rsi_high=65.0,
    stage1_score_min=1.0,
    final_score_min=4.0,
)

BASE_URL = "https://president-trading-system-1.onrender.com"
APP_VERSION = "1.5.0"
