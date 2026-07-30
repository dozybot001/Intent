"""Deterministic descriptive statistics for benchmark trial rows.

The functions in this module are deliberately independent from the benchmark
runner.  They accept JSON-like row dictionaries, use only the standard
library, and preserve sample counts whenever a statistic cannot be computed.
"""

from fractions import Fraction
from itertools import combinations
import math
from statistics import NormalDist, median


DEFAULT_METRIC_FIELDS = (
    "session_b_elapsed_seconds",
    "handoff_elapsed_seconds",
    "handoff_chars",
    "session_b_input_tokens",
    "session_b_cached_input_tokens",
    "session_b_non_cached_input_tokens",
    "session_b_output_tokens",
    "session_b_reasoning_output_tokens",
)


def analyze_trial_rows(
    rows,
    *,
    success_field="final_ok",
    pair_field="pair_id",
    metric_fields=DEFAULT_METRIC_FIELDS,
    confidence=0.95,
):
    """Summarize condition outcomes and paired binary comparisons.

    A success outcome is considered observed only when ``success_field`` is a
    real boolean.  Missing outcomes, missing pair identifiers, duplicate rows
    within a pair, and incomplete pairs remain visible in the result instead
    of being silently coerced or discarded.
    """
    _validate_confidence(confidence)
    materialized_rows = list(rows)
    fields = tuple(metric_fields)

    grouped = {}
    rows_without_pair_id = 0
    for row in materialized_rows:
        condition = condition_key(row)
        grouped.setdefault(condition, []).append(row)
        if not _has_pair_id(row.get(pair_field)):
            rows_without_pair_id += 1

    condition_stats = {}
    for condition in sorted(grouped):
        condition_rows = grouped[condition]
        outcomes = [
            row.get(success_field)
            for row in condition_rows
            if isinstance(row.get(success_field), bool)
        ]
        passed = sum(outcomes)
        observed = len(outcomes)
        interval = wilson_interval(passed, observed, confidence=confidence)
        condition_stats[condition] = {
            "rows": len(condition_rows),
            "success": {
                "observed": observed,
                "missing": len(condition_rows) - observed,
                "passed": passed,
                "failed": observed - passed,
                "rate": passed / observed if observed else None,
                "wilson_ci": _interval_payload(interval, confidence),
            },
            "metrics": {
                field: summarize_numeric(
                    (row.get(field) for row in condition_rows),
                    expected_count=len(condition_rows),
                )
                for field in fields
            },
        }

    comparisons = [
        _paired_comparison(
            condition_a,
            condition_b,
            grouped,
            success_field=success_field,
            pair_field=pair_field,
        )
        for condition_a, condition_b in combinations(sorted(grouped), 2)
    ]

    return {
        "schema": "intent-benchmark-statistics-v1",
        "row_count": len(materialized_rows),
        "confidence": confidence,
        "success_field": success_field,
        "metric_fields": list(fields),
        "conditions": condition_stats,
        "pairing": {
            "pair_field": pair_field,
            "rows_without_pair_id": rows_without_pair_id,
            "comparisons": comparisons,
        },
    }


def condition_key(row):
    """Return the report label used for a condition and optional ablation."""
    condition = str(row.get("condition") or "(missing)")
    ablation = str(row.get("ablation") or "")
    return f"{condition}:{ablation}" if ablation else condition


def summarize_numeric(values, *, expected_count=None):
    """Return raw finite values plus median and linear-interpolated IQR.

    A single value has a meaningful median but not a meaningful spread for a
    benchmark distribution, so quartiles and IQR are reported as ``None``
    until at least two observations exist.
    """
    observed = sorted(value for value in values if _is_finite_number(value))
    count = len(observed)
    if expected_count is None:
        expected_count = count
    if expected_count < count:
        raise ValueError("expected_count cannot be smaller than observed count")

    result = {
        "count": count,
        "missing": expected_count - count,
        "values": observed,
        "median": median(observed) if observed else None,
        "q1": None,
        "q3": None,
        "iqr": None,
    }
    if count >= 2:
        q1 = _linear_quantile(observed, 0.25)
        q3 = _linear_quantile(observed, 0.75)
        result.update({"q1": q1, "q3": q3, "iqr": q3 - q1})
    return result


def wilson_interval(successes, total, *, confidence=0.95):
    """Return the Wilson score interval as ``(low, high)`` or ``None``."""
    _validate_count(successes, "successes")
    _validate_count(total, "total")
    _validate_confidence(confidence)
    if successes > total:
        raise ValueError("successes cannot exceed total")
    if total == 0:
        return None

    z = NormalDist().inv_cdf(0.5 + confidence / 2)
    rate = successes / total
    z_squared = z * z
    denominator = 1 + z_squared / total
    center = (rate + z_squared / (2 * total)) / denominator
    margin = (
        z
        * math.sqrt(
            rate * (1 - rate) / total
            + z_squared / (4 * total * total)
        )
        / denominator
    )
    return max(0.0, center - margin), min(1.0, center + margin)


