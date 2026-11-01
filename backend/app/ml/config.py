"""ML configuration: thresholds, caveats and shared wording.

Thresholds are initial heuristics, not statistical guarantees. They decide what
may be *attempted*, never what is claimed.
"""

from typing import Final

# --- Minimum sample sizes ---------------------------------------------------

MIN_CORRELATION_PAIRS: Final[int] = 14
CORRELATION_CAUTION_PAIRS: Final[int] = 30
MIN_CLUSTER_DAYS: Final[int] = 30
MIN_DAYS_FOR_FEATURES: Final[int] = 14

# Prediction: heuristics that gate what can be attempted.
MIN_DAYS_FOR_BASELINE: Final[int] = 7
MIN_DAYS_FOR_MODEL: Final[int] = 28
# A model is only promoted when it is evaluated on at least this many held-out days.
MIN_EVALUATION_DAYS: Final[int] = 7

# --- Anomaly detection ------------------------------------------------------

# Robust z-score threshold; values beyond this are flagged as unusual.
ANOMALY_MAD_THRESHOLD: Final[float] = 3.5
# When MAD is zero (most values identical) a z-score is undefined; a value this
# far above the median (as a fraction of it) is still treated as unusual.
ANOMALY_ZERO_MAD_MARGIN: Final[float] = 1.0
MIN_ANOMALY_HISTORY: Final[int] = 5

# --- Correlation strength bands (|r|) ---------------------------------------

CORRELATION_WEAK: Final[float] = 0.3
CORRELATION_MODERATE: Final[float] = 0.5
CORRELATION_STRONG: Final[float] = 0.7

# --- Shared caveats ---------------------------------------------------------

CORRELATION_CAVEAT: Final[str] = (
    "Association only. A correlation does not show that one factor causes the other; "
    "both may be driven by something else entirely."
)
IMPORTANCE_CAVEAT: Final[str] = (
    "Feature importance describes how much this model used a feature, not a causal "
    "effect in the real world."
)
ANOMALY_CAVEAT: Final[str] = (
    "Flagged as unusual relative to this user's own history. Unusual is not the same "
    "as wrong or important."
)
SIMULATION_CAVEAT: Final[str] = (
    "Scenarios are arithmetic on recorded spending, not evidence that a change would "
    "produce these savings. No causal claim is made."
)
