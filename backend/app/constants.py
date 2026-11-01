"""Centralised constants: categories, currencies, lifestyle enums and limits.

Keeping these in one module means validation, schemas and the database all
reference the same source of truth.
"""

from typing import Final

# --- Currencies -------------------------------------------------------------

# ISO 4217 codes supported by the application (one primary currency per user).
SUPPORTED_CURRENCIES: Final[frozenset[str]] = frozenset(
    {
        "BDT",
        "USD",
        "EUR",
        "GBP",
        "INR",
        "PKR",
        "CAD",
        "AUD",
        "JPY",
        "CNY",
        "SGD",
        "MYR",
        "AED",
        "SAR",
        "CHF",
        "NZD",
        "ZAR",
        "BRL",
    }
)
DEFAULT_CURRENCY: Final[str] = "USD"

# --- Expense categories -----------------------------------------------------

EXPENSE_CATEGORIES: Final[tuple[str, ...]] = (
    "food",
    "groceries",
    "transport",
    "housing",
    "utilities",
    "health",
    "education",
    "entertainment",
    "shopping",
    "travel",
    "personal_care",
    "gifts",
    "subscriptions",
    "other",
)
EXPENSE_CATEGORY_SET: Final[frozenset[str]] = frozenset(EXPENSE_CATEGORIES)

# --- Payment methods --------------------------------------------------------

PAYMENT_METHODS: Final[tuple[str, ...]] = (
    "cash",
    "card",
    "bank_transfer",
    "mobile_wallet",
    "other",
)
PAYMENT_METHOD_SET: Final[frozenset[str]] = frozenset(PAYMENT_METHODS)

# --- Transport modes --------------------------------------------------------

TRANSPORT_MODES: Final[tuple[str, ...]] = (
    "walk",
    "bicycle",
    "bus",
    "train",
    "subway",
    "taxi",
    "ride_share",
    "car",
    "fuel",
    "other",
)
TRANSPORT_MODE_SET: Final[frozenset[str]] = frozenset(TRANSPORT_MODES)

# --- Lifestyle enums --------------------------------------------------------

MEAL_TYPES: Final[tuple[str, ...]] = ("breakfast", "lunch", "dinner", "snack")
MEAL_TYPE_SET: Final[frozenset[str]] = frozenset(MEAL_TYPES)

WORK_MODES: Final[tuple[str, ...]] = ("office", "remote", "hybrid", "travel", "off")
WORK_MODE_SET: Final[frozenset[str]] = frozenset(WORK_MODES)

SHOPPING_ACTIVITY_LEVELS: Final[tuple[str, ...]] = ("none", "small", "major", "online")
SHOPPING_ACTIVITY_SET: Final[frozenset[str]] = frozenset(SHOPPING_ACTIVITY_LEVELS)

# --- Numeric limits ---------------------------------------------------------

STRESS_MIN: Final[int] = 1
STRESS_MAX: Final[int] = 5
MAX_SLEEP_HOURS: Final[int] = 24
MAX_DAILY_COUNT: Final[int] = 50

MIN_AMOUNT: Final[str] = "0.01"
MAX_AMOUNT: Final[str] = "999999999999.99"

APP_AUTHOR: Final[str] = "Jaidul Islam"
