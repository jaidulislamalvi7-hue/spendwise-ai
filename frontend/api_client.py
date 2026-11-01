"""HTTP client for the FastAPI backend.

Streamlit never talks to PostgreSQL. Every data access goes through this client
and therefore through the backend's authorization layer.
"""

from typing import Any

import httpx

from settings import get_settings


class ApiError(Exception):
    """An error returned by the backend or the transport layer."""

    def __init__(self, message: str, status_code: int | None = None, detail: Any = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.detail = detail


class AuthExpiredError(ApiError):
    """Raised when the token is missing, invalid or expired (HTTP 401)."""


def _extract_detail(response: httpx.Response) -> str:
    """Turn a FastAPI error payload into a readable message."""
    try:
        payload = response.json()
    except ValueError:
        return response.text or f"HTTP {response.status_code}"

    detail = payload.get("detail") if isinstance(payload, dict) else payload
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list):
        # Pydantic validation errors: "field: message".
        parts = []
        for item in detail:
            if isinstance(item, dict):
                location = ".".join(str(p) for p in item.get("loc", []) if p != "body")
                parts.append(f"{location}: {item.get('msg', 'invalid value')}".strip(": "))
            else:
                parts.append(str(item))
        return "; ".join(parts) or "Validation failed"
    return str(detail)


