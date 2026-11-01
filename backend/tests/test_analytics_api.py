"""API tests for analytics, insights, prediction and simulation endpoints.

These require PostgreSQL and are skipped when it is unavailable. The ``client``
and ``register_user`` fixtures come from ``tests/conftest.py``.
"""

import pytest
from fastapi.testclient import TestClient

from tests.db_guard import requires_db

pytestmark = requires_db


def _auth(account: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {account['token']}"}


def _add_expenses(client: TestClient, account: dict, days: int = 10) -> None:
    for day in range(1, days + 1):
        client.post(
            "/api/expenses",
            json={
                "amount": str(10 + day),
                "category": "food" if day % 2 else "transport",
                "expense_date": f"2026-01-{day:02d}",
            },
            headers=_auth(account),
        )


ANALYTICS_ENDPOINTS = (
    "/api/analytics/summary",
    "/api/analytics/categories",
    "/api/analytics/trends",
    "/api/analytics/weekday-weekend",
    "/api/analytics/weekday-profile",
    "/api/analytics/behaviour",
    "/api/insights/correlations",
    "/api/insights/clusters",
    "/api/insights/anomalies",
    "/api/predictions/daily",
    "/api/predictions/weekly",
    "/api/predictions/feature-importance",
)


@pytest.mark.parametrize("endpoint", ANALYTICS_ENDPOINTS)
def test_endpoint_requires_authentication(client: TestClient, endpoint: str) -> None:
    assert client.get(endpoint).status_code == 401


@pytest.mark.parametrize("endpoint", ANALYTICS_ENDPOINTS)
def test_endpoint_works_for_new_user(client: TestClient, register_user, endpoint: str) -> None:
    account = register_user()
    response = client.get(endpoint, headers=_auth(account))
    assert response.status_code == 200, response.text


def test_summary_reflects_only_own_expenses(client: TestClient, register_user) -> None:
    owner = register_user()
    _add_expenses(client, owner, days=5)

    other = register_user()
    response = client.get("/api/analytics/summary", headers=_auth(other))
    assert response.json()["transaction_count"] == 0
    assert response.json()["total_spend"] == 0.0


def test_categories_isolated_between_users(client: TestClient, register_user) -> None:
    owner = register_user()
    _add_expenses(client, owner, days=4)

    other = register_user()
    assert client.get("/api/analytics/categories", headers=_auth(other)).json() == []


def test_anomalies_isolated_between_users(client: TestClient, register_user) -> None:
    owner = register_user()
    _add_expenses(client, owner, days=8)
    other = register_user()
    payload = client.get("/api/insights/anomalies", headers=_auth(other)).json()
    assert payload["flagged"] == []


def test_correlation_suppressed_for_new_user(client: TestClient, register_user) -> None:
    account = register_user()
    payload = client.get("/api/insights/correlations", headers=_auth(account)).json()
    assert payload["results"] == []


def test_prediction_insufficient_for_new_user(client: TestClient, register_user) -> None:
    account = register_user()
    payload = client.get("/api/predictions/daily", headers=_auth(account)).json()
    assert payload["status"] == "insufficient_data"


def test_simulation_requires_a_scenario(client: TestClient, register_user) -> None:
    account = register_user()
    response = client.post("/api/simulation/what-if", json={}, headers=_auth(account))
    assert response.status_code == 422


def test_simulation_what_if(client: TestClient, register_user) -> None:
    account = register_user()
    client.post(
        "/api/expenses",
        json={
            "amount": "100.00",
            "category": "transport",
            "expense_date": "2026-01-01",
            "transport_mode": "taxi",
        },
        headers=_auth(account),
    )
    response = client.post(
        "/api/simulation/what-if", json={"bus_fare": 10.0}, headers=_auth(account)
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["calculated"][0]["classification"] == "calculated"
    assert body["calculated"][0]["difference"] == 90.0
    # Estimates are explicitly reported as unavailable, never implied.
    assert body["estimated_status"] == "unavailable"
    assert body["estimated_reason"]


def test_simulation_isolated_between_users(client: TestClient, register_user) -> None:
    owner = register_user()
    client.post(
        "/api/expenses",
        json={
            "amount": "100.00",
            "category": "transport",
            "expense_date": "2026-01-01",
            "transport_mode": "taxi",
        },
        headers=_auth(owner),
    )
    other = register_user()
    body = client.post(
        "/api/simulation/what-if", json={"bus_fare": 10.0}, headers=_auth(other)
    ).json()
    assert body["status"] == "insufficient_data"
