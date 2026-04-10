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
    min_confirmations: int = 2,
):
    warnings = []
    rejected_by = []

    confirmation_count = sum(
        1 for ok in (ema_reclaim_ok, breakout_ok, volume_ok) if ok
    )

    if mode == "main":
        if stage1_score < 2.3:
            rejected_by.append("stage1_score_low")
        if not oversold_ok:
            rejected_by.append("rsi_oversold_fail")
        if not divergence_ok:
            rejected_by.append("divergence_fail")
        if not fib_ok:
            rejected_by.append("fib_zone_fail")
        if rr < 1.25:
            rejected_by.append("rr_too_low")
        if confirmation_count < min_confirmations:
            rejected_by.append("confirmation_stack_fail")
        passed = not rejected_by
        if not divergence_chain_ok:
            warnings.append("divergence_chain_not_confirmed")
        if not ema_reclaim_ok:
            warnings.append("ema_reclaim_fail")
        if not breakout_ok:
            warnings.append("micro_breakout_fail")
        if not volume_ok:
            warnings.append("volume_confirm_fail")
        return passed, ("ready" if passed else "watch"), warnings, rejected_by, confirmation_count

    if stage1_score < 1.6:
        rejected_by.append("stage1_score_low")
    if rr < 1.0:
        rejected_by.append("rr_too_low")
    if confirmation_count < 1:
        rejected_by.append("confirmation_stack_fail")
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
    return passed, "watch", warnings, rejected_by, confirmation_count
