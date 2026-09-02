"""Unit tests for the academic calculation engine.

These cover the formulas the whole platform depends on, including the edge
cases called out in section 73 of the brief.
"""
from decimal import Decimal

from django.test import SimpleTestCase

from apps.core.calculations import (
    attendance_percentage,
    attendance_status,
    evaluate_risk,
    grade_point_average,
    linear_trend,
    percentage,
    resolve_grade,
    scaled_score,
    sessions_needed_to_reach,
    weighted_total,
)


class AttendanceCalculationTests(SimpleTestCase):
    def test_basic_percentage(self):
        self.assertEqual(attendance_percentage(15, 0, 0, 20), Decimal("75.00"))

    def test_late_counts_as_attended(self):
        self.assertEqual(attendance_percentage(14, 1, 0, 20), Decimal("75.00"))

    def test_excused_sessions_leave_the_denominator(self):
        # 14 of 18 applicable sessions once 2 excused are removed.
        self.assertEqual(attendance_percentage(14, 0, 2, 20), Decimal("77.78"))

    def test_zero_attendance(self):
        self.assertEqual(attendance_percentage(0, 0, 0, 20), Decimal("0.00"))

    def test_perfect_attendance(self):
        self.assertEqual(attendance_percentage(20, 0, 0, 20), Decimal("100.00"))

    def test_no_sessions_held_is_not_a_division_error(self):
        self.assertEqual(attendance_percentage(0, 0, 0, 0), Decimal("0.00"))

    def test_all_sessions_excused_is_not_a_division_error(self):
        self.assertEqual(attendance_percentage(0, 0, 5, 5), Decimal("0.00"))

    def test_status_bands_use_supplied_thresholds(self):
        self.assertEqual(attendance_status(80, 75, 65), "ok")
        self.assertEqual(attendance_status(70, 75, 65), "warning")
        self.assertEqual(attendance_status(60, 75, 65), "critical")
        self.assertEqual(attendance_status(75, 75, 65), "ok")

    def test_status_respects_a_reconfigured_threshold(self):
        # An institution running an 85% rule must see 80% flagged.
        self.assertEqual(attendance_status(80, 85, 70), "warning")

    def test_sessions_needed_to_recover(self):
        self.assertEqual(sessions_needed_to_reach(15, 0, 20, 75), 0)
        self.assertEqual(sessions_needed_to_reach(10, 0, 20, 75), 20)

    def test_sessions_needed_is_zero_when_already_above(self):
        self.assertEqual(sessions_needed_to_reach(19, 0, 20, 75), 0)


class AssessmentCalculationTests(SimpleTestCase):
    def test_score_scales_onto_the_component_weight(self):
        # 16/20 on a component worth 10 marks -> 8.00
        self.assertEqual(scaled_score(16, 20, 10), Decimal("8.00"))

    def test_scaling_a_zero_maximum_does_not_divide_by_zero(self):
        self.assertEqual(scaled_score(5, 0, 10), Decimal("0.00"))

    def test_weighted_total_sums_scaled_components(self):
        total = weighted_total([(16, 20, 10), (18, 20, 10), (40, 50, 20)])
        self.assertEqual(total, Decimal("33.00"))

    def test_percentage_of_zero_maximum(self):
        self.assertEqual(percentage(10, 0), Decimal("0.00"))


