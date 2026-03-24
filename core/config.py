from pydantic import BaseModel


class ScanConfig(BaseModel):
    mode: str = "main"
    limit: int = 10
    pivot_window: int = 3
    rsi_period: int = 14
    lookback_bars: int = 220
    min_quote_volume_usdt_main: float = 8_000_000
    min_quote_volume_usdt_sub: float = 2_500_000
    max_recent_pump_pct_main: float = 15.0
    max_recent_pump_pct_sub: float = 20.0
    min_reward_risk_main: float = 1.5
    min_reward_risk_sub: float = 1.0
    fib_zone_main_low: float = 0.618
    fib_zone_main_high: float = 0.786
    fib_zone_sub_low: float = 0.55
    fib_zone_sub_high: float = 0.82
    structure_lookback_bars: int = 70
    resistance_buffer_pct_main: float = 2.5
    resistance_buffer_pct_sub: float = 1.8
    support_buffer_pct_main: float = 2.5
    support_buffer_pct_sub: float = 1.8
    max_stop_pct_main: float = 10.0
    max_stop_pct_sub: float = 14.0
    min_stop_pct_main: float = 1.5
    min_stop_pct_sub: float = 0.8
    min_pivot_spacing: int = 4
    min_structure_score_main: float = 2.0
    min_structure_score_sub: float = 1.0
    candidate_pool_main: int = 120
    candidate_pool_sub: int = 180
    max_scan_seconds_main: float = 14.0
    max_scan_seconds_sub: float = 24.0
    max_processed_symbols_main: int = 36
    max_processed_symbols_sub: int = 72

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
    def candidate_pool(self) -> int:
        return self.candidate_pool_main if self.mode == "main" else self.candidate_pool_sub

    @property
    def max_scan_seconds(self) -> float:
        return self.max_scan_seconds_main if self.mode == "main" else self.max_scan_seconds_sub

    @property
    def max_processed_symbols(self) -> int:
        return self.max_processed_symbols_main if self.mode == "main" else self.max_processed_symbols_sub

    @property
    def min_quote_volume_usdt(self) -> float:
        return self.min_quote_volume_usdt_main if self.mode == "main" else self.min_quote_volume_usdt_sub

    @property
    def max_recent_pump_pct(self) -> float:
        return self.max_recent_pump_pct_main if self.mode == "main" else self.max_recent_pump_pct_sub

    @property
    def resistance_buffer_pct(self) -> float:
        return self.resistance_buffer_pct_main if self.mode == "main" else self.resistance_buffer_pct_sub

    @property
    def support_buffer_pct(self) -> float:
        return self.support_buffer_pct_main if self.mode == "main" else self.support_buffer_pct_sub
