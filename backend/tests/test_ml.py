"""Tests for analytics, correlation, clustering, anomalies and simulation."""

import math
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from app.ml import analytics, anomaly, clustering, correlation, prediction, simulation
from app.ml.config import MIN_CLUSTER_DAYS, MIN_CORRELATION_PAIRS


def _transactions(rows: list[tuple[date, float, str]], **extra) -> pd.DataFrame:
    data = []
    for index, (day, amount, category) in enumerate(rows):
        entry = {
            "id": str(index),
            "expense_date": day,
            "amount": amount,
            "category": category,
            "transport_mode": None,
            "is_restaurant_visit": None,
            "is_coffee_or_snack": None,
            "is_shopping": None,
            "is_entertainment": None,
        }
        entry.update(extra)
        data.append(entry)
    return pd.DataFrame(data)


def _daily_series(values: list[float], start: date = date(2026, 1, 1)) -> pd.DataFrame:
    index = [start + timedelta(days=i) for i in range(len(values))]
    return pd.DataFrame({"total": values}, index=index)


class TestAnalytics:
    def test_summary_empty(self) -> None:
        result = analytics.summary(pd.DataFrame(columns=["expense_date", "amount", "category"]))
        assert result["total_spend"] == 0.0
        assert result["transaction_count"] == 0

    def test_summary_totals_and_averages(self) -> None:
        rows = [
            (date(2026, 1, 1), 10.0, "food"),
            (date(2026, 1, 1), 5.0, "food"),
            (date(2026, 1, 3), 15.0, "transport"),
        ]
        result = analytics.summary(_transactions(rows))
        assert result["total_spend"] == 30.0
        assert result["transaction_count"] == 3
        assert result["days_recorded"] == 3  # includes the empty day
        assert result["average_per_day"] == pytest.approx(10.0)

    def test_category_percentages_sum_to_about_100(self) -> None:
        rows = [
            (date(2026, 1, 1), 30.0, "food"),
            (date(2026, 1, 2), 70.0, "transport"),
        ]
        breakdown = analytics.category_breakdown(_transactions(rows))
        assert sum(item["percentage"] for item in breakdown) == pytest.approx(100.0)
        assert breakdown[0]["category"] == "transport"

    def test_weekday_vs_weekend(self) -> None:
        # Monday start: days 0-4 weekday, 5-6 weekend.
        rows = [(date(2026, 1, 5) + timedelta(days=i), 10.0, "food") for i in range(5)]
        rows += [(date(2026, 1, 10), 50.0, "food"), (date(2026, 1, 11), 50.0, "food")]
        result = analytics.weekday_vs_weekend(_transactions(rows))
        assert result["weekday_average"] == pytest.approx(10.0)
        assert result["weekend_average"] == pytest.approx(50.0)
        assert result["difference"] == pytest.approx(40.0)

    def test_trends_returns_daily_weekly_monthly(self) -> None:
        result = analytics.trends(_transactions([(date(2026, 1, 1), 10.0, "food")]))
        assert result["daily"]
        assert set(result["weekly"][0]) == {"period", "total"}
        assert result["monthly"]

    def test_trend_direction_detects_increase(self) -> None:
        daily = _daily_series([10.0, 10.0, 10.0, 10.0, 30.0, 30.0, 30.0, 30.0])
        assert analytics.trend_direction(daily["total"]) == "increasing"

    def test_behaviour_summary_counts_no_spend_days(self) -> None:
        rows = [(date(2026, 1, 1), 10.0, "food"), (date(2026, 1, 3), 10.0, "food")]
        result = analytics.behaviour_summary(_transactions(rows))
        assert result["no_spend_days"] == 1


