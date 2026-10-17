"""JWT_SECRET rules per environment (V6 F2)."""

from __future__ import annotations

import pytest
from pydantic import SecretStr

from lifeline_api.main import build_state
from lifeline_api.settings import MIN_PROD_SECRET_LENGTH, Settings

STRONG = "k" * MIN_PROD_SECRET_LENGTH


def _prod(secret: str) -> Settings:
    return Settings(app_env="prod", jwt_secret=SecretStr(secret))


@pytest.mark.parametrize(
    "secret,reason",
    [
        ("", "not set"),
        ("change-me-dev-only", "placeholder"),
        ("changeme", "placeholder"),
        ("secret", "placeholder"),
        ("dev", "placeholder"),
        ("CHANGE-ME-DEV-ONLY", "placeholder"),
        ("k" * (MIN_PROD_SECRET_LENGTH - 1), "shorter than 32"),
    ],
)
def test_prod_rejects_weak_secret(secret: str, reason: str) -> None:
    with pytest.raises(RuntimeError) as exc:
        _prod(secret).signing_secret()
    assert reason in str(exc.value)
    if secret:
        assert secret not in str(exc.value), "the message must not print the value"


def test_prod_refuses_to_start_with_placeholder() -> None:
    with pytest.raises(RuntimeError):
        build_state(_prod("change-me-dev-only"))


def test_prod_accepts_strong_secret() -> None:
    assert _prod(STRONG).signing_secret() == STRONG


def test_dev_without_secret_uses_random_secret_with_warning(caplog: pytest.LogCaptureFixture) -> None:
    a = Settings(app_env="dev").signing_secret()
    b = Settings(app_env="dev").signing_secret()
    assert len(a) >= MIN_PROD_SECRET_LENGTH and a != b
    assert "JWT_SECRET is not set" in caplog.text


def test_dev_keeps_a_given_secret() -> None:
    assert Settings(app_env="dev", jwt_secret=SecretStr("short-dev")).signing_secret() == "short-dev"
