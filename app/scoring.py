"""
Scoring engine for the BD Pipeline Agent.

v2 Formula (4-Layer):
  Layer 1: Identity Filter (hard pass/fail gate)
  Layer 2: PMF from weighted criteria (0-100)
  Layer 3: Friction Coefficient from behavior comparison (0.5-1.0)
  Layer 4: Intent Multiplier from signals (0.8-2.0)

  Base = PMF score (0-100)
  Adjusted = Base * friction_coefficient * intent_multiplier
  RS Bonus = (relationship_score / 5) * 20
  Matchmaker Score = min(100, Adjusted + RS_Bonus)

Tiers:
  80+   = Hot
  60-79 = Warm
  40-59 = Monitor
  <40   = Pass
  filtered = Hard-filtered by identity

v1 Formula (kept for reference):
  Matchmaker = (PMF * W1) + ((RS / 5 * 100) * W2)
"""

import json
from typing import List, Tuple, Optional
from datetime import datetime, timedelta


def calculate_pmf(scores_and_weights: List[Tuple[int, int]]) -> float:
    """
    Calculate normalized Product-Market Fit score (0-100).
    Unchanged from v1.
    """
    if not scores_and_weights:
        return 0.0

    raw_pmf = 0.0
    max_possible = 0.0

    for score, weight in scores_and_weights:
        raw_pmf += (score / 5.0) * weight
        max_possible += weight

    if max_possible == 0:
        return 0.0

    return (raw_pmf / max_possible) * 100.0


# ============ v2: IDENTITY HARD FILTER ============


def run_identity_filter(prospect, client_filter):
    """
    Check prospect against client's identity filters.
    Returns (passed: bool, reason: str or None).
    If no filter exists for this client, always passes.
    """
    if not client_filter:
        return True, None

    reasons = []

    # Business model filter
    if client_filter.allowed_business_models:
        allowed = _parse_json_list(client_filter.allowed_business_models)
        if allowed and prospect.business_model:
            if prospect.business_model not in allowed:
                reasons.append(f"Business model '{prospect.business_model}' not in allowed: {allowed}")

    # Stage filter
    if client_filter.allowed_stages:
        allowed = _parse_json_list(client_filter.allowed_stages)
        if allowed and prospect.stage:
            if prospect.stage not in allowed:
                reasons.append(f"Stage '{prospect.stage}' not in allowed: {allowed}")

    # Employee count filter
    if client_filter.min_employees and prospect.employees:
        if prospect.employees < client_filter.min_employees:
            reasons.append(f"Too small: {prospect.employees} employees, minimum {client_filter.min_employees}")
    if client_filter.max_employees and prospect.employees:
        if prospect.employees > client_filter.max_employees:
            reasons.append(f"Too large: {prospect.employees} employees, maximum {client_filter.max_employees}")

    # Excluded verticals
    if client_filter.excluded_verticals:
        excluded = _parse_json_list(client_filter.excluded_verticals)
        if excluded and prospect.industry_vertical:
            if prospect.industry_vertical in excluded:
                reasons.append(f"Vertical '{prospect.industry_vertical}' is excluded")

    # Required verticals
    if client_filter.required_verticals:
        required = _parse_json_list(client_filter.required_verticals)
        if required and prospect.industry_vertical:
            if prospect.industry_vertical not in required:
                reasons.append(f"Vertical '{prospect.industry_vertical}' not in required: {required}")

    if reasons:
        return False, "; ".join(reasons)
    return True, None


# ============ v2: FRICTION COEFFICIENT ============