class GradingTests(SimpleTestCase):
    BANDS = [
        {"letter": "O", "min_percentage": 91, "grade_point": 10, "is_pass": True},
        {"letter": "A", "min_percentage": 71, "grade_point": 8, "is_pass": True},
        {"letter": "P", "min_percentage": 40, "grade_point": 4, "is_pass": True},
        {"letter": "F", "min_percentage": 0, "grade_point": 0, "is_pass": False},
    ]

    def test_highest_matching_band_wins(self):
        self.assertEqual(resolve_grade(95, self.BANDS)["letter"], "O")
        self.assertEqual(resolve_grade(75, self.BANDS)["letter"], "A")
        self.assertEqual(resolve_grade(40, self.BANDS)["letter"], "P")
        self.assertEqual(resolve_grade(10, self.BANDS)["letter"], "F")

    def test_boundary_percentage_is_inclusive(self):
        self.assertEqual(resolve_grade(91, self.BANDS)["letter"], "O")
        self.assertEqual(resolve_grade(90.99, self.BANDS)["letter"], "A")

    def test_gpa_is_credit_weighted(self):
        # (10*4 + 8*3) / 7 = 9.14
        self.assertEqual(grade_point_average([(10, 4), (8, 3)]), Decimal("9.14"))

    def test_gpa_with_no_credits_is_zero(self):
        self.assertEqual(grade_point_average([]), Decimal("0.00"))
        self.assertEqual(grade_point_average([(9, 0)]), Decimal("0.00"))


class TrendTests(SimpleTestCase):
    def test_declining_scores_produce_a_negative_trend(self):
        self.assertLess(linear_trend([80, 78, 60, 55]), 0)

    def test_improving_scores_produce_a_positive_trend(self):
        self.assertGreater(linear_trend([55, 60, 78, 80]), 0)

    def test_single_value_has_no_trend(self):
        self.assertEqual(linear_trend([70]), Decimal("0.00"))


class RiskIndicatorTests(SimpleTestCase):
    """The indicator must stay explainable: score, level and every factor."""

    def test_healthy_student_scores_zero(self):
        outcome = evaluate_risk(
            {
                "attendance_percentage": 92,
                "average_percentage": 78,
                "missed_assignments": 0,
                "score_trend": 3,
                "days_inactive": 1,
            }
        )
        self.assertEqual(outcome["score"], 0)
        self.assertEqual(outcome["level"], "low")
        self.assertEqual(outcome["factors"], [])

    def test_struggling_student_accumulates_weighted_factors(self):
        outcome = evaluate_risk(
            {
                "attendance_percentage": 55,
                "average_percentage": 40,
                "missed_assignments": 3,
                "score_trend": -15,
                "days_inactive": 30,
            }
        )
        self.assertEqual(outcome["score"], 100)
        self.assertEqual(outcome["level"], "critical")
        self.assertEqual(len(outcome["factors"]), 5)

    def test_every_factor_reports_observed_value_and_threshold(self):
        outcome = evaluate_risk({"attendance_percentage": 55})
        factor = outcome["factors"][0]
        for key in ("code", "label", "weight", "metric", "observed", "threshold", "guidance"):
            self.assertIn(key, factor)
        self.assertEqual(factor["observed"], 55)
        self.assertEqual(factor["threshold"], 70)

    def test_missing_metrics_are_skipped_rather_than_assumed(self):
        outcome = evaluate_risk({"attendance_percentage": None, "average_percentage": 40})
        codes = [factor["code"] for factor in outcome["factors"]]
        self.assertNotIn("low_attendance", codes)
        self.assertIn("low_average", codes)

    def test_score_is_capped_at_one_hundred(self):
        rules = [
            {"code": "a", "label": "A", "weight": 80, "metric": "m", "operator": "lt", "threshold": 10},
            {"code": "b", "label": "B", "weight": 80, "metric": "m", "operator": "lt", "threshold": 10},
        ]
        self.assertEqual(evaluate_risk({"m": 1}, rules)["score"], 100)

    def test_administrator_rules_override_the_defaults(self):
        rules = [
            {
                "code": "strict_attendance",
                "label": "Attendance below 90%",
                "weight": 50,
                "metric": "attendance_percentage",
                "operator": "lt",
                "threshold": 90,
                "guidance": "",
            }
        ]
        outcome = evaluate_risk({"attendance_percentage": 85}, rules)
        self.assertEqual(outcome["score"], 50)
        self.assertEqual(outcome["factors"][0]["code"], "strict_attendance")

    def test_disclaimer_is_always_present(self):
        outcome = evaluate_risk({"attendance_percentage": 50})
        self.assertIn("not a prediction", outcome["disclaimer"].lower())
        self.assertEqual(outcome["indicator_name"], "Academic Support Risk Indicator")
