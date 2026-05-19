"""
Pytest configuration and shared fixtures.

Mocks frappe and ratelimit at the module level BEFORE any greythr_bridge
imports so that decorators applied at class-definition time (rate_limited,
retry) pick up the no-op versions during tests.
"""
import sys
import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

# ── 1. Mock frappe and submodules ─────────────────────────────────────────────
frappe_mock = MagicMock()
frappe_mock.logger.return_value = MagicMock()
sys.modules.setdefault("frappe", frappe_mock)

# Mock frappe submodules so `from frappe.utils.password import ...` works in tests
_frappe_utils_password = MagicMock()
_frappe_utils_password.set_encrypted_password = MagicMock()
sys.modules.setdefault("frappe.utils", MagicMock())
sys.modules.setdefault("frappe.utils.password", _frappe_utils_password)

# ── 2. Mock ratelimit → no-op decorators so tests run without sleeping ────────
ratelimit_mock = MagicMock()
ratelimit_mock.limits = lambda calls, period: (lambda f: f)
ratelimit_mock.sleep_and_retry = lambda f: f
sys.modules.setdefault("ratelimit", ratelimit_mock)


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def settings():
    """Mock greytHR Settings object with sensible defaults."""
    s = MagicMock()
    s.enabled = True
    s.dry_run = False
    s.api_base_url = "https://api.greythr.com"
    s.tenant_domain = "globex.greythr.com"
    s.client_id = "test_client_id"
    # No cached token by default → forces OAuth fetch
    s.cached_token = None
    s.token_expires_at = None
    s.get_password.return_value = "test_secret"
    s.save = MagicMock()
    return s


@pytest.fixture(autouse=True)
def patch_frappe(settings):
    """Wire frappe.get_single to return the mock settings for every test."""
    frappe_mock.reset_mock()  # clear call_args_list accumulated from previous tests
    frappe_mock.get_single.return_value = settings
    frappe_mock.logger.return_value.info = MagicMock()
    yield frappe_mock


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    """Replace time.sleep with a no-op so retry backoff doesn't slow tests."""
    monkeypatch.setattr("greythr_bridge.utils.retry.time.sleep", lambda s: None)


@pytest.fixture()
def token_response():
    """Standard OAuth success payload."""
    return {"access_token": "fresh_token_abc", "expires_in": 3_888_000}


@pytest.fixture()
def cached_settings(settings):
    """Settings with a valid cached token (no OAuth fetch needed)."""
    settings.cached_token = "cached_token_xyz"
    settings.token_expires_at = datetime.now() + timedelta(days=30)
    settings.get_password.return_value = "cached_token_xyz"
    return settings