def exact_mcnemar_two_sided(condition_a_only, condition_b_only):
    """Return the exact two-sided McNemar p value for discordant pairs.

    With no discordant pairs the exact null result is 1.0.  Callers should
    still report the complete-pair count, because 1.0 can mean either strong
    concordance or simply very little data.
    """
    _validate_count(condition_a_only, "condition_a_only")
    _validate_count(condition_b_only, "condition_b_only")
    discordant = condition_a_only + condition_b_only
    if discordant == 0:
        return 1.0

    smaller = min(condition_a_only, condition_b_only)
    lower_tail_numerator = sum(
        math.comb(discordant, index)
        for index in range(smaller + 1)
    )
    probability = Fraction(2 * lower_tail_numerator, 2**discordant)
    return min(1.0, float(probability))


def exact_mcnemar_one_sided(condition_a_only, condition_b_only):
    """Return P(A-only >= observed) under equal discordant probabilities."""
    _validate_count(condition_a_only, "condition_a_only")
    _validate_count(condition_b_only, "condition_b_only")
    discordant = condition_a_only + condition_b_only
    if discordant == 0:
        return 1.0
    numerator = sum(
        math.comb(discordant, index)
        for index in range(condition_a_only, discordant + 1)
    )
    return float(Fraction(numerator, 2**discordant))


def _paired_comparison(
    condition_a,
    condition_b,
    grouped,
    *,
    success_field,
    pair_field,
):
    rows_a = _rows_by_pair(grouped[condition_a], pair_field)
    rows_b = _rows_by_pair(grouped[condition_b], pair_field)
    pair_ids = set(rows_a) | set(rows_b)

    both_pass = 0
    both_fail = 0
    condition_a_only = 0
    condition_b_only = 0
    missing_condition_pairs = 0
    missing_outcome_pairs = 0
    duplicate_pairs = 0

    for pair_id in pair_ids:
        pair_rows_a = rows_a.get(pair_id, [])
        pair_rows_b = rows_b.get(pair_id, [])
        if len(pair_rows_a) > 1 or len(pair_rows_b) > 1:
            duplicate_pairs += 1
            continue
        if not pair_rows_a or not pair_rows_b:
            missing_condition_pairs += 1
            continue

        outcome_a = pair_rows_a[0].get(success_field)
        outcome_b = pair_rows_b[0].get(success_field)
        if not isinstance(outcome_a, bool) or not isinstance(outcome_b, bool):
            missing_outcome_pairs += 1
            continue
        if outcome_a and outcome_b:
            both_pass += 1
        elif outcome_a:
            condition_a_only += 1
        elif outcome_b:
            condition_b_only += 1
        else:
            both_fail += 1

    complete_pairs = both_pass + both_fail + condition_a_only + condition_b_only
    discordant_pairs = condition_a_only + condition_b_only
    return {
        "condition_a": condition_a,
        "condition_b": condition_b,
        "pairs_seen": len(pair_ids),
        "complete_pairs": complete_pairs,
        "missing_condition_pairs": missing_condition_pairs,
        "missing_outcome_pairs": missing_outcome_pairs,
        "duplicate_pairs": duplicate_pairs,
        "both_pass": both_pass,
        "both_fail": both_fail,
        "condition_a_only_pass": condition_a_only,
        "condition_b_only_pass": condition_b_only,
        "discordant_pairs": discordant_pairs,
        "condition_a_success_rate": (
            (both_pass + condition_a_only) / complete_pairs
            if complete_pairs
            else None
        ),
        "condition_b_success_rate": (
            (both_pass + condition_b_only) / complete_pairs
            if complete_pairs
            else None
        ),
        "success_rate_difference_a_minus_b": (
            (condition_a_only - condition_b_only) / complete_pairs
            if complete_pairs
            else None
        ),
        "mcnemar_exact_two_sided_p": (
            exact_mcnemar_two_sided(condition_a_only, condition_b_only)
            if complete_pairs
            else None
        ),
        "mcnemar_exact_one_sided_p_a_greater": (
            exact_mcnemar_one_sided(condition_a_only, condition_b_only)
            if complete_pairs
            else None
        ),
        "mcnemar_exact_one_sided_p_b_greater": (
            exact_mcnemar_one_sided(condition_b_only, condition_a_only)
            if complete_pairs
            else None
        ),
    }


def _rows_by_pair(rows, pair_field):
    grouped = {}
    for row in rows:
        pair_id = row.get(pair_field)
        if not _has_pair_id(pair_id):
            continue
        grouped.setdefault(pair_id, []).append(row)
    return grouped


def _interval_payload(interval, confidence):
    if interval is None:
        return None
    return {
        "confidence": confidence,
        "low": interval[0],
        "high": interval[1],
    }


def _linear_quantile(sorted_values, probability):
    position = (len(sorted_values) - 1) * probability
    lower_index = math.floor(position)
    upper_index = math.ceil(position)
    lower = sorted_values[lower_index]
    upper = sorted_values[upper_index]
    if lower_index == upper_index:
        return lower
    return lower + (upper - lower) * (position - lower_index)


def _is_finite_number(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _has_pair_id(value):
    return value is not None and value != ""


def _validate_confidence(confidence):
    if (
        not isinstance(confidence, (int, float))
        or isinstance(confidence, bool)
        or not 0 < confidence < 1
    ):
        raise ValueError("confidence must be a number between 0 and 1")


def _validate_count(value, name):
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
