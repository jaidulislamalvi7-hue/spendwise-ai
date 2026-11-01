"""Tests for frontend-level constants and attribution."""

import config


def test_attribution_constant() -> None:
    assert config.APP_AUTHOR == "Jaidul Islam"


def test_footer_includes_author() -> None:
    assert "Jaidul Islam" in config.FOOTER_TEXT
    assert config.APP_NAME in config.FOOTER_TEXT
