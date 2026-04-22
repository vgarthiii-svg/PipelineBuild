"""
Scoring math — should be deterministic and stable.
These are the regressions most likely to bite us after a careless edit.
"""

import pytest

from app.scoring import calculate_pmf, calculate_matchmaker, assign_tier


class TestPMF:
    def test_empty_scores_returns_zero(self):
        assert calculate_pmf([]) == 0.0

    def test_perfect_scores_returns_hundred(self):
        assert calculate_pmf([(5, 1), (5, 1)]) == pytest.approx(100.0)

    def test_zero_scores_returns_zero(self):
        assert calculate_pmf([(0, 5), (0, 3)]) == pytest.approx(0.0)

    def test_weighted_average_math(self):
        # (3/5 * 4 + 4/5 * 6) / (4 + 6) * 100 = 72
        assert calculate_pmf([(3, 4), (4, 6)]) == pytest.approx(72.0, abs=0.1)

    def test_higher_weight_dominates(self):
        # Same raw scores; weight shift moves PMF in the expected direction
        low_weight_on_high_score = calculate_pmf([(5, 1), (1, 10)])
        high_weight_on_high_score = calculate_pmf([(5, 10), (1, 1)])
        assert high_weight_on_high_score > low_weight_on_high_score


class TestMatchmaker:
    def test_no_multipliers_returns_pmf_plus_rs_bonus(self):
        # PMF 80, RS 5 → adjusted 80, rs bonus (5/5)*20 = 20 → 100
        ms = calculate_matchmaker(pmf=80, rs=5)
        assert ms == pytest.approx(100.0)

    def test_friction_reduces_adjusted_pmf(self):
        base = calculate_matchmaker(pmf=80, rs=0)
        reduced = calculate_matchmaker(pmf=80, rs=0, friction_coefficient=0.8)
        assert reduced < base
        # 80 * 0.8 = 64
        assert reduced == pytest.approx(64.0)

    def test_intent_multiplies_pmf_side(self):
        base = calculate_matchmaker(pmf=50, rs=0)
        boosted = calculate_matchmaker(pmf=50, rs=0, intent_multiplier=1.2)
        assert boosted == pytest.approx(60.0)

    def test_zero_rs_still_scores(self):
        ms = calculate_matchmaker(pmf=90, rs=0)
        assert ms > 0

    def test_score_caps_at_100(self):
        # Adjusted PMF 100 + RS bonus 20 would be 120; formula caps at 100
        ms = calculate_matchmaker(pmf=100, rs=5, intent_multiplier=1.0)
        assert ms == pytest.approx(100.0)


class TestTierAssignment:
    @pytest.mark.parametrize("score,expected", [
        (95, "hot"),
        (80, "hot"),
        (79, "warm"),
        (60, "warm"),
        (59, "monitor"),
        (40, "monitor"),
        (39, "pass"),
        (0, "pass"),
    ])
    def test_tier_boundaries(self, score, expected):
        assert assign_tier(score) == expected

    def test_filtered_flag_overrides(self):
        assert assign_tier(95, filtered=True) == "filtered"

    def test_none_score_returns_unscored(self):
        assert assign_tier(None) == "unscored"