def calculate_friction_coefficient(client_behavior, prospect_behavior):
    """
    Compare behavior profiles. Returns coefficient 0.5 to 1.0.
    1.0 = strong alignment, 0.5 = major mismatches.
    If either profile is missing, returns 1.0 (neutral).
    """
    if not client_behavior or not prospect_behavior:
        return 1.0

    friction_points = 0
    comparisons = 0

    # Sales motion
    if client_behavior.sales_motion and prospect_behavior.sales_motion:
        comparisons += 1
        if client_behavior.sales_motion != prospect_behavior.sales_motion:
            pair = {client_behavior.sales_motion, prospect_behavior.sales_motion}
            if pair == {"transactional", "enterprise"}:
                friction_points += 2
            else:
                friction_points += 1

    # Decision speed
    if client_behavior.decision_speed and prospect_behavior.decision_speed:
        comparisons += 1
        if client_behavior.decision_speed != prospect_behavior.decision_speed:
            pair = {client_behavior.decision_speed, prospect_behavior.decision_speed}
            if pair == {"fast", "bureaucratic"}:
                friction_points += 2
            else:
                friction_points += 1

    # Partner model
    if client_behavior.partner_model and prospect_behavior.partner_model:
        comparisons += 1
        if client_behavior.partner_model != prospect_behavior.partner_model:
            friction_points += 1

    # Culture
    if client_behavior.culture and prospect_behavior.culture:
        comparisons += 1
        if client_behavior.culture != prospect_behavior.culture:
            pair = {client_behavior.culture, prospect_behavior.culture}
            if pair == {"innovation-forward", "legacy"}:
                friction_points += 2
            else:
                friction_points += 1

    # Customer segment
    if client_behavior.customer_segment and prospect_behavior.customer_segment:
        comparisons += 1
        if client_behavior.customer_segment != prospect_behavior.customer_segment:
            friction_points += 1

    if comparisons == 0:
        return 1.0

    max_friction = comparisons * 2
    coefficient = 1.0 - (friction_points / max_friction * 0.5)
    return round(max(0.5, min(1.0, coefficient)), 2)


# ============ v2: INTENT MULTIPLIER ============


def calculate_intent_multiplier(intent_signals, days_lookback=90):
    """
    Calculate intent multiplier from recent signals.
    Returns 0.8 to 2.0.
    No signals = 0.8 (penalty for stale opportunities).
    """
    if not intent_signals:
        return 0.8

    cutoff = datetime.now().date() - timedelta(days=days_lookback)
    recent_signals = [s for s in intent_signals if not s.signal_date or s.signal_date >= cutoff]

    if not recent_signals:
        return 0.8

    urgency_weights = {"high": 3, "moderate": 2, "low": 1}
    total_weight = sum(urgency_weights.get(s.urgency, 1) for s in recent_signals)

    thirty_days = datetime.now().date() - timedelta(days=30)
    recency_bonus = sum(1 for s in recent_signals if s.signal_date and s.signal_date >= thirty_days)

    raw_score = total_weight + (recency_bonus * 0.5)
    multiplier = 0.8 + min(1.2, raw_score * 0.2)

    return round(min(2.0, multiplier), 2)


# ============ v2: UPDATED MATCHMAKER SCORE ============


def calculate_matchmaker(
    pmf: float,
    rs: int,
    friction_coefficient: float = 1.0,
    intent_multiplier: float = 1.0,
    pmf_weight: float = 0.6,
    rs_weight: float = 0.4,
) -> float:
    """
    v2 Matchmaker Score (0-100).

    Formula:
      Adjusted = PMF * friction_coefficient * intent_multiplier
      RS Bonus = (RS / 5) * 20
      Final = min(100, Adjusted + RS_Bonus)

    The pmf_weight and rs_weight params are kept for API compatibility
    but the v2 formula uses the layered approach instead.
    """
    adjusted = pmf * friction_coefficient * intent_multiplier
    rs_bonus = (rs / 5.0) * 20.0 if rs else 0.0
    final = min(100.0, adjusted + rs_bonus)
    return round(final, 1)


def assign_tier(matchmaker_score: Optional[float], filtered: bool = False) -> str:
    """
    Assign a tier based on the Matchmaker Score.
    v2 thresholds: 80/60/40.
    """
    if filtered:
        return "filtered"
    if matchmaker_score is None:
        return "unscored"
    if matchmaker_score >= 80:
        return "hot"
    elif matchmaker_score >= 60:
        return "warm"
    elif matchmaker_score >= 40:
        return "monitor"
    else:
        return "pass"


