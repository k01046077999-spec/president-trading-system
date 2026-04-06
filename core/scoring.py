def classify_signal(mode: str, stage1_score: float, fib_ok: bool, rr: float, divergence_strength: float, trend_ok: bool, entry_ok: bool):
    warnings = []
    rejected_by = []

    if mode == "main":
        if stage1_score < 2.45:
            rejected_by.append("stage1_score_low")
        if not trend_ok:
            rejected_by.append("trend_filter_fail")
        if not entry_ok:
            rejected_by.append("entry_not_confirmed")
        if not fib_ok:
            rejected_by.append("fib_zone_fail")
        if rr < 1.8:
            rejected_by.append("rr_too_low")
        if divergence_strength < 1.0:
            rejected_by.append("divergence_weak")
        passed = not rejected_by
        return passed, ("ready" if passed else "watch"), warnings, rejected_by

    if stage1_score < 1.75:
        rejected_by.append("stage1_score_low")
    if rr < 1.2:
        rejected_by.append("rr_too_low")
    passed = len(rejected_by) == 0
    if not trend_ok:
        warnings.append("trend_filter_weak")
    if not entry_ok:
        warnings.append("entry_not_confirmed")
    if not fib_ok:
        warnings.append("fib_zone_not_confirmed")
    if divergence_strength < 0.85:
        warnings.append("divergence_weak")
    return passed, "watch", warnings, rejected_by
