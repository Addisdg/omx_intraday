from __future__ import annotations


def calculate_rank_components(
    confidence: float,
    historical_probability: float,
    total_r: float,
    max_drawdown_r: float,
) -> dict:
    confidence_contribution = confidence * 0.35
    probability_contribution = historical_probability * 0.35
    total_r_contribution = total_r * 5
    drawdown_penalty = abs(max_drawdown_r) * 3
    rank_score = confidence_contribution + probability_contribution + total_r_contribution - drawdown_penalty

    return {
        "confidence_contribution": round(confidence_contribution, 2),
        "probability_contribution": round(probability_contribution, 2),
        "total_r_contribution": round(total_r_contribution, 2),
        "drawdown_penalty": round(drawdown_penalty, 2),
        "rank_score": round(rank_score, 2),
    }


def candidate_filter_result(
    status: str,
    historical_probability: float | None,
    total_r: float | None,
    research_quality: str | None = None,
    min_probability: float = 60,
) -> dict:
    if status != "ok":
        return {"candidate_pass": False, "candidate_filter": "Failed: no usable research result"}
    if historical_probability is None:
        return {"candidate_pass": False, "candidate_filter": "Failed: historical probability unavailable"}
    if total_r is None:
        return {"candidate_pass": False, "candidate_filter": "Failed: total R unavailable"}

    reasons = []
    if historical_probability < min_probability:
        reasons.append(f"historical probability below {min_probability:.0f}%")
    if total_r <= 0:
        reasons.append("total R is not positive")
    if research_quality in {"Low", "No evidence"}:
        reasons.append(f"research quality is {research_quality.lower()}")

    if reasons:
        return {"candidate_pass": False, "candidate_filter": "Failed: " + "; ".join(reasons)}
    return {"candidate_pass": True, "candidate_filter": "Passed: probability threshold, positive total R, and usable research quality"}
