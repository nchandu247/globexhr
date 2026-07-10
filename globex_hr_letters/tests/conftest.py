"""
Pytest configuration and shared fixtures.

Mocks frappe at the module level BEFORE any globex_hr_letters imports so
that decorators applied at class-definition time (whitelist, retry) pick up
the no-op versions during tests.
"""
import sys
import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

# ── 1. Mock frappe and submodules ─────────────────────────────────────────────
frappe_mock = MagicMock()
frappe_mock.logger.return_value = MagicMock()
# @frappe.whitelist() decorator: make it an identity decorator in tests
# so the decorated function still callable. Without this, decorated functions
# become MagicMock and tests can't invoke them.
frappe_mock.whitelist = lambda *args, **kwargs: (lambda f: f)
sys.modules.setdefault("frappe", frappe_mock)

# Mock frappe submodules so `from frappe.utils.password import ...` works in tests
_frappe_utils_password = MagicMock()
_frappe_utils_password.set_encrypted_password = MagicMock()
sys.modules.setdefault("frappe.utils", MagicMock())
sys.modules.setdefault("frappe.utils.password", _frappe_utils_password)

# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def settings():
    """Mock HR Letters Settings object with sensible defaults."""
    s = MagicMock()
    s.enabled = True
    s.zoho_sign_client_id = "test_client_id"
    # No cached access token by default → forces OAuth refresh
    s.zoho_sign_access_token = None
    s.zoho_sign_token_expires_at = None
    s.get_password.return_value = "test_secret"
    s.save = MagicMock()
    return s


@pytest.fixture(autouse=True)
def patch_frappe(settings):
    """Wire frappe.get_single to return the mock settings for every test."""
    frappe_mock.reset_mock()  # clear call_args_list accumulated from previous tests
    # reset_mock() does NOT clear side_effect — explicitly null the ones that
    # tests commonly script with side_effect lists (otherwise iterators from
    # one test leak into the next and cause StopIteration).
    frappe_mock.get_all.side_effect = None
    frappe_mock.get_all.return_value = None
    frappe_mock.new_doc.side_effect = None
    frappe_mock.new_doc.return_value = MagicMock()
    frappe_mock.get_doc.side_effect = None
    frappe_mock.db.set_value.side_effect = None
    frappe_mock.get_single.return_value = settings
    frappe_mock.logger.return_value.info = MagicMock()
    yield frappe_mock


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    """Replace time.sleep with a no-op so retry backoff doesn't slow tests."""
    monkeypatch.setattr("globex_hr_letters.utils.retry.time.sleep", lambda s: None)


@pytest.fixture()
def token_response():
    """Standard Zoho OAuth success payload."""
    return {"access_token": "fresh_token_abc", "expires_in": 3600}
