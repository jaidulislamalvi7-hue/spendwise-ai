"""API tests through the FastAPI test client (requires PostgreSQL).

The ``client`` fixture lives in ``tests/conftest.py`` so every module shares it.
"""

import uuid

from fastapi.testclient import TestClient

from tests.db_guard import requires_db

pytestmark = requires_db


def _register(client: TestClient) -> dict:
    payload = {
        "email": f"api-{uuid.uuid4().hex[:10]}@example.com",
        "password": "supersecret123",
        "primary_currency": "USD",
        "timezone": "UTC",
    }
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 201, response.text
    return {"user": response.json(), "password": payload["password"], "email": payload["email"]}


def _login(client: TestClient, email: str, password: str) -> str:
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _new_authed_client(client: TestClient) -> tuple[str, dict]:
    account = _register(client)
    token = _login(client, account["email"], account["password"])
    return token, account["user"]


EXPENSE = {
    "amount": "12.50",
    "category": "food",
    "expense_date": "2026-10-30",
    "description": "lunch",
}


class TestHealth:
    def test_health_endpoint(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestAuthApi:
    def test_register_returns_user_without_password(self, client: TestClient) -> None:
        account = _register(client)
        body = account["user"]
        assert body["email"] == account["email"]
        assert "password" not in body
        assert "password_hash" not in body

    def test_duplicate_registration_returns_409(self, client: TestClient) -> None:
        account = _register(client)
        response = client.post(
            "/api/auth/register",
            json={"email": account["email"], "password": "supersecret123"},
        )
        assert response.status_code == 409

    def test_login_returns_token(self, client: TestClient) -> None:
        account = _register(client)
        token = _login(client, account["email"], account["password"])
        assert token

    def test_login_with_wrong_password_returns_401(self, client: TestClient) -> None:
        account = _register(client)
        response = client.post(
            "/api/auth/login", json={"email": account["email"], "password": "wrong-password"}
        )
        assert response.status_code == 401

    def test_login_unknown_email_returns_401(self, client: TestClient) -> None:
        response = client.post(
            "/api/auth/login", json={"email": "ghost@example.com", "password": "whatever1"}
        )
        assert response.status_code == 401

    def test_me_requires_token(self, client: TestClient) -> None:
        assert client.get("/api/auth/me").status_code == 401

    def test_auth_responses_never_expose_sensitive_fields(self, client: TestClient) -> None:
        account = _register(client)
        token = _login(client, account["email"], account["password"])

        login_body = client.post(
            "/api/auth/login", json={"email": account["email"], "password": account["password"]}
        ).json()
        me_body = client.get("/api/auth/me", headers=_auth(token)).json()

        for body in (account["user"], login_body, me_body):
            serialized = str(body).lower()
            assert "password_hash" not in serialized
            assert "password" not in serialized
            assert "jwt_secret" not in serialized
            # The hash itself must never appear, only the opaque token.
            assert "$argon2" not in serialized

    def test_health_does_not_disclose_environment(self, client: TestClient) -> None:
        # The probe must stay minimal; environment names hint at deployment shape.
        assert client.get("/health").json() == {"status": "ok"}

    def test_unauthorized_error_has_no_stack_trace(self, client: TestClient) -> None:
        response = client.get("/api/expenses")
        assert response.status_code == 401
        body = str(response.json()).lower()
        assert "traceback" not in body
        assert "sqlalchemy" not in body

    def test_me_returns_profile(self, client: TestClient) -> None:
        token, user = _new_authed_client(client)
        response = client.get("/api/auth/me", headers=_auth(token))
        assert response.status_code == 200
        assert response.json()["id"] == user["id"]


class TestExpenseApi:
    def test_create_expense(self, client: TestClient) -> None:
        token, _ = _new_authed_client(client)
        response = client.post("/api/expenses", json=EXPENSE, headers=_auth(token))
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["amount"] == "12.50"
        assert body["expense_date"] == "2026-10-30"

    def test_create_requires_authentication(self, client: TestClient) -> None:
        assert client.post("/api/expenses", json=EXPENSE).status_code == 401

    def test_create_rejects_zero_amount(self, client: TestClient) -> None:
        token, _ = _new_authed_client(client)
        payload = {**EXPENSE, "amount": "0"}
        assert client.post("/api/expenses", json=payload, headers=_auth(token)).status_code == 422

    def test_create_rejects_unknown_category(self, client: TestClient) -> None:
        token, _ = _new_authed_client(client)
        payload = {**EXPENSE, "category": "yachts"}
        assert client.post("/api/expenses", json=payload, headers=_auth(token)).status_code == 422

    def test_ignores_user_id_in_body(self, client: TestClient) -> None:
        token, user = _new_authed_client(client)
        other = _register(client)["user"]
        payload = {**EXPENSE, "user_id": other["id"]}
        response = client.post("/api/expenses", json=payload, headers=_auth(token))
        assert response.status_code == 201
        # The expense belongs to the token owner, not the supplied user_id.
        listed = client.get("/api/expenses", headers=_auth(token)).json()
        assert listed["total"] == 1
        assert listed["items"][0]["id"] == response.json()["id"]
        other_listed = client.get(
            "/api/expenses",
            headers=_auth(_login(client, other["email"], "supersecret123")),
        ).json()
        assert other_listed["total"] == 0

    def test_list_filters(self, client: TestClient) -> None:
        token, _ = _new_authed_client(client)
        client.post("/api/expenses", json=EXPENSE, headers=_auth(token))
        client.post(
            "/api/expenses",
            json={**EXPENSE, "category": "transport", "expense_date": "2026-11-02"},
            headers=_auth(token),
        )
        filtered = client.get(
            "/api/expenses", params={"category": "transport"}, headers=_auth(token)
        ).json()
        assert filtered["total"] == 1
        ranged = client.get(
            "/api/expenses",
            params={"date_from": "2026-11-01", "date_to": "2026-11-30"},
            headers=_auth(token),
        ).json()
        assert ranged["total"] == 1

    def test_invalid_date_range_returns_422(self, client: TestClient) -> None:
        token, _ = _new_authed_client(client)
        response = client.get(
            "/api/expenses",
            params={"date_from": "2026-11-10", "date_to": "2026-11-01"},
            headers=_auth(token),
        )
        assert response.status_code == 422

    def test_get_update_delete_flow(self, client: TestClient) -> None:
        token, _ = _new_authed_client(client)
        created = client.post("/api/expenses", json=EXPENSE, headers=_auth(token)).json()
        expense_id = created["id"]

        assert client.get(f"/api/expenses/{expense_id}", headers=_auth(token)).status_code == 200

        updated = client.patch(
            f"/api/expenses/{expense_id}", json={"amount": "20.00"}, headers=_auth(token)
        )
        assert updated.status_code == 200
        assert updated.json()["amount"] == "20.00"

        assert client.delete(f"/api/expenses/{expense_id}", headers=_auth(token)).status_code == 204
        assert client.get(f"/api/expenses/{expense_id}", headers=_auth(token)).status_code == 404

    def test_missing_expense_returns_404(self, client: TestClient) -> None:
        token, _ = _new_authed_client(client)
        response = client.get(f"/api/expenses/{uuid.uuid4()}", headers=_auth(token))
        assert response.status_code == 404

    def test_cross_user_read_is_404(self, client: TestClient) -> None:
        owner_token, _ = _new_authed_client(client)
        created = client.post("/api/expenses", json=EXPENSE, headers=_auth(owner_token)).json()

        intruder_token, _ = _new_authed_client(client)
        response = client.get(f"/api/expenses/{created['id']}", headers=_auth(intruder_token))
        assert response.status_code == 404

    def test_cross_user_update_is_404(self, client: TestClient) -> None:
        owner_token, _ = _new_authed_client(client)
        created = client.post("/api/expenses", json=EXPENSE, headers=_auth(owner_token)).json()

        intruder_token, _ = _new_authed_client(client)
        response = client.patch(
            f"/api/expenses/{created['id']}", json={"amount": "1.00"}, headers=_auth(intruder_token)
        )
        assert response.status_code == 404

    def test_cross_user_delete_is_404_and_preserves_record(self, client: TestClient) -> None:
        owner_token, _ = _new_authed_client(client)
        created = client.post("/api/expenses", json=EXPENSE, headers=_auth(owner_token)).json()

        intruder_token, _ = _new_authed_client(client)
        assert (
            client.delete(
                f"/api/expenses/{created['id']}", headers=_auth(intruder_token)
            ).status_code
            == 404
        )
        assert (
            client.get(f"/api/expenses/{created['id']}", headers=_auth(owner_token)).status_code
            == 200
        )

    def test_cross_user_list_is_isolated(self, client: TestClient) -> None:
        owner_token, _ = _new_authed_client(client)
        client.post("/api/expenses", json=EXPENSE, headers=_auth(owner_token))

        intruder_token, _ = _new_authed_client(client)
        assert client.get("/api/expenses", headers=_auth(intruder_token)).json()["total"] == 0


class TestLifestyleApi:
    def test_create_and_list(self, client: TestClient) -> None:
        token, _ = _new_authed_client(client)
        response = client.post(
            "/api/lifestyle-logs",
            json={"log_date": "2026-10-30", "stress_level": 3, "work_mode": "remote"},
            headers=_auth(token),
        )
        assert response.status_code == 201, response.text
        listed = client.get("/api/lifestyle-logs", headers=_auth(token)).json()
        assert listed["total"] == 1

    def test_duplicate_date_returns_409(self, client: TestClient) -> None:
        token, _ = _new_authed_client(client)
        payload = {"log_date": "2026-10-30"}
        client.post("/api/lifestyle-logs", json=payload, headers=_auth(token))
        assert (
            client.post("/api/lifestyle-logs", json=payload, headers=_auth(token)).status_code
            == 409
        )

    def test_validation_rejects_stress_out_of_range(self, client: TestClient) -> None:
        token, _ = _new_authed_client(client)
        response = client.post(
            "/api/lifestyle-logs",
            json={"log_date": "2026-10-30", "stress_level": 9},
            headers=_auth(token),
        )
        assert response.status_code == 422

    def test_update_and_delete(self, client: TestClient) -> None:
        token, _ = _new_authed_client(client)
        created = client.post(
            "/api/lifestyle-logs",
            json={"log_date": "2026-10-30", "stress_level": 2},
            headers=_auth(token),
        ).json()
        updated = client.patch(
            f"/api/lifestyle-logs/{created['id']}", json={"stress_level": 4}, headers=_auth(token)
        )
        assert updated.status_code == 200
        assert updated.json()["stress_level"] == 4
        assert (
            client.delete(f"/api/lifestyle-logs/{created['id']}", headers=_auth(token)).status_code
            == 204
        )

    def test_cross_user_lifestyle_access_is_404(self, client: TestClient) -> None:
        owner_token, _ = _new_authed_client(client)
        created = client.post(
            "/api/lifestyle-logs", json={"log_date": "2026-10-30"}, headers=_auth(owner_token)
        ).json()

        intruder_token, _ = _new_authed_client(client)
        assert (
            client.patch(
                f"/api/lifestyle-logs/{created['id']}",
                json={"stress_level": 1},
                headers=_auth(intruder_token),
            ).status_code
            == 404
        )
        assert (
            client.delete(
                f"/api/lifestyle-logs/{created['id']}", headers=_auth(intruder_token)
            ).status_code
            == 404
        )
        assert client.get("/api/lifestyle-logs", headers=_auth(intruder_token)).json()["total"] == 0


class TestTokenHandling:
    def test_invalid_token_returns_401(self, client: TestClient) -> None:
        assert client.get("/api/expenses", headers=_auth("not.a.jwt")).status_code == 401

    def test_expired_token_returns_401(self, client: TestClient) -> None:
        token, _ = _new_authed_client(client)
        from app.security.tokens import create_access_token

        expired = create_access_token(uuid.uuid4(), expires_minutes=-1)
        assert client.get("/api/expenses", headers=_auth(expired)).status_code == 401
        # Sanity: a valid token still works.
        assert client.get("/api/expenses", headers=_auth(token)).status_code == 200
