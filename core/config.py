from pydantic import BaseModel


class ScanConfig(BaseModel):
    mode: str = "main"
    limit: int = 15
    pivot_window: int = 3
    rsi_period: int = 14
    lookback_bars: int = 260
    min_quote_volume_usdt: float = 3_000_000
    max_recent_pump_pct: float = 18.0
    min_reward_risk_main: float = 1.6
    min_reward_risk_sub: float = 1.1
    fib_zone_main_low: float = 0.618
    fib_zone_main_high: float = 0.786
    fib_zone_sub_low: float = 0.55
    fib_zone_sub_high: float = 0.82
    structure_lookback_bars: int = 80
    resistance_buffer_pct: float = 3.0
    support_buffer_pct: float = 3.0
    max_stop_pct_main: float = 12.0
    max_stop_pct_sub: float = 15.0
    min_stop_pct_main: float = 1.5
    min_stop_pct_sub: float = 1.0
    min_pivot_spacing: int = 4
    min_structure_score_main: float = 2.0
    min_structure_score_sub: float = 1.0
    max_scan_symbols_main: int = 40
    max_scan_symbols_sub: int = 60

    @property
    def min_reward_risk(self) -> float:
        return self.min_reward_risk_main if self.mode == "main" else self.min_reward_risk_sub

    @property
    def max_stop_pct(self) -> float:
        return self.max_stop_pct_main if self.mode == "main" else self.max_stop_pct_sub

    @property
    def min_stop_pct(self) -> float:
        return self.min_stop_pct_main if self.mode == "main" else self.min_stop_pct_sub

    @property
    def fib_zone_low(self) -> float:
        return self.fib_zone_main_low if self.mode == "main" else self.fib_zone_sub_low

    @property
    def fib_zone_high(self) -> float:
        return self.fib_zone_main_high if self.mode == "main" else self.fib_zone_sub_high

    @property
    def min_structure_score(self) -> float:
        return self.min_structure_score_main if self.mode == "main" else self.min_structure_score_sub

    @property
    def max_scan_symbols(self) -> int:
        return self.max_scan_symbols_main if self.mode == "main" else self.max_scan_symbols_sub
