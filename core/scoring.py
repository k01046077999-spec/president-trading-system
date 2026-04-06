def classify_signal(
    mode: str,
    stage1_score: float,
    oversold_ok: bool,
    fib_ok: bool,
    divergence_ok: bool,
    divergence_chain_ok: bool,
    volume_ok: bool,
    breakout_ok: bool,
    ema_reclaim_ok: bool,
    rr: float,
    pre_main_score: int = 0,
    ema_tight_ok: bool = False,
    rising_lows_ok: bool = False,
    compression_ok: bool = False,
    volume_alive_ok: bool = False,
):
    warnings = []
    rejected_by = []

    if mode == "main":
        if stage1_score < 2.4:
            rejected_by.append("stage1_score_low")
        if not oversold_ok:
            rejected_by.append("rsi_oversold_fail")
        if not divergence_ok:
            rejected_by.append("divergence_fail")
        if not fib_ok:
            rejected_by.append("fib_zone_fail")
        if not ema_reclaim_ok:
            rejected_by.append("ema_reclaim_fail")
        if not breakout_ok:
            rejected_by.append("micro_breakout_fail")
        if not volume_ok:
            rejected_by.append("volume_confirm_fail")
        if rr < 1.5:
            rejected_by.append("rr_too_low")
        passed = not rejected_by
        return passed, ("ready" if passed else "watch"), warnings, rejected_by

    if mode == "pre_main":
        if stage1_score < 1.8:
            rejected_by.append("stage1_score_low")
        if rr < 0.8:
            rejected_by.append("rr_too_low")
        if pre_main_score < 3:
            rejected_by.append("pre_main_score_low")
        if breakout_ok:
            warnings.append("already_breakout")
        if not oversold_ok:
            warnings.append("rsi_oversold_fail")
        if not divergence_ok:
            warnings.append("divergence_fail")
        elif not divergence_chain_ok:
            warnings.append("divergence_chain_not_confirmed")
        if not fib_ok:
            warnings.append("fib_zone_not_confirmed")
        if not ema_tight_ok:
            warnings.append("ema_not_tight")
        if not rising_lows_ok:
            warnings.append("rising_lows_not_confirmed")
        if not compression_ok:
            warnings.append("volatility_compression_fail")
        if not volume_alive_ok:
            warnings.append("volume_alive_fail")
        passed = len(rejected_by) == 0
        return passed, "watch", warnings, rejected_by

    if stage1_score < 1.6:
        rejected_by.append("stage1_score_low")
    if rr < 1.0:
        rejected_by.append("rr_too_low")
    passed = len(rejected_by) == 0
    if not oversold_ok:
        warnings.append("rsi_oversold_fail")
    if not divergence_ok:
        warnings.append("divergence_fail")
    elif not divergence_chain_ok:
        warnings.append("divergence_chain_not_confirmed")
    if not fib_ok:
        warnings.append("fib_zone_not_confirmed")
    if not ema_reclaim_ok:
        warnings.append("ema_reclaim_fail")
    if not breakout_ok:
        warnings.append("micro_breakout_fail")
    if not volume_ok:
        warnings.append("volume_confirm_fail")
    return passed, "watch", warnings, rejected_by