def score_pipeline_entry(criterion_scores_and_weights, rs, friction=1.0, intent=1.0, filtered=False, pmf_weight=0.6, rs_weight=0.4):
    """
    Full scoring for a single pipeline entry.
    Returns dict with pmf_score, matchmaker_score, tier, friction_coefficient, intent_multiplier.
    """
    pmf = calculate_pmf(criterion_scores_and_weights)
    matchmaker = calculate_matchmaker(pmf, rs, friction, intent, pmf_weight, rs_weight)
    tier = assign_tier(matchmaker, filtered)

    return {
        "pmf_score": round(pmf, 1),
        "matchmaker_score": round(matchmaker, 1),
        "tier": tier,
        "friction_coefficient": friction,
        "intent_multiplier": intent,
    }


# ============ HEURISTIC SCORING (NO API) ============


def heuristic_score_prospect(prospect, client, criteria):
    """
    Score a prospect against client criteria using rule-based heuristics.
    No API call. Uses prospect metadata (type, industry, business_model, stage,
    employees, description) to infer scores.

    Returns list of dicts: [{criterion_id, score, reasoning}]
    """
    results = []

    # Build a prospect profile from available data
    p_type = (prospect.type or "").lower()
    p_vertical = (prospect.industry_vertical or "").lower()
    p_model = (prospect.business_model or "").lower()
    p_stage = (prospect.stage or "").lower()
    p_segment = _infer_segment(prospect.employees)
    p_desc = (prospect.description or "").lower()
    p_name = (prospect.name or "").lower()

    # Client context
    c_desc = (client.description or "").lower()
    c_buyer = (client.target_buyer or "").lower()
    c_revenue = (client.primary_revenue_driver or "").lower()

    for criterion in criteria:
        c_name = criterion.name.lower()
        c_criterion_desc = (criterion.description or "").lower()

        score = _heuristic_for_criterion(
            c_name, c_criterion_desc,
            p_type, p_vertical, p_model, p_stage, p_segment, p_desc, p_name,
            c_desc, c_buyer, c_revenue,
            prospect,
        )

        reasoning = _heuristic_reasoning(c_name, score, prospect)

        results.append({
            "criterion_id": criterion.id,
            "score": score,
            "reasoning": reasoning,
        })

    return results


