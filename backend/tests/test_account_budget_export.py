"""API tests for account settings, data export and budgets.

Requires PostgreSQL; skipped automatically when the test database is
unreachable. Uses the shared ``client`` fixture from conftest.
"""

import csv
import io
import uuid

from fastapi.testclient import TestClient

from tests.db_guard import requires_db

pytestmark = requires_db


def _account(client: TestClient, currency: str = "USD", tz: str = "UTC") -> dict:
    """Register and log in a fresh user; return token and credentials."""
    payload = {
        "email": f"acct-{uuid.uuid4().hex[:10]}@example.com",
        "password": "supersecret123",
        "primary_currency": currency,
        "timezone": tz,
    }
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 201, response.text
    token = client.post(
        "/api/auth/login", json={"email": payload["email"], "password": payload["password"]}
    ).json()["access_token"]
    return {"token": token, "email": payload["email"], "password": payload["password"]}


def _auth(account: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {account['token']}"}


def _add_expense(client: TestClient, account: dict, amount: str = "12.50", category="food") -> dict:
    response = client.post(
        "/api/expenses",
        json={"amount": amount, "category": category, "expense_date": "2026-10-30"},
        headers=_auth(account),
    )
    assert response.status_code == 201, response.text
    return response.json()


class TestProfileSettings:
    def test_update_display_name(self, client: TestClient) -> None:
        account = _account(client)
        response = client.patch(
            "/api/auth/me", json={"display_name": "Alex"}, headers=_auth(account)
        )
        assert response.status_code == 200
        assert response.json()["display_name"] == "Alex"

    def test_update_currency(self, client: TestClient) -> None:
        account = _account(client)
        response = client.patch(
            "/api/auth/me", json={"primary_currency": "bdt"}, headers=_auth(account)
        )
        assert response.json()["primary_currency"] == "BDT"

    def test_invalid_currency_is_rejected(self, client: TestClient) -> None:
        account = _account(client)
        response = client.patch(
            "/api/auth/me", json={"primary_currency": "XXX"}, headers=_auth(account)
        )
        assert response.status_code == 422

    def test_invalid_timezone_is_rejected(self, client: TestClient) -> None:
        account = _account(client)
        response = client.patch(
            "/api/auth/me", json={"timezone": "Nowhere/City"}, headers=_auth(account)
        )
        assert response.status_code == 422

    def test_timezone_change_does_not_rewrite_existing_dates(self, client: TestClient) -> None:
        account = _account(client)
        created = _add_expense(client, account)
        assert created["expense_date"] == "2026-10-30"

        client.patch("/api/auth/me", json={"timezone": "America/New_York"}, headers=_auth(account))

        reread = client.get(f"/api/expenses/{created['id']}", headers=_auth(account)).json()
        assert reread["expense_date"] == "2026-10-30"
        assert reread["spent_at"] == created["spent_at"]

    def test_profile_update_requires_auth(self, client: TestClient) -> None:
        assert client.patch("/api/auth/me", json={"display_name": "x"}).status_code == 401


class TestPasswordChange:
    def test_change_password_then_login_with_new(self, client: TestClient) -> None:
        account = _account(client)
        response = client.post(
            "/api/auth/password",
            json={"current_password": account["password"], "new_password": "brandnewpass1"},
            headers=_auth(account),
        )
        assert response.status_code == 204

        login = client.post(
            "/api/auth/login",
            json={"email": account["email"], "password": "brandnewpass1"},
        )
        assert login.status_code == 200

    def test_wrong_current_password_is_rejected(self, client: TestClient) -> None:
        account = _account(client)
        response = client.post(
            "/api/auth/password",
            json={"current_password": "wrong-password", "new_password": "brandnewpass1"},
            headers=_auth(account),
        )
        assert response.status_code == 400

    def test_short_new_password_is_rejected(self, client: TestClient) -> None:
        account = _account(client)
        response = client.post(
            "/api/auth/password",
            json={"current_password": account["password"], "new_password": "short"},
            headers=_auth(account),
        )
        assert response.status_code == 422


class TestExport:
    def test_expenses_export_contains_only_own_rows(self, client: TestClient) -> None:
        owner = _account(client)
        _add_expense(client, owner, amount="99.99", category="travel")
        other = _account(client)

        response = client.get("/api/export/expenses.csv", headers=_auth(other))
        assert response.status_code == 200
        rows = list(csv.DictReader(io.StringIO(response.text)))
        assert rows == []  # header only

        own = client.get("/api/export/expenses.csv", headers=_auth(owner))
        rows = list(csv.DictReader(io.StringIO(own.text)))
        assert len(rows) == 1
        assert rows[0]["category"] == "travel"
        assert rows[0]["amount"] == "99.99"

    def test_export_headers_are_stable(self, client: TestClient) -> None:
        account = _account(client)
        response = client.get("/api/export/expenses.csv", headers=_auth(account))
        header = response.text.splitlines()[0]
        for column in ("expense_date", "spent_at_utc", "category", "amount"):
            assert column in header

    def test_lifestyle_export_is_scoped(self, client: TestClient) -> None:
        owner = _account(client)
        client.post(
            "/api/lifestyle-logs",
            json={"log_date": "2026-10-30", "stress_level": 3},
            headers=_auth(owner),
        )
        other = _account(client)
        response = client.get("/api/export/lifestyle.csv", headers=_auth(other))
        assert list(csv.DictReader(io.StringIO(response.text))) == []

    def test_csv_formula_injection_is_neutralised(self, client: TestClient) -> None:
        account = _account(client)
        client.post(
            "/api/expenses",
            json={
                "amount": "1.00",
                "category": "food",
                "expense_date": "2026-10-30",
                "description": '=HYPERLINK("http://evil")',
            },
            headers=_auth(account),
        )
        response = client.get("/api/export/expenses.csv", headers=_auth(account))
        rows = list(csv.DictReader(io.StringIO(response.text)))
        assert rows[0]["description"].startswith("'=")

    def test_export_requires_auth(self, client: TestClient) -> None:
        assert client.get("/api/export/expenses.csv").status_code == 401

    def test_export_is_download_not_inline(self, client: TestClient) -> None:
        account = _account(client)
        response = client.get("/api/export/expenses.csv", headers=_auth(account))
        assert "attachment" in response.headers.get("content-disposition", "")


class TestBudgets:
    def test_create_and_read_budget_status(self, client: TestClient) -> None:
        account = _account(client)
        response = client.put(
            "/api/budgets",
            json={"category": "food", "monthly_limit": "100.00"},
            headers=_auth(account),
        )
        assert response.status_code == 200, response.text

        statuses = client.get("/api/budgets", headers=_auth(account)).json()
        assert len(statuses) == 1
        status = statuses[0]
        assert status["category"] == "food"
        assert float(status["monthly_limit"]) == 100.0
        assert "remaining" in status and "percentage_used" in status

    def test_upsert_updates_rather_than_duplicates(self, client: TestClient) -> None:
        account = _account(client)
        for limit in ("100.00", "250.00"):
            client.put(
                "/api/budgets",
                json={"category": "food", "monthly_limit": limit},
                headers=_auth(account),
            )
        statuses = client.get("/api/budgets", headers=_auth(account)).json()
        assert len(statuses) == 1
        assert float(statuses[0]["monthly_limit"]) == 250.0

    def test_overall_budget_and_category_budget_coexist(self, client: TestClient) -> None:
        account = _account(client)
        client.put("/api/budgets", json={"monthly_limit": "500.00"}, headers=_auth(account))
        client.put(
            "/api/budgets",
            json={"category": "food", "monthly_limit": "100.00"},
            headers=_auth(account),
        )
        statuses = client.get("/api/budgets", headers=_auth(account)).json()
        assert len(statuses) == 2

    def test_invalid_limit_is_rejected(self, client: TestClient) -> None:
        account = _account(client)
        response = client.put("/api/budgets", json={"monthly_limit": "0"}, headers=_auth(account))
        assert response.status_code == 422

    def test_overall_budget_upsert_is_idempotent(self, client: TestClient) -> None:
        # Regression: a NULL category must be matched with IS NULL, not IS <param>.
        account = _account(client)
        for limit in ("300.00", "450.00"):
            response = client.put(
                "/api/budgets", json={"monthly_limit": limit}, headers=_auth(account)
            )
            assert response.status_code == 200, response.text

        statuses = client.get("/api/budgets", headers=_auth(account)).json()
        assert len(statuses) == 1
        assert statuses[0]["category"] is None
        assert float(statuses[0]["monthly_limit"]) == 450.0

    def test_category_budget_upsert_is_idempotent(self, client: TestClient) -> None:
        # Regression: a real category must use equality, never IS.
        account = _account(client)
        for limit in ("60.00", "75.00"):
            response = client.put(
                "/api/budgets",
                json={"category": "transport", "monthly_limit": limit},
                headers=_auth(account),
            )
            assert response.status_code == 200, response.text

        statuses = client.get("/api/budgets", headers=_auth(account)).json()
        assert len(statuses) == 1
        assert statuses[0]["category"] == "transport"
        assert float(statuses[0]["monthly_limit"]) == 75.0

    def test_overall_and_category_lookups_do_not_collide(self, client: TestClient) -> None:
        # The IS NULL branch and the equality branch must select different rows.
        account = _account(client)
        client.put("/api/budgets", json={"monthly_limit": "500.00"}, headers=_auth(account))
        client.put(
            "/api/budgets",
            json={"category": "transport", "monthly_limit": "75.00"},
            headers=_auth(account),
        )

        statuses = client.get("/api/budgets", headers=_auth(account)).json()
        by_category = {status["category"]: float(status["monthly_limit"]) for status in statuses}
        assert by_category == {None: 500.0, "transport": 75.0}

    def test_updating_one_budget_leaves_the_other_intact(self, client: TestClient) -> None:
        account = _account(client)
        client.put("/api/budgets", json={"monthly_limit": "500.00"}, headers=_auth(account))
        client.put(
            "/api/budgets",
            json={"category": "transport", "monthly_limit": "75.00"},
            headers=_auth(account),
        )
        # Upsert the category budget again; the overall budget must not change.
        client.put(
            "/api/budgets",
            json={"category": "transport", "monthly_limit": "90.00"},
            headers=_auth(account),
        )

        statuses = client.get("/api/budgets", headers=_auth(account)).json()
        by_category = {status["category"]: float(status["monthly_limit"]) for status in statuses}
        assert by_category == {None: 500.0, "transport": 90.0}

    def test_invalid_category_is_rejected(self, client: TestClient) -> None:
        account = _account(client)
        response = client.put(
            "/api/budgets",
            json={"category": "yachts", "monthly_limit": "10.00"},
            headers=_auth(account),
        )
        assert response.status_code == 422

    def test_budgets_are_isolated_between_users(self, client: TestClient) -> None:
        owner = _account(client)
        client.put(
            "/api/budgets",
            json={"category": "food", "monthly_limit": "100.00"},
            headers=_auth(owner),
        )
        other = _account(client)
        assert client.get("/api/budgets", headers=_auth(other)).json() == []

    def test_cannot_read_another_users_budget(self, client: TestClient) -> None:
        owner = _account(client)
        created = client.put(
            "/api/budgets",
            json={"category": "food", "monthly_limit": "100.00"},
            headers=_auth(owner),
        ).json()
        other = _account(client)
        response = client.get(f"/api/budgets/{created['id']}", headers=_auth(other))
        assert response.status_code == 404

    def test_cannot_delete_another_users_budget(self, client: TestClient) -> None:
        owner = _account(client)
        created = client.put(
            "/api/budgets",
            json={"category": "food", "monthly_limit": "100.00"},
            headers=_auth(owner),
        ).json()
        other = _account(client)
        assert (
            client.delete(f"/api/budgets/{created['id']}", headers=_auth(other)).status_code == 404
        )
        assert len(client.get("/api/budgets", headers=_auth(owner)).json()) == 1

    def test_delete_own_budget(self, client: TestClient) -> None:
        account = _account(client)
        created = client.put(
            "/api/budgets",
            json={"category": "food", "monthly_limit": "100.00"},
            headers=_auth(account),
        ).json()
        response = client.delete(f"/api/budgets/{created['id']}", headers=_auth(account))
        assert response.status_code == 204
        assert client.get("/api/budgets", headers=_auth(account)).json() == []


class TestAccountDeletion:
    def test_wrong_password_does_not_delete(self, client: TestClient) -> None:
        account = _account(client)
        response = client.post(
            "/api/auth/delete-account",
            json={"password": "wrong-password", "confirm": "DELETE"},
            headers=_auth(account),
        )
        assert response.status_code == 400
        # The account still exists and the token still works.
        assert client.get("/api/auth/me", headers=_auth(account)).status_code == 200

    def test_confirmation_string_is_required(self, client: TestClient) -> None:
        account = _account(client)
        response = client.post(
            "/api/auth/delete-account",
            json={"password": account["password"], "confirm": "yes"},
            headers=_auth(account),
        )
        assert response.status_code == 422

    def test_get_request_cannot_delete(self, client: TestClient) -> None:
        account = _account(client)
        assert client.get("/api/auth/delete-account", headers=_auth(account)).status_code == 405

    def test_delete_removes_user_and_data(self, client: TestClient) -> None:
        account = _account(client)
        _add_expense(client, account)
        client.post(
            "/api/lifestyle-logs",
            json={"log_date": "2026-10-30"},
            headers=_auth(account),
        )

        response = client.post(
            "/api/auth/delete-account",
            json={"password": account["password"], "confirm": "DELETE"},
            headers=_auth(account),
        )
        assert response.status_code == 204

        # The token is now unusable because the user no longer exists.
        assert client.get("/api/auth/me", headers=_auth(account)).status_code == 401
        # And the credentials no longer authenticate.
        relogin = client.post(
            "/api/auth/login",
            json={"email": account["email"], "password": account["password"]},
        )
        assert relogin.status_code == 401

    def test_deleting_one_account_does_not_affect_another(self, client: TestClient) -> None:
        doomed = _account(client)
        survivor = _account(client)
        _add_expense(client, survivor, amount="7.00")

        client.post(
            "/api/auth/delete-account",
            json={"password": doomed["password"], "confirm": "DELETE"},
            headers=_auth(doomed),
        )

        assert client.get("/api/auth/me", headers=_auth(survivor)).status_code == 200
        listed = client.get("/api/expenses", headers=_auth(survivor)).json()
        assert listed["total"] == 1
