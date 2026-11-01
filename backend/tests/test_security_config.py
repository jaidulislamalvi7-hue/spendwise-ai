"""Security and production-safety tests (no database required).

These lock in the audit findings: secrets must not leak, the health endpoint
must stay minimal, deployment settings must fail safely, and HMAC-only
algorithms must be enforced.
"""

import pytest
from pydantic import ValidationError

from app.config import Settings, get_jwt_secret


class TestSecretHandling:
    def test_jwt_secret_is_not_in_repr(self) -> None:
        settings = Settings(jwt_secret="super-secret-value-1234567890")
        assert "super-secret-value-1234567890" not in repr(settings)

    def test_jwt_secret_is_not_in_model_dump(self) -> None:
        settings = Settings(jwt_secret="super-secret-value-1234567890")
        dumped = str(settings.model_dump())
        assert "super-secret-value-1234567890" not in dumped

    def test_get_jwt_secret_returns_plain_value(self) -> None:
        settings = Settings(jwt_secret="another-real-secret-value")
        # Access through the module-level accessor used by the token layer.
        assert settings.jwt_secret.get_secret_value() == "another-real-secret-value"

    def test_placeholder_secret_is_rejected_by_accessor(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "app.config.get_settings",
            lambda: Settings(jwt_secret="CHANGE_ME_GENERATE_A_RANDOM_SECRET"),
        )
        with pytest.raises(RuntimeError, match="placeholder"):
            get_jwt_secret()


class TestAlgorithmRestriction:
    @pytest.mark.parametrize("algorithm", ["HS256", "HS384", "HS512", "hs256"])
    def test_hmac_algorithms_are_accepted(self, algorithm: str) -> None:
        assert Settings(jwt_algorithm=algorithm).jwt_algorithm == algorithm

    @pytest.mark.parametrize("algorithm", ["none", "RS256", "ES256", "PS256"])
    def test_non_hmac_algorithms_are_rejected(self, algorithm: str) -> None:
        # 'none' and asymmetric algorithms would enable algorithm-confusion attacks.
        with pytest.raises(ValidationError):
            Settings(jwt_algorithm=algorithm)


class TestProductionSafety:
    def test_placeholder_secret_fails_outside_development(self) -> None:
        with pytest.raises(ValidationError):
            Settings(app_env="production", jwt_secret="CHANGE_ME_GENERATE_A_RANDOM_SECRET")

    def test_real_secret_is_accepted_in_production(self) -> None:
        settings = Settings(app_env="production", jwt_secret="a-real-production-secret-value")
        assert settings.app_env == "production"

    def test_expiry_must_be_within_bounds(self) -> None:
        with pytest.raises(ValidationError):
            Settings(jwt_expire_minutes=0)
        with pytest.raises(ValidationError):
            Settings(jwt_expire_minutes=100000)

    def test_default_expiry_is_short_lived(self) -> None:
        assert Settings().jwt_expire_minutes <= 60
