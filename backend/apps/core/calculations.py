"""The academic calculation engine (brief section 79).

Every attendance percentage, weighted score, grade, GPA and risk score in the
platform is computed here - never in a view, a serializer or the frontend.
All thresholds are supplied by configuration, never hard-coded.
"""
from decimal import Decimal, ROUND_HALF_UP

TWO_PLACES = Decimal("0.01")


def _d(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value or 0))


def round2(value) -> Decimal:
    return _d(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------------------
# Attendance
# ---------------------------------------------------------------------------
def attendance_percentage(present: int, late: int, excused: int, total: int) -> Decimal:
    """Attendance % = counted sessions / applicable sessions x 100.

    'Late' counts as attended; 'excused' is removed from the denominator so a
    medically excused student is not penalised.
    """
    applicable = max(int(total) - int(excused), 0)
    if applicable <= 0:
        return Decimal("0.00")
    counted = int(present) + int(late)
    return round2(_d(counted) / _d(applicable) * 100)


def attendance_status(percentage, warning_threshold, critical_threshold) -> str:
    pct = _d(percentage)
    if pct < _d(critical_threshold):
        return "critical"
    if pct < _d(warning_threshold):
        return "warning"
    return "ok"


def sessions_needed_to_reach(present, late, total, target_percentage) -> int:
    """How many consecutive future sessions are needed to reach the target."""
    target = _d(target_percentage) / 100
    counted = _d(int(present) + int(late))
    total_d = _d(total)
    if total_d > 0 and counted / total_d >= target:
        return 0
    if target >= 1:
        return -1  # unreachable without a 100% target being already met
    needed = (target * total_d - counted) / (1 - target)
    return max(int(needed.to_integral_value(rounding=ROUND_HALF_UP)), 0)


# ---------------------------------------------------------------------------
# Assessment
# ---------------------------------------------------------------------------
def scaled_score(obtained, component_max, component_weight) -> Decimal:
    """Scale a raw score onto the component's configured weight."""
    component_max = _d(component_max)
    if component_max <= 0:
        return Decimal("0.00")
    return round2(_d(obtained) / component_max * _d(component_weight))


def weighted_total(component_results) -> Decimal:
    """Sum scaled component scores.

    ``component_results`` is an iterable of ``(obtained, max_marks, weight)``.
    """
    total = Decimal("0.00")
    for obtained, max_marks, weight in component_results:
        total += scaled_score(obtained, max_marks, weight)
    return round2(total)


def percentage(obtained, maximum) -> Decimal:
    maximum = _d(maximum)
    if maximum <= 0:
        return Decimal("0.00")
    return round2(_d(obtained) / maximum * 100)


# ---------------------------------------------------------------------------
# Grading
# ---------------------------------------------------------------------------
def resolve_grade(percent, bands):
    """Map a percentage to a grade using configured bands.

    ``bands`` is an iterable of objects/dicts exposing ``min_percentage``,
    ``letter`` and ``grade_point``. The highest matching band wins.
    """
    percent = _d(percent)
    best = None
    for band in bands:
        minimum = _d(band["min_percentage"] if isinstance(band, dict) else band.min_percentage)
        if percent >= minimum:
            if best is None:
                best = band
            else:
                best_min = _d(
                    best["min_percentage"] if isinstance(best, dict) else best.min_percentage
                )
                if minimum > best_min:
                    best = band
    return best


def grade_point_average(entries) -> Decimal:
    """Credit-weighted GPA. ``entries`` is an iterable of ``(grade_point, credits)``."""
    total_points = Decimal("0")
    total_credits = Decimal("0")
    for grade_point, credits in entries:
        gp, cr = _d(grade_point), _d(credits)
        total_points += gp * cr
        total_credits += cr
    if total_credits <= 0:
        return Decimal("0.00")
    return round2(total_points / total_credits)


#: CGPA is the same credit-weighted mean taken across every completed semester.
cumulative_gpa = grade_point_average


# ---------------------------------------------------------------------------
# Academic Support Risk Indicator (brief sections 31 and 89)
# ---------------------------------------------------------------------------
DEFAULT_RISK_RULES = [
    {
        "code": "low_attendance",
        "label": "Attendance below threshold",
        "weight": 30,
        "metric": "attendance_percentage",
        "operator": "lt",
        "threshold": 70,
        "guidance": "Attendance is below the departmental expectation.",
    },
    {
        "code": "low_average",
        "label": "Average score below threshold",
        "weight": 25,
        "metric": "average_percentage",
        "operator": "lt",
        "threshold": 50,
        "guidance": "Assessment average is below the pass expectation.",
    },
    {
        "code": "missing_assignments",
        "label": "Multiple missing assignments",
        "weight": 20,
        "metric": "missed_assignments",
        "operator": "gte",
        "threshold": 2,
        "guidance": "Two or more assignments have not been submitted.",
    },
    {
        "code": "declining_scores",
        "label": "Recent score decline",
        "weight": 15,
        "metric": "score_trend",
        "operator": "lte",
        "threshold": -10,
        "guidance": "Recent scores are trending downward compared with earlier work.",
    },
    {
        "code": "inactivity",
        "label": "Extended inactivity",
        "weight": 10,
        "metric": "days_inactive",
        "operator": "gte",
        "threshold": 14,
        "guidance": "No platform activity recorded for two weeks or more.",
    },
]

RISK_LEVELS = [
    (75, "critical", "Critical"),
    (50, "high", "High"),
    (25, "moderate", "Moderate"),
    (0, "low", "Low"),
]

OPERATORS = {
    "lt": lambda a, b: a < b,
    "lte": lambda a, b: a <= b,
    "gt": lambda a, b: a > b,
    "gte": lambda a, b: a >= b,
    "eq": lambda a, b: a == b,
}


def evaluate_risk(metrics: dict, rules=None) -> dict:
    """Rule-based, fully explainable academic support risk indicator.

    Returns the score, level and the individual contributing factors so a human
    can always see *why* a student surfaced. This is deliberately not a
    prediction and must never be presented as a diagnosis.
    """
    rules = rules or DEFAULT_RISK_RULES
    score = 0
    factors = []
    for rule in rules:
        metric_value = metrics.get(rule["metric"])
        if metric_value is None:
            continue
        compare = OPERATORS.get(rule.get("operator", "lt"))
        if compare is None:
            continue
        triggered = compare(_d(metric_value), _d(rule["threshold"]))
        if triggered:
            score += int(rule["weight"])
            factors.append(
                {
                    "code": rule["code"],
                    "label": rule["label"],
                    "weight": int(rule["weight"]),
                    "metric": rule["metric"],
                    "observed": float(_d(metric_value)),
                    "threshold": float(_d(rule["threshold"])),
                    "guidance": rule.get("guidance", ""),
                }
            )

    score = min(score, 100)
    level_code, level_label = "low", "Low"
    for minimum, code, label in RISK_LEVELS:
        if score >= minimum:
            level_code, level_label = code, label
            break

    return {
        "score": score,
        "level": level_code,
        "level_label": level_label,
        "factors": factors,
        "indicator_name": "Academic Support Risk Indicator",
        "disclaimer": (
            "This is a rule-based academic support signal intended to prompt human "
            "review. It is not a prediction, a judgement of ability, or any form of "
            "diagnosis."
        ),
    }


def linear_trend(values) -> Decimal:
    """Simple slope proxy: mean of the later half minus mean of the earlier half."""
    values = [_d(v) for v in values if v is not None]
    if len(values) < 2:
        return Decimal("0.00")
    midpoint = len(values) // 2
    earlier = values[:midpoint] or values[:1]
    later = values[midpoint:] or values[-1:]
    mean_earlier = sum(earlier) / _d(len(earlier))
    mean_later = sum(later) / _d(len(later))
    return round2(mean_later - mean_earlier)
