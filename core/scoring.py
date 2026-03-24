from __future__ import annotations

from typing import Dict


def score_candidate(
    *,
    divergence: Dict,
    zone: Dict,
    volume_ratio_value: float,
    recent_pump: float,
    level_gap_pct: float,
    rr1: float,
    structure_score: float,
    mode: str,
) -> Dict[str, object]:
    score = 0.0
    reasons = []
    warnings = []
    hard_fail_reasons = []
    downgrade_reasons = []

    if divergence.get("linked"):
        score += 3
        reasons.append("다이버전스 연계")
    elif divergence.get("regular"):
        score += 1.5
        reasons.append("일반 다이버전스")
    else:
        hard_fail_reasons.append("유효 다이버전스 없음")

    extreme_score = divergence.get("extreme_score", 0)
    if extreme_score:
        score += extreme_score
        reasons.append("RSI 극단 구간")

    spacing_score = divergence.get("spacing_score", 0)
    score += spacing_score * 0.75
    if spacing_score:
        reasons.append("피벗 간격 양호")
    else:
        warnings.append("피벗 간격 부족")

    if divergence.get("strength", 0) >= 0.09:
        score += 1
        reasons.append("가격·RSI 괴리 양호")
    else:
        warnings.append("다이버전스 강도 약함")

    if zone["in_zone"]:
        score += 2 if mode == "main" else 1
        reasons.append("Fib 핵심구간")
    else:
        warnings.append("진입구간 대기")
        downgrade_reasons.append("현재 진입구간 아님")

    if volume_ratio_value > 0.05:
        score += 0.75
        reasons.append("거래량 증가")
    else:
        warnings.append("거래량 증가 약함")

    score += structure_score
    if structure_score >= 2:
        reasons.append("구조 선명도 양호")
    elif structure_score >= 1:
        reasons.append("구조 보통")
    else:
        warnings.append("구조 노이즈 가능성")

    if recent_pump > 0:
        score -= 1
        warnings.append("최근 급등 구간")
        downgrade_reasons.append("최근 급등으로 추격 리스크")

    if level_gap_pct < 0:
        score -= 2
        warnings.append("반대 레벨 침범")
        hard_fail_reasons.append("반대 레벨 침범")
    elif level_gap_pct < (2.5 if mode == "main" else 1.8):
        score -= 0.75
        warnings.append("반대 레벨 여유 부족")
        downgrade_reasons.append("반대 레벨 여유 부족")

    rr_cut = 1.5 if mode == "main" else 1.0
    if rr1 >= rr_cut:
        score += 1.5
        reasons.append("손익비 양호")
    else:
        warnings.append("손익비 부족")
        downgrade_reasons.append("손익비 부족")

    passed = score >= (7.5 if mode == "main" else 3.5) and not hard_fail_reasons
    return {
        "score": round(score, 2),
        "passed": passed,
        "reasons": reasons,
        "warnings": warnings,
        "hard_fail_reasons": hard_fail_reasons,
        "downgrade_reasons": downgrade_reasons,
    }
