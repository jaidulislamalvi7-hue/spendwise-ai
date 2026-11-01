"""Schemas for analytics, insights, prediction and simulation endpoints."""

from pydantic import BaseModel, Field, model_validator

from app.constants import EXPENSE_CATEGORY_SET

# --- Analytics --------------------------------------------------------------


class SummaryResponse(BaseModel):
    transaction_count: int
    days_recorded: int
    total_spend: float
    average_per_day: float
    average_per_transaction: float
    median_transaction: float
    largest_transaction: float
    date_from: str | None
    date_to: str | None


class CategoryItem(BaseModel):
    category: str
    total: float
    transaction_count: int
    average: float
    percentage: float


class PeriodTotal(BaseModel):
    period: str
    total: float


class TrendsResponse(BaseModel):
    daily: list[PeriodTotal]
    weekly: list[PeriodTotal]
    monthly: list[PeriodTotal]
    trend_direction: str


class WeekdayWeekendResponse(BaseModel):
    weekday_average: float
    weekend_average: float
    weekday_days: int
    weekend_days: int
    difference: float


class WeekdayItem(BaseModel):
    weekday: str
    average: float
    days: int


class BehaviourResponse(BaseModel):
    no_spend_days: int
    average_transactions_per_day: float
    most_frequent_category: str | None
    small_transaction_share: float
    largest_day: dict | None


# --- Insights ---------------------------------------------------------------


class CorrelationItem(BaseModel):
    metric: str
    method: str
    coefficient: float | None
    sample_size: int
    sufficient: bool
    strength: str | None
    direction: str | None
    caution: bool
    caveat: str
    note: str | None = None


class CorrelationResponse(BaseModel):
    results: list[CorrelationItem]
    min_pairs_required: int
    caution_below_pairs: int
    caveat: str


class ClusterItem(BaseModel):
    cluster_id: int
    label: str
    traits: list[str]
    days: int
    average_total: float
    average_transactions: float
    weekend_share: float
    average_largest_transaction: float


class ClusterResponse(BaseModel):
    method: str
    status: str
    days: int
    k: int | None = None
    silhouette: float | None = None
    silhouette_note: str | None = None
    min_days_required: int | None = None
    clusters: list[ClusterItem]
    caveat: str


class AnomalyItem(BaseModel):
    id: str
    expense_date: str
    category: str
    amount: float
    category_median: float | None = None
    robust_z: float | None = None
    reason: str


class AnomalyResponse(BaseModel):
    method: str
    status: str
    checked: int
    flagged: list[AnomalyItem]
    caveat: str


# --- Prediction -------------------------------------------------------------


class PredictionResponse(BaseModel):
    status: str
    message: str | None = None
    days_available: int | None = None
    min_days_required: int | None = None
    days_used: int | None = None
    holdout_days: int | None = None
    method: str | None = None
    method_type: str | None = None
    next_day_forecast: float | None = None
    weekly_forecast: float | None = None
    evaluation: dict | None = None
    model_rejected_reason: str | None = None
    model_skipped_reason: str | None = None
    caveat: str | None = None


class FeatureImportanceItem(BaseModel):
    feature: str
    importance: float


class FeatureImportanceResponse(BaseModel):
    status: str
    features: list[FeatureImportanceItem]
    caveat: str | None = None


# --- Simulation -------------------------------------------------------------


class SimulationRequest(BaseModel):
    """All scenarios are optional; at least one must be supplied."""

    bus_fare: float | None = Field(default=None, ge=0)
    restaurant_reduction_pct: float | None = Field(default=None, ge=0, le=100)
    coffee_reduction_pct: float | None = Field(default=None, ge=0, le=100)
    category: str | None = None
    category_reduction_pct: float | None = Field(default=None, ge=0, le=100)
    recurring_amount: float | None = Field(default=None, gt=0)
    recurring_times_per_month: int = Field(default=1, ge=1, le=31)

    @model_validator(mode="after")
    def _validate_scenarios(self) -> "SimulationRequest":
        if self.category is not None:
            normalized = self.category.strip().lower()
            if normalized not in EXPENSE_CATEGORY_SET:
                raise ValueError(f"unknown category: {self.category}")
            if self.category_reduction_pct is None:
                raise ValueError("category_reduction_pct is required when category is set")
            self.category = normalized
        if self.category_reduction_pct is not None and self.category is None:
            raise ValueError("category is required when category_reduction_pct is set")
        if (
            not any(
                value is not None
                for value in (
                    self.bus_fare,
                    self.restaurant_reduction_pct,
                    self.coffee_reduction_pct,
                    self.recurring_amount,
                )
            )
            and self.category is None
        ):
            raise ValueError("at least one scenario must be provided")
        return self


class SimulationWindow(BaseModel):
    days: int
    date_from: str | None
    date_to: str | None


class SimulationResponse(BaseModel):
    status: str
    window: SimulationWindow
    current: dict
    calculated: list[dict]
    estimated: list[dict]
    estimated_status: str = "unavailable"
    estimated_reason: str | None = None
    caveat: str
