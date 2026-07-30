import pytest

from intent_cli.benchmark.statistics import (
    analyze_trial_rows,
    exact_mcnemar_one_sided,
    exact_mcnemar_two_sided,
    summarize_numeric,
    wilson_interval,
)


def test_wilson_interval_reports_uncertainty_and_handles_no_observations():
    assert wilson_interval(0, 0) is None

    low, high = wilson_interval(5, 10)
    assert low == pytest.approx(0.236593, abs=1e-6)
    assert high == pytest.approx(0.763407, abs=1e-6)


def test_numeric_summary_preserves_values_and_does_not_invent_single_sample_spread():
    summary = summarize_numeric([4, None, 1, float("nan"), 3, 2], expected_count=6)

    assert summary == {
        "count": 4,
        "missing": 2,
        "values": [1, 2, 3, 4],
        "median": 2.5,
        "q1": 1.75,
        "q3": 3.25,
        "iqr": 1.5,
    }

    one = summarize_numeric([7], expected_count=2)
    assert one["count"] == 1
    assert one["missing"] == 1
    assert one["median"] == 7
    assert one["q1"] is None
    assert one["q3"] is None
    assert one["iqr"] is None


def test_condition_summary_counts_missing_success_and_numeric_data():
    rows = [
        {
            "condition": "intent-full",
            "final_ok": True,
            "session_b_elapsed_seconds": 10,
            "handoff_chars": 500,
        },
        {
            "condition": "intent-full",
            "final_ok": False,
            "session_b_elapsed_seconds": 20,
            "handoff_chars": None,
        },
        {
            "condition": "intent-full",
            "final_ok": None,
            "session_b_elapsed_seconds": None,
            "handoff_chars": 700,
        },
    ]

    result = analyze_trial_rows(rows)
    condition = result["conditions"]["intent-full"]

    assert result["row_count"] == 3
    assert condition["success"]["observed"] == 2
    assert condition["success"]["missing"] == 1
    assert condition["success"]["passed"] == 1
    assert condition["success"]["failed"] == 1
    assert condition["success"]["rate"] == 0.5
    assert condition["success"]["wilson_ci"] is not None
    assert condition["metrics"]["session_b_elapsed_seconds"]["median"] == 15
    assert condition["metrics"]["session_b_elapsed_seconds"]["missing"] == 1
    assert condition["metrics"]["handoff_chars"]["values"] == [500, 700]
    assert result["pairing"]["rows_without_pair_id"] == 3


def test_paired_comparison_reports_concordance_discordance_and_exclusions():
    rows = [
        _row("p1", "git-only", True),
        _row("p1", "intent-full", True),
        _row("p2", "git-only", True),
        _row("p2", "intent-full", False),
        _row("p3", "git-only", False),
        _row("p3", "intent-full", True),
        _row("p4", "git-only", False),
        _row("p4", "intent-full", False),
        _row("p5", "git-only", True),
        _row("p6", "git-only", None),
        _row("p6", "intent-full", True),
        _row("p7", "git-only", True),
        _row("p7", "git-only", False),
        _row("p7", "intent-full", True),
    ]

    comparison = analyze_trial_rows(rows)["pairing"]["comparisons"][0]

    assert comparison["condition_a"] == "git-only"
    assert comparison["condition_b"] == "intent-full"
    assert comparison["pairs_seen"] == 7
    assert comparison["complete_pairs"] == 4
    assert comparison["missing_condition_pairs"] == 1
    assert comparison["missing_outcome_pairs"] == 1
    assert comparison["duplicate_pairs"] == 1
    assert comparison["both_pass"] == 1
    assert comparison["both_fail"] == 1
    assert comparison["condition_a_only_pass"] == 1
    assert comparison["condition_b_only_pass"] == 1
    assert comparison["success_rate_difference_a_minus_b"] == 0
    assert comparison["mcnemar_exact_two_sided_p"] == 1.0


def test_pairwise_statistics_return_null_when_no_complete_pair_exists():
    rows = [
        _row("p1", "git-only", True),
        _row("p2", "intent-full", False),
    ]

    comparison = analyze_trial_rows(rows)["pairing"]["comparisons"][0]

    assert comparison["complete_pairs"] == 0
    assert comparison["missing_condition_pairs"] == 2
    assert comparison["success_rate_difference_a_minus_b"] is None
    assert comparison["mcnemar_exact_two_sided_p"] is None


def test_exact_mcnemar_matches_exact_two_sided_binomial_tail():
    assert exact_mcnemar_two_sided(0, 0) == 1.0
    assert exact_mcnemar_two_sided(8, 2) == pytest.approx(0.109375)
    assert exact_mcnemar_two_sided(10, 0) == pytest.approx(0.001953125)


def test_exact_mcnemar_one_sided_matches_preregistered_direction():
    assert exact_mcnemar_one_sided(0, 0) == 1.0
    assert exact_mcnemar_one_sided(6, 0) == pytest.approx(1 / 64)
    assert exact_mcnemar_one_sided(0, 6) == 1.0


def test_ablation_is_part_of_the_condition_label():
    result = analyze_trial_rows([
        {
            "condition": "intent-full",
            "ablation": "no-decision",
            "final_ok": False,
        }
    ])

    assert list(result["conditions"]) == ["intent-full:no-decision"]


def test_invalid_counts_and_confidence_are_rejected():
    with pytest.raises(ValueError):
        wilson_interval(2, 1)
    with pytest.raises(ValueError):
        exact_mcnemar_two_sided(-1, 2)
    with pytest.raises(ValueError):
        exact_mcnemar_one_sided(1, -1)
    with pytest.raises(ValueError):
        analyze_trial_rows([], confidence=1)


def _row(pair_id, condition, final_ok):
    return {
        "pair_id": pair_id,
        "condition": condition,
        "final_ok": final_ok,
    }
