from __future__ import annotations


SCREENER_TABLE_COLUMNS = {
    "ranking": [
        "symbol",
        "status",
        "status_reason",
        "rank_score",
        "candidate_pass",
        "candidate_filter",
        "setup",
        "signal",
        "confidence",
        "historical_probability",
        "total_r",
        "max_drawdown_r",
    ],
    "quality": [
        "symbol",
        "status",
        "research_quality",
        "similar_samples",
        "fallback_level",
        "validation_status",
        "quality_warnings",
        "matched_by",
    ],
    "research": [
        "symbol",
        "similar_win_rate",
        "average_r",
        "decision",
        "confidence_contribution",
        "probability_contribution",
        "total_r_contribution",
        "drawdown_penalty",
    ],
}


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


def screener_failure_row(symbol: str, status: str, reason: str) -> dict:
    candidate = candidate_filter_result(status, None, None)
    return {
        "symbol": symbol,
        "status": status,
        "status_reason": reason,
        "rank_score": 0,
        "research_quality": "No evidence",
        "quality_reason": reason,
        "fallback_level": "none",
        "validation_status": "not_run",
        "quality_warnings": reason,
        "similar_samples": 0,
        "matched_by": "none",
        "decision": "Research only: no usable result",
        **candidate,
    }


def classify_screener_exception(exc: Exception) -> dict:
    message = str(exc).strip()
    lowered = message.lower()

    if isinstance(exc, TimeoutError) or "timeout" in lowered or "timed out" in lowered:
        return {
            "status": "provider_timeout",
            "reason": "Market-data provider timed out for this symbol.",
        }
    if isinstance(exc, ConnectionError) or any(term in lowered for term in ["connection", "network", "dns", "name resolution"]):
        return {
            "status": "provider_connection_error",
            "reason": "Market-data provider connection failed for this symbol.",
        }
    if any(term in lowered for term in ["rate limit", "too many requests", "429"]):
        return {
            "status": "provider_rate_limited",
            "reason": "Market-data provider rate-limited this request.",
        }
    if isinstance(exc, ValueError) and "missing expected columns" in lowered:
        return {
            "status": "provider_schema_error",
            "reason": "Market-data provider returned an unexpected data shape.",
        }
    if any(term in lowered for term in ["possibly delisted", "no data", "not found", "invalid symbol"]):
        return {
            "status": "no_data",
            "reason": "No usable market data was returned for this symbol.",
        }
    return {
        "status": "error",
        "reason": "Unexpected screener error while processing this symbol.",
    }


def research_status_reason(status: str) -> str:
    reasons = {
        "no_data": "No candles were available for research.",
        "invalid_data": "Research data failed quality checks.",
        "insufficient_data": "Not enough candles were available for research.",
    }
    return reasons.get(status, f"Research returned status {status}.")


def select_screener_columns(columns: list[str], preset: str) -> list[str]:
    preferred = SCREENER_TABLE_COLUMNS.get(preset, [])
    return [column for column in preferred if column in columns]