class ApiClient:
    """Thin, stateless wrapper around the backend REST API."""

    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ):
        self.base_url = (base_url or get_settings().backend_api_url).rstrip("/")
        self.token = token
        self.timeout = timeout
        # Optional transport injection; tests supply a MockTransport.
        self.transport = transport

    # -- plumbing ---------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = f"{self.base_url}/api{path}"
        try:
            with httpx.Client(timeout=self.timeout, transport=self.transport) as client:
                response = client.request(method, url, headers=self._headers(), **kwargs)
        except httpx.ConnectError as exc:
            raise ApiError(f"Cannot reach the backend at {self.base_url}. Is it running?") from exc
        except httpx.TimeoutException as exc:
            raise ApiError("The backend took too long to respond.") from exc

        if response.status_code == 204:
            return None
        if response.status_code == 401:
            raise AuthExpiredError("Your session has expired. Please sign in again.", 401)
        if response.status_code >= 400:
            raise ApiError(_extract_detail(response), response.status_code, _safe_json(response))
        if not response.content:
            return None
        return response.json()

    # -- auth -------------------------------------------------------------

    def register(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/auth/register", json=payload)

    def login(self, email: str, password: str) -> dict[str, Any]:
        return self._request("POST", "/auth/login", json={"email": email, "password": password})

    def me(self) -> dict[str, Any]:
        return self._request("GET", "/auth/me")

    def update_profile(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("PATCH", "/auth/me", json=payload)

    def change_password(self, current_password: str, new_password: str) -> None:
        self._request(
            "POST",
            "/auth/password",
            json={"current_password": current_password, "new_password": new_password},
        )

    def delete_account(self, password: str) -> None:
        self._request(
            "POST", "/auth/delete-account", json={"password": password, "confirm": "DELETE"}
        )

    # -- export -----------------------------------------------------------

    def _download(self, path: str, **params: Any) -> bytes:
        """Fetch a CSV payload as raw bytes."""
        url = f"{self.base_url}/api{path}"
        try:
            with httpx.Client(timeout=self.timeout, transport=self.transport) as client:
                response = client.get(url, headers=self._headers(), params=params or None)
        except httpx.ConnectError as exc:
            raise ApiError(f"Cannot reach the backend at {self.base_url}.") from exc
        except httpx.TimeoutException as exc:
            raise ApiError("The backend took too long to respond.") from exc
        if response.status_code == 401:
            raise AuthExpiredError("Your session has expired. Please sign in again.", 401)
        if response.status_code >= 400:
            raise ApiError(_extract_detail(response), response.status_code, _safe_json(response))
        return response.content

    def export_expenses_csv(self) -> bytes:
        return self._download("/export/expenses.csv")

    def export_lifestyle_csv(self) -> bytes:
        return self._download("/export/lifestyle.csv")

    # -- budgets ----------------------------------------------------------

    def budgets(self) -> list[dict[str, Any]]:
        return self._request("GET", "/budgets")

    def upsert_budget(self, category: str | None, monthly_limit: float) -> dict[str, Any]:
        payload: dict[str, Any] = {"monthly_limit": f"{monthly_limit:.2f}"}
        if category:
            payload["category"] = category
        return self._request("PUT", "/budgets", json=payload)

    def delete_budget(self, budget_id: str) -> None:
        self._request("DELETE", f"/budgets/{budget_id}")

    def health(self) -> dict[str, Any]:
        url = f"{self.base_url}/health"
        with httpx.Client(timeout=self.timeout, transport=self.transport) as client:
            return client.get(url).json()

    # -- expenses ---------------------------------------------------------

    def list_expenses(
        self,
        date_from: str | None = None,
        date_to: str | None = None,
        category: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if date_from:
            params["date_from"] = date_from
        if date_to:
            params["date_to"] = date_to
        if category:
            params["category"] = category
        return self._request("GET", "/expenses", params=params)

    def create_expense(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/expenses", json=payload)

    def update_expense(self, expense_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("PATCH", f"/expenses/{expense_id}", json=payload)

    def delete_expense(self, expense_id: str) -> None:
        self._request("DELETE", f"/expenses/{expense_id}")

    # -- lifestyle --------------------------------------------------------

    def list_lifestyle(
        self, date_from: str | None = None, date_to: str | None = None, limit: int = 100
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit}
        if date_from:
            params["date_from"] = date_from
        if date_to:
            params["date_to"] = date_to
        return self._request("GET", "/lifestyle-logs", params=params)

    def create_lifestyle(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/lifestyle-logs", json=payload)

    def update_lifestyle(self, log_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("PATCH", f"/lifestyle-logs/{log_id}", json=payload)

    def delete_lifestyle(self, log_id: str) -> None:
        self._request("DELETE", f"/lifestyle-logs/{log_id}")

    # -- analytics --------------------------------------------------------

    def summary(self) -> dict[str, Any]:
        return self._request("GET", "/analytics/summary")

    def categories(self) -> list[dict[str, Any]]:
        return self._request("GET", "/analytics/categories")

    def trends(self, date_from: str | None = None, date_to: str | None = None) -> dict[str, Any]:
        params = {}
        if date_from:
            params["date_from"] = date_from
        if date_to:
            params["date_to"] = date_to
        return self._request("GET", "/analytics/trends", params=params or None)

    def weekday_weekend(self) -> dict[str, Any]:
        return self._request("GET", "/analytics/weekday-weekend")

    def weekday_profile(self) -> list[dict[str, Any]]:
        return self._request("GET", "/analytics/weekday-profile")

    def behaviour(self) -> dict[str, Any]:
        return self._request("GET", "/analytics/behaviour")

    # -- insights ---------------------------------------------------------

    def correlations(self) -> dict[str, Any]:
        return self._request("GET", "/insights/correlations")

    def clusters(self) -> dict[str, Any]:
        return self._request("GET", "/insights/clusters")

    def anomalies(self) -> dict[str, Any]:
        return self._request("GET", "/insights/anomalies")

    # -- predictions and simulation ---------------------------------------

    def prediction_daily(self) -> dict[str, Any]:
        return self._request("GET", "/predictions/daily")

    def prediction_weekly(self) -> dict[str, Any]:
        return self._request("GET", "/predictions/weekly")

    def feature_importance(self) -> dict[str, Any]:
        return self._request("GET", "/predictions/feature-importance")

    def simulate(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/simulation/what-if", json=payload)


def _safe_json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return None