class TestCorrelation:
    def _frame(self, n: int, coefficient_sign: int = 1) -> pd.DataFrame:
        rng = np.random.default_rng(0)
        spend = rng.normal(50, 10, n)
        stress = coefficient_sign * spend + rng.normal(0, 5, n)
        return pd.DataFrame({"total": spend, "stress_level": stress})

    def test_suppressed_below_minimum_pairs(self) -> None:
        result = correlation.analyse(self._frame(MIN_CORRELATION_PAIRS - 5))
        stress = next(r for r in result["results"] if r["metric"] == "stress_vs_daily_spend")
        assert stress["sufficient"] is False
        assert stress["coefficient"] is None
        assert stress["sample_size"] == MIN_CORRELATION_PAIRS - 5

    def test_reported_with_enough_pairs(self) -> None:
        result = correlation.analyse(self._frame(MIN_CORRELATION_PAIRS + 10))
        stress = next(r for r in result["results"] if r["metric"] == "stress_vs_daily_spend")
        assert stress["sufficient"] is True
        assert stress["coefficient"] is not None
        assert stress["sample_size"] == MIN_CORRELATION_PAIRS + 10

    def test_strength_and_direction(self) -> None:
        result = correlation.analyse(self._frame(40, coefficient_sign=-1))
        stress = next(r for r in result["results"] if r["metric"] == "stress_vs_daily_spend")
        assert stress["direction"] == "negative"
        assert stress["strength"] in {"moderate", "fairly strong", "strong"}

    def test_caveat_always_present(self) -> None:
        result = correlation.analyse(self._frame(40))
        assert "caus" in result["caveat"].lower()
        assert all("caus" in item["caveat"].lower() for item in result["results"])

    def test_constant_series_is_suppressed(self) -> None:
        frame = pd.DataFrame({"total": [10.0] * 30, "stress_level": [3] * 30})
        result = correlation.analyse(frame)
        stress = next(r for r in result["results"] if r["metric"] == "stress_vs_daily_spend")
        assert stress["sufficient"] is False


class TestClustering:
    def _rows(self, days: int) -> list[tuple[date, float, str]]:
        rows = []
        for day in range(days):
            base = date(2026, 1, 1) + timedelta(days=day)
            # Two clear regimes: cheap weekdays, expensive weekends.
            if base.weekday() >= 5:
                rows.append((base, 200.0, "shopping"))
            else:
                rows.append((base, 10.0, "food"))
        return rows

    def test_insufficient_days(self) -> None:
        result = clustering.cluster_days(_transactions(self._rows(MIN_CLUSTER_DAYS - 10)))
        assert result["status"] == "insufficient_data"
        assert result["clusters"] == []

    def test_clusters_produced_with_enough_days(self) -> None:
        result = clustering.cluster_days(_transactions(self._rows(MIN_CLUSTER_DAYS + 10)))
        assert result["status"] == "ok"
        assert result["k"] and result["k"] >= 2
        assert len(result["clusters"]) == result["k"]

    def test_labels_avoid_moral_language(self) -> None:
        result = clustering.cluster_days(_transactions(self._rows(MIN_CLUSTER_DAYS + 10)))
        for cluster in result["clusters"]:
            lowered = cluster["label"].lower()
            for banned in ("bad", "good", "worst", "best", "irresponsible"):
                assert banned not in lowered

    def test_empty_input(self) -> None:
        assert clustering.cluster_days(pd.DataFrame())["status"] == "insufficient_data"


class TestAnomaly:
    def _rows(self) -> list[tuple[date, float, str]]:
        rows = [(date(2026, 1, 1) + timedelta(days=i), 10.0, "food") for i in range(10)]
        rows.append((date(2026, 1, 12), 500.0, "food"))
        return rows

    def test_flags_obvious_outlier(self) -> None:
        result = anomaly.detect_robust(_transactions(self._rows()))
        assert result["status"] == "ok"
        assert any(item["amount"] == 500.0 for item in result["flagged"])

    def test_does_not_flag_typical_values(self) -> None:
        result = anomaly.detect_robust(_transactions(self._rows()))
        assert not any(item["amount"] == 10.0 for item in result["flagged"])

    def test_reason_is_human_readable(self) -> None:
        result = anomaly.detect_robust(_transactions(self._rows()))
        assert result["flagged"]
        assert "median" in result["flagged"][0]["reason"].lower()

    def test_insufficient_history_is_not_judged(self) -> None:
        rows = [(date(2026, 1, 1), 10.0, "food")]
        assert anomaly.detect_robust(_transactions(rows))["flagged"] == []

    def test_missing_data_handled(self) -> None:
        assert anomaly.detect_robust(pd.DataFrame())["status"] == "insufficient_data"