def _heuristic_for_criterion(c_name, c_desc, p_type, p_vertical, p_model, p_stage, p_segment, p_desc, p_name, c_desc_full, c_buyer, c_revenue, prospect):
    """
    Score 0-5 based on keyword matching and logical rules.
    """
    score = 2  # baseline

    # ---- Distribution / Channel alignment ----
    if any(kw in c_name for kw in ["distribution", "channel", "partner"]):
        if any(kw in p_type for kw in ["carrier", "brokerage", "agency", "mga"]):
            score = 4
        if any(kw in p_desc for kw in ["distribution", "channel", "partner", "broker", "agent"]):
            score = min(5, score + 1)
        if "technology" in p_type or "saas" in p_model:
            if any(kw in p_desc for kw in ["distribution", "platform", "marketplace"]):
                score = 4
            else:
                score = 2
        if any(kw in p_desc for kw in ["claims only", "claims-only", "litigation"]):
            score = 1

    # ---- SMB / Commercial focus ----
    elif any(kw in c_name for kw in ["smb", "small", "commercial"]):
        if p_segment == "SMB":
            score = 4
        elif p_segment == "mid-market":
            score = 3
        elif p_segment == "enterprise":
            score = 1
        if any(kw in p_desc for kw in ["small business", "smb", "small commercial", "commercial lines"]):
            score = min(5, score + 1)
        if any(kw in p_desc for kw in ["enterprise", "fortune 500", "large corporate"]):
            score = max(1, score - 1)

    # ---- Digital / CX / Acquisition ----
    elif any(kw in c_name for kw in ["digital", "cx", "customer experience", "acquisition", "online"]):
        if any(kw in p_desc for kw in ["digital", "online", "platform", "self-service", "portal", "api", "automation"]):
            score = 4
        if any(kw in p_desc for kw in ["ai", "machine learning", "analytics", "data"]):
            score = min(5, score + 1)
        if "technology" in p_type or "saas" in p_model:
            score = max(score, 3)
        if any(kw in p_type for kw in ["carrier"]) and "technology" not in p_type:
            score = max(2, score - 1)

    # ---- Lead gen / Demand gen ----
    elif any(kw in c_name for kw in ["lead", "demand", "referral", "acquisition"]):
        if any(kw in p_desc for kw in ["lead", "referral", "marketing", "demand", "customer acquisition"]):
            score = 4
        if any(kw in p_desc for kw in ["marketplace", "platform", "matching"]):
            score = min(5, score + 1)
        if any(kw in p_type for kw in ["carrier", "brokerage"]):
            score = max(score, 3)  # carriers need leads

    # ---- Product complementarity ----
    elif any(kw in c_name for kw in ["product", "complement", "integration", "compatibility"]):
        if "technology" in p_type and any(kw in c_desc_full for kw in ["insurance", "carrier", "policy"]):
            score = 3
        if any(kw in p_desc for kw in ["integration", "api", "connect", "plug"]):
            score = min(5, score + 1)

    # ---- Buyer alignment ----
    elif any(kw in c_name for kw in ["buyer", "alignment", "icp", "target"]):
        # Check if prospect sells to same buyer type as client
        if c_buyer:
            buyer_keywords = c_buyer.split()
            matches = sum(1 for kw in buyer_keywords if kw.lower() in p_desc or kw.lower() in p_type)
            if matches >= 2:
                score = 4
            elif matches >= 1:
                score = 3
        if p_vertical and c_desc_full and p_vertical in c_desc_full:
            score = min(5, score + 1)

    # ---- Technology / Innovation ----
    elif any(kw in c_name for kw in ["technology", "innovation", "tech", "modern"]):
        if "technology" in p_type or "saas" in p_model:
            score = 4
        if any(kw in p_desc for kw in ["ai", "machine learning", "cloud", "api", "automation"]):
            score = min(5, score + 1)
        if p_stage == "growth":
            score = min(5, score + 1)
        if "legacy" in p_desc:
            score = 1

    # ---- Market presence / Scale ----
    elif any(kw in c_name for kw in ["market", "scale", "reach", "presence", "size"]):
        if prospect.employees:
            if prospect.employees > 5000:
                score = 5
            elif prospect.employees > 1000:
                score = 4
            elif prospect.employees > 200:
                score = 3
            elif prospect.employees > 50:
                score = 2
            else:
                score = 1
        if "national" in p_type:
            score = max(score, 4)
        if "regional" in p_type:
            score = max(score, 3)

    # ---- Generic fallback: keyword matching ----
    else:
        c_keywords = set(c_name.split() + c_desc.split())
        c_keywords -= {"the", "a", "an", "of", "in", "for", "to", "and", "or", "is", "it", "with"}
        p_text = p_desc + " " + p_type + " " + p_vertical
        matches = sum(1 for kw in c_keywords if len(kw) > 3 and kw in p_text)
        if matches >= 3:
            score = 4
        elif matches >= 2:
            score = 3
        elif matches >= 1:
            score = 2
        else:
            score = 1

    return max(0, min(5, score))


def _infer_segment(employees):
    """Infer customer segment from employee count."""
    if not employees:
        return "unknown"
    if employees < 100:
        return "SMB"
    elif employees < 1000:
        return "mid-market"
    else:
        return "enterprise"


def _heuristic_reasoning(criterion_name, score, prospect):
    """Generate a brief reasoning string for a heuristic score."""
    labels = {0: "No match", 1: "Weak fit", 2: "Baseline", 3: "Moderate fit", 4: "Good fit", 5: "Strong fit"}
    label = labels.get(score, "Scored")
    parts = [label]
    if prospect.type:
        parts.append(f"Type: {prospect.type}")
    if prospect.industry_vertical:
        parts.append(f"Vertical: {prospect.industry_vertical}")
    if prospect.stage:
        parts.append(f"Stage: {prospect.stage}")
    return " | ".join(parts) + " (heuristic)"


# ============ HELPERS ============


def _parse_json_list(value):
    """Parse a JSON string to a list, or return the value if already a list."""
    if not value:
        return []
    if isinstance(value, list):
        return value
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return []
