"""Frontend-level constants shared across Streamlit pages."""

APP_NAME = "SpendWise AI"
APP_TAGLINE = "Personal Expense & Lifestyle Intelligence System"
APP_AUTHOR = "Jaidul Islam"

FOOTER_TEXT = f"{APP_NAME} \u2014 Developed by {APP_AUTHOR}"

# Categories mirror the backend's central list (app/constants.py).
EXPENSE_CATEGORIES = (
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

PAYMENT_METHODS = ("cash", "card", "bank_transfer", "mobile_wallet", "other")

# Must stay in sync with backend/app/constants.py SUPPORTED_CURRENCIES.
SUPPORTED_CURRENCIES = (
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
)
TRANSPORT_MODES = (
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
MEAL_TYPES = ("breakfast", "lunch", "dinner", "snack")
WORK_MODES = ("office", "remote", "hybrid", "travel", "off")
SHOPPING_ACTIVITIES = ("none", "small", "major", "online")

CATEGORY_COLORS = {
    "food": "#ef4444",
    "groceries": "#f97316",
    "transport": "#3b82f6",
    "housing": "#8b5cf6",
    "utilities": "#06b6d4",
    "health": "#10b981",
    "education": "#6366f1",
    "entertainment": "#ec4899",
    "shopping": "#f59e0b",
    "travel": "#14b8a6",
    "personal_care": "#a855f7",
    "gifts": "#e11d48",
    "subscriptions": "#0ea5e9",
    "other": "#6b7280",
}
