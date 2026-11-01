"""Password hashing and JWT tests (no database)."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest

from app.config import Settings
from app.security.passwords import hash_password, needs_rehash, verify_password
from app.security.tokens import (
    TokenError,
    create_access_token,
    decode_access_token,
    token_subject_uuid,
)

SECRET = "unit-test-secret-not-a-placeholder"


@pytest.fixture(autouse=True)
def _settings(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.config.get_settings",
        lambda: Settings(
            app_env="development",
            jwt_secret=SECRET,
            jwt_algorithm="HS256",
            jwt_expire_minutes=30,
        ),
    )


class TestPasswordHashing:
    def test_hash_is_argon2(self) -> None:
        assert hash_password("correct horse battery").startswith("$argon2id$")

    def test_hash_is_not_the_plaintext(self) -> None:
        password = "supersecret123"
        assert password not in hash_password(password)

    def test_hashes_are_salted(self) -> None:
        assert hash_password("same-password") != hash_password("same-password")

    def test_correct_password_verifies(self) -> None:
        stored = hash_password("supersecret123")
        assert verify_password("supersecret123", stored) is True

    def test_wrong_password_fails(self) -> None:
        stored = hash_password("supersecret123")
        assert verify_password("wrong-password", stored) is False

    def test_empty_password_fails(self) -> None:
        assert verify_password("", hash_password("x")) is False

    def test_garbage_hash_fails(self) -> None:
        assert verify_password("anything", "not-a-hash") is False

    def test_empty_password_cannot_be_hashed(self) -> None:
        with pytest.raises(ValueError):
            hash_password("")

    def test_current_hash_needs_no_rehash(self) -> None:
        assert needs_rehash(hash_password("supersecret123")) is False

    def test_non_argon2_hash_needs_rehash(self) -> None:
        assert needs_rehash("$2b$12$abcdefghijklmnopqrstuv") is True

    def test_bcrypt_fallback_verifies(self) -> None:
        bcrypt = pytest.importorskip("bcrypt")
        stored = bcrypt.hashpw(b"fallbackpass", bcrypt.gensalt()).decode()
        assert verify_password("fallbackpass", stored) is True
        assert verify_password("wrong", stored) is False


class TestTokens:
    def test_round_trip(self) -> None:
        user_id = uuid4()
        token = create_access_token(user_id)
        assert token_subject_uuid(token) == user_id

    def test_claims_include_expiry(self) -> None:
        claims = decode_access_token(create_access_token(uuid4()))
        assert "exp" in claims
        assert claims["type"] == "access"

    def test_expired_token_is_rejected(self) -> None:
        token = create_access_token(uuid4(), expires_minutes=-1)
        with pytest.raises(TokenError):
            decode_access_token(token)

    def test_token_signed_with_other_secret_is_rejected(self) -> None:
        foreign = jwt.encode(
            {
                "sub": str(uuid4()),
                "exp": int((datetime.now(UTC) + timedelta(minutes=5)).timestamp()),
                "type": "access",
            },
            "a-completely-different-secret",
            algorithm="HS256",
        )
        with pytest.raises(TokenError):
            decode_access_token(foreign)

    def test_garbage_token_is_rejected(self) -> None:
        with pytest.raises(TokenError):
            decode_access_token("definitely.not.a.jwt")

    def test_wrong_token_type_is_rejected(self) -> None:
        token = jwt.encode(
            {
                "sub": str(uuid4()),
                "exp": int((datetime.now(UTC) + timedelta(minutes=5)).timestamp()),
                "type": "refresh",
            },
            SECRET,
            algorithm="HS256",
        )
        with pytest.raises(TokenError):
            decode_access_token(token)
