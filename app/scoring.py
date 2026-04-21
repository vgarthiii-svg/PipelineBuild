"""
Scoring engine for the BD Pipeline Agent.

Matchmaker Score = (PMF * W1) + ((RS / 5 * 100) * W2)
Default weights: W1 = 0.6, W2 = 0.4

PMF Calculation:
  raw_pmf = sum of (criterion_score / 5) * criterion_weight
  max_possible = sum of all criterion weights
  normalized_pmf = (raw_pmf / max_possible) * 100

Tiers:
  70+   = Hot    (priority outreach)
  50-69 = Warm   (secondary outreach)
  30-49 = Monitor (track for changes)
  <30   = Pass   (skip unless something changes)
"""

from typing import List, Tuple, Optional


def calculate_pmf(scores_and_weights: List[Tuple[int, int]]) -> float:
    """
    Calculate normalized Product-Market Fit score (0-100).

    Args:
        scores_and_weights: List of (criterion_score 0-5, criterion_weight 1-10) tuples

    Returns:
        Normalized PMF score 0-100, or 0.0 if no criteria.
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


def calculate_matchmaker(
    pmf: float,
    rs: int,
    pmf_weight: float = 0.6,
    rs_weight: float = 0.4,
) -> float:
    """
    Calculate the Matchmaker Score (0-100).

    Args:
        pmf: Normalized PMF score (0-100)
        rs: Relationship Strength (0-5)
        pmf_weight: Weight for PMF dimension (default 0.6)
        rs_weight: Weight for RS dimension (default 0.4)

    Returns:
        Matchmaker score 0-100.
    """
    rs_normalized = (rs / 5.0) * 100.0
    return (pmf * pmf_weight) + (rs_normalized * rs_weight)


def assign_tier(matchmaker_score: Optional[float]) -> str:
    """
    Assign a tier based on the Matchmaker Score.

    Returns one of: "hot", "warm", "monitor", "pass", "unscored"
    """
    if matchmaker_score is None:
        return "unscored"

    if matchmaker_score >= 70:
        return "hot"
    elif matchmaker_score >= 50:
        return "warm"
    elif matchmaker_score >= 30:
        return "monitor"
    else:
        return "pass"


def score_pipeline_entry(criterion_scores_and_weights, rs, pmf_weight=0.6, rs_weight=0.4):
    """
    Full scoring for a single pipeline entry.

    Returns dict with pmf_score, matchmaker_score, tier.
    """
    pmf = calculate_pmf(criterion_scores_and_weights)
    matchmaker = calculate_matchmaker(pmf, rs, pmf_weight, rs_weight)
    tier = assign_tier(matchmaker)

    return {
        "pmf_score": round(pmf, 1),
        "matchmaker_score": round(matchmaker, 1),
        "tier": tier,
    }
