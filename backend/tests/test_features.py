"""Feature engineering and leakage-prevention tests (no database)."""

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from app.ml.features import (
    add_calendar_features,
    add_historical_features,
    add_lifestyle_features,
    add_weekday_baseline_features,
    build_daily_frame,
    build_feature_matrix,
    handle_missing_values,
    is_sufficient_for_features,
    prediction_feature_columns,
)


def _daily(series: list[float], start: date = date(2026, 1, 1)) -> pd.DataFrame:
    index = [start + timedelta(days=i) for i in range(len(series))]
    return pd.DataFrame({"total": series}, index=index)


class TestDailyFrame:
    def test_fills_gaps_between_recorded_days(self) -> None:
        dates = pd.Series([date(2026, 1, 1), date(2026, 1, 4)])
        amounts = pd.Series([10.0, 20.0])
        daily = build_daily_frame(dates, amounts)
        assert len(daily) == 4
        assert daily.loc[date(2026, 1, 2), "total"] == 0.0

    def test_sums_transactions_on_the_same_day(self) -> None:
        dates = pd.Series([date(2026, 1, 1), date(2026, 1, 1)])
        amounts = pd.Series([5.0, 7.5])
        daily = build_daily_frame(dates, amounts)
        assert daily.loc[date(2026, 1, 1), "total"] == 12.5

    def test_empty_input_returns_empty_frame(self) -> None:
        assert build_daily_frame(pd.Series([], dtype=object), pd.Series([], dtype=float)).empty


class TestCalendarFeatures:
    def test_weekend_flag_matches_day_of_week(self) -> None:
        daily = _daily([10.0] * 7, start=date(2026, 1, 5))  # Monday
        result = add_calendar_features(daily)
        assert result["is_weekend"].tolist() == [0, 0, 0, 0, 0, 1, 1]
        assert result["dow"].tolist() == [0, 1, 2, 3, 4, 5, 6]


class TestHistoricalFeatures:
    def test_lag_uses_only_previous_day(self) -> None:
        daily = _daily([10.0, 20.0, 30.0])
        result = add_historical_features(daily)
        assert np.isnan(result["lag_1"].iloc[0])
        assert result["lag_1"].iloc[1] == 10.0
        assert result["lag_1"].iloc[2] == 20.0

    def test_rolling_mean_excludes_current_day(self) -> None:
        # Day three is a huge spike; its own rolling mean must not include it.
        daily = _daily([10.0, 10.0, 1000.0])
        result = add_historical_features(daily)
        assert result["rolling_mean_7"].iloc[2] == pytest.approx(10.0)

    def test_leakage_check_spike_does_not_change_its_own_features(self) -> None:
        # Two series identical except for the final target must produce identical
        # historical features for that final row. A 21-day series gives every
        # lag/rolling/same-weekday feature a finite value at the last row, so the
        # comparison is not vacuous.
        values = [10.0 + (i % 5) for i in range(21)]
        baseline = _daily(values)
        spiked = _daily(values)
        spiked.loc[spiked.index[-1], "total"] = 9999.0

        columns = ["lag_1", "lag_7", "rolling_mean_7", "rolling_mean_14", "same_weekday_mean"]
        left = add_historical_features(add_weekday_baseline_features(baseline))
        right = add_historical_features(add_weekday_baseline_features(spiked))

        finite_compared = 0
        for column in columns:
            a = left[column].iloc[-1]
            b = right[column].iloc[-1]
            if pd.isna(a) and pd.isna(b):
                continue  # undefined in both: unchanged, not evidence of leakage
            assert not pd.isna(a), f"{column} is NaN for the baseline but not the spike"
            assert not pd.isna(b), f"{column} is NaN for the spike but not the baseline"
            assert a == pytest.approx(b), f"{column} changed when only the target changed"
            finite_compared += 1

        # The test must genuinely exercise finite feature values, not only NaNs.
        assert finite_compared >= 4, f"only {finite_compared} finite features compared"

    def test_same_weekday_mean_uses_prior_occurrences(self) -> None:
        # 14 days: two Mondays; the second Monday's mean must be the first Monday.
        values = [0.0] * 14
        values[0] = 50.0
        values[7] = 10.0
        daily = _daily(values, start=date(2026, 1, 5))  # Monday
        result = add_weekday_baseline_features(daily)
        assert np.isnan(result["same_weekday_mean"].iloc[0])
        assert result["same_weekday_mean"].iloc[7] == pytest.approx(50.0)


class TestLifestyleFeatures:
    def test_lifestyle_is_lagged_by_one_day(self) -> None:
        daily = _daily([10.0, 20.0, 30.0])
        lifestyle = pd.DataFrame(
            {
                "log_date": [date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 3)],
                "stress_level": [1, 2, 3],
            }
        )
        result = add_lifestyle_features(daily, lifestyle, lag_days=1)
        assert np.isnan(result["stress_level"].iloc[0])
        assert result["stress_level"].iloc[1] == 1
        assert result["stress_level"].iloc[2] == 2

    def test_lag_zero_is_available_for_descriptive_use(self) -> None:
        daily = _daily([10.0, 20.0])
        lifestyle = pd.DataFrame(
            {"log_date": [date(2026, 1, 1), date(2026, 1, 2)], "stress_level": [4, 5]}
        )
        result = add_lifestyle_features(daily, lifestyle, lag_days=0)
        assert result["stress_level"].iloc[0] == 4


class TestMissingValues:
    def test_leading_gaps_are_filled_without_looking_ahead(self) -> None:
        daily = _daily([10.0, 10.0, 10.0])
        features = handle_missing_values(build_feature_matrix(daily))
        assert features.notna().all().all()

    def test_target_is_never_modified(self) -> None:
        daily = _daily([10.0, 0.0, 5.0])
        features = handle_missing_values(build_feature_matrix(daily))
        assert features["total"].tolist() == daily["total"].tolist()


class TestFeatureContract:
    def test_target_is_not_a_feature_column(self) -> None:
        assert "total" not in prediction_feature_columns()

    def test_all_declared_features_exist_in_matrix(self) -> None:
        features = build_feature_matrix(_daily([10.0] * 20))
        for column in prediction_feature_columns():
            assert column in features.columns

    def test_sufficiency_threshold(self) -> None:
        assert is_sufficient_for_features(_daily([1.0] * 20)) is True
        assert is_sufficient_for_features(_daily([1.0] * 3)) is False