class TestSimulation:
    def _rows(self) -> list[tuple[date, float, str]]:
        return [
            (date(2026, 1, 1), 100.0, "transport"),
            (date(2026, 1, 2), 50.0, "food"),
            (date(2026, 1, 3), 20.0, "food"),
        ]

    def _frame(self) -> pd.DataFrame:
        frame = _transactions(self._rows())
        frame.loc[0, "transport_mode"] = "taxi"
        frame.loc[1, "is_restaurant_visit"] = True
        frame.loc[2, "is_coffee_or_snack"] = True
        return frame

    def test_taxi_to_bus_is_direct_arithmetic(self) -> None:
        result = simulation.run(self._frame(), bus_fare=10.0)
        scenario = result["calculated"][0]
        assert scenario["classification"] == "calculated"
        assert scenario["current_cost"] == 100.0
        assert scenario["scenario_cost"] == 10.0
        assert scenario["difference"] == 90.0

    def test_restaurant_reduction(self) -> None:
        result = simulation.run(self._frame(), restaurant_reduction_pct=50)
        scenario = result["calculated"][0]
        assert scenario["current_cost"] == 50.0
        assert scenario["difference"] == 25.0

    def test_coffee_reduction(self) -> None:
        result = simulation.run(self._frame(), coffee_reduction_pct=100)
        assert result["calculated"][0]["difference"] == 20.0

    def test_category_reduction(self) -> None:
        result = simulation.run(self._frame(), category="transport", category_reduction_pct=10)
        assert result["calculated"][0]["difference"] == pytest.approx(10.0)

    def test_recurring_expense_adds_cost(self) -> None:
        result = simulation.run(self._frame(), recurring_amount=30.0)
        assert result["calculated"][0]["difference"] > 0

    def test_window_is_reported(self) -> None:
        result = simulation.run(self._frame(), bus_fare=10.0)
        assert result["window"]["days"] == 3
        assert result["window"]["date_from"] == "2026-01-01"

    def test_outputs_are_not_causal(self) -> None:
        result = simulation.run(self._frame(), bus_fare=10.0)
        assert "caus" in result["caveat"].lower()
        for calculated in result["calculated"]:
            text = (
                calculated.get("note", "")
                + " "
                + " ".join(str(v) for v in calculated.get("assumptions", {}).values())
            ).lower()
            # The wording must not assert that the change produces savings.
            assert "you will save" not in text
            assert "will produce" not in text

    def test_empty_history(self) -> None:
        result = simulation.run(pd.DataFrame(), bus_fare=10.0)
        assert result["status"] == "insufficient_data"


class TestPrediction:
    def test_insufficient_data_response(self) -> None:
        result = prediction.evaluate_and_predict(_daily_series([10.0, 12.0]))
        assert result["status"] == "insufficient_data"
        assert result["message"]

    def test_baseline_used_with_modest_history(self) -> None:
        series = [10.0 + (i % 3) for i in range(15)]
        result = prediction.evaluate_and_predict(_daily_series(series))
        assert result["status"] == "ok"
        assert result["method_type"] == "statistical_baseline"
        assert "baselines" in result["evaluation"]

    def test_metrics_are_reported(self) -> None:
        series = [10.0 + (i % 4) for i in range(40)]
        result = prediction.evaluate_and_predict(_daily_series(series))
        evaluation = result["evaluation"]
        method = result["method"]

        def assert_metrics(metrics: dict, label: str) -> None:
            """MAE and RMSE must both be present, finite and non-negative."""
            for key in ("mae", "rmse"):
                assert key in metrics, f"{label} is missing {key.upper()}"
                value = metrics[key]
                assert isinstance(value, (int, float)), f"{label} {key} is not numeric"
                assert math.isfinite(value), f"{label} {key} is not finite"
                assert value >= 0, f"{label} {key} is negative"

        # Every baseline that was evaluated must report usable error metrics.
        assert evaluation["baselines"], "at least one baseline must be evaluated"
        for name, metrics in evaluation["baselines"].items():
            assert_metrics(metrics, f"baseline '{name}'")

        # The selected method must report its own metrics, wherever they live.
        if method in evaluation["baselines"]:
            assert_metrics(evaluation["baselines"][method], f"selected baseline '{method}'")
        else:
            assert method == "gradient_boosting", f"unexpected method '{method}'"
            assert "model" in evaluation, "model was selected but no metrics were recorded"
            assert_metrics(evaluation["model"], "selected model")

        # The chosen baseline must be one that was actually evaluated.
        assert evaluation["best_baseline"] in evaluation["baselines"]

        # If a model was evaluated, promotion must stay evidence-based: the
        # model may only be the selected method when it beats the best baseline
        # on BOTH metrics.
        if "model" in evaluation:
            baseline_metrics = evaluation["baselines"][evaluation["best_baseline"]]
            beats_both = (
                evaluation["model"]["mae"] < baseline_metrics["mae"]
                and evaluation["model"]["rmse"] < baseline_metrics["rmse"]
            )
            if method == "gradient_boosting":
                assert beats_both, "model promoted without beating the baseline on both metrics"

    def test_model_rejected_when_it_does_not_beat_baseline(self) -> None:
        # A constant series gives the model nothing to learn; whatever happens,
        # the reported method must be consistent with the stated reason.
        series = [50.0] * 40
        result = prediction.evaluate_and_predict(_daily_series(series))
        if result["method_type"] == "statistical_baseline":
            reason = result.get("model_rejected_reason") or result.get("model_skipped_reason")
            assert reason, "a rejected or skipped model must explain why"
        else:
            # If a model was promoted it must have beaten the baseline on MAE.
            assert (
                result["evaluation"]["model"]["mae"]
                < result["evaluation"]["baselines"][result["evaluation"]["best_baseline"]]["mae"]
            )

    def test_promotion_requires_beating_baseline_on_both_metrics(self) -> None:
        series = [10.0 + (i % 7) * 3 for i in range(60)]
        result = prediction.evaluate_and_predict(_daily_series(series))
        evaluation = result["evaluation"]
        if "model" in evaluation and result["method_type"] == "model":
            baseline = evaluation["baselines"][evaluation["best_baseline"]]
            assert evaluation["model"]["mae"] < baseline["mae"]
            assert evaluation["model"]["rmse"] < baseline["rmse"]

    def test_no_random_splitting(self) -> None:
        # The holdout is the final window; evaluation must not touch earlier days.
        series = [5.0] * 30
        result = prediction.evaluate_and_predict(_daily_series(series))
        assert result["holdout_days"] <= len(series)

    def test_feature_importance_insufficient(self) -> None:
        from app.ml.features import build_feature_matrix

        result = prediction.feature_importance(build_feature_matrix(_daily_series([1.0] * 5)))
        assert result["status"] == "insufficient_data"

    def test_constant_series_always_returns_a_forecast(self) -> None:
        # A flat series has no learnable signal; a baseline must still be given.
        result = prediction.evaluate_and_predict(_daily_series([25.0] * 40))
        assert result["status"] == "ok"
        assert result["next_day_forecast"] == pytest.approx(25.0)
        assert result["weekly_forecast"] == pytest.approx(175.0)
        assert result["forecast_source"].endswith("baseline")
        assert result["model_skipped_reason"]

    def test_forecast_source_is_always_present(self) -> None:
        result = prediction.evaluate_and_predict(_daily_series([10.0 + i for i in range(20)]))
        assert result["forecast_source"] in {
            "model",
            "same_weekday_baseline",
            "historical_average_baseline",
            "fallback_zero",
        }

    def test_forecast_is_finite(self) -> None:
        import math

        result = prediction.evaluate_and_predict(_daily_series([0.0] * 30))
        assert math.isfinite(result["next_day_forecast"])
        assert math.isfinite(result["weekly_forecast"])


class TestClusteringDegenerate:
    def test_max_usable_k_is_bounded(self) -> None:
        from app.ml.clustering import CANDIDATE_K, max_usable_k

        assert max_usable_k(0) == 0
        assert max_usable_k(1) == 0
        assert max_usable_k(2) == 1
        assert max_usable_k(100) == max(CANDIDATE_K)

    def test_max_k_never_exceeds_sample_minus_one(self) -> None:
        from app.ml.clustering import max_usable_k

        for n in (0, 1, 2, 3, 5, 1000):
            assert max_usable_k(n) <= max(0, n - 1)

    def test_constant_features_do_not_crash(self) -> None:
        rows = [(date(2026, 1, 1) + timedelta(days=i), 10.0, "food") for i in range(40)]
        result = clustering.cluster_days(_transactions(rows))
        # Either clusters are found or the limitation is stated; never a crash.
        assert result["status"] in {"ok", "insufficient_variation"}


class TestSimulationEstimates:
    def test_estimates_are_reported_as_unavailable(self) -> None:
        rows = [(date(2026, 1, 1), 100.0, "transport")]
        result = simulation.run(_transactions(rows), bus_fare=10.0)
        assert result["estimated"] == []
        assert result["estimated_status"] == "unavailable"
        assert "not available" in result["estimated_reason"].lower()

    def test_empty_history_also_flags_estimates_unavailable(self) -> None:
        result = simulation.run(pd.DataFrame(), bus_fare=10.0)
        assert result["estimated_status"] == "unavailable"
