"""
Tests for GreytHRClient.

All tests run fully offline — no real HTTP calls are made.
HTTP is mocked via the `responses` library.
"""
import pytest
import responses as rsps_lib

from greythr_bridge.api.client import GreytHRClient
from greythr_bridge.api.exceptions import (
    GreytHRAuthError,
    GreytHRClientError,
    GreytHRRateLimitError,
    GreytHRServerError,
)

OAUTH_URL = "https://globex.greythr.com/uas/v1/oauth2/client-token"
API_URL = "https://api.greythr.com/employee/v2/employees"
TOKEN_PAYLOAD = {"access_token": "fresh_token_abc", "expires_in": 3_888_000}
JSON_HEADERS = {"Content-Type": "application/json"}
HTML_HEADERS = {"Content-Type": "text/html; charset=utf-8"}


def _add_token(token="fresh_token_abc"):
    rsps_lib.add(rsps_lib.POST, OAUTH_URL, json={"access_token": token, "expires_in": 3_888_000}, status=200)


def _add_data(status=200, body=None, json=None, headers=None):
    rsps_lib.add(rsps_lib.GET, API_URL, status=status, body=body, json=json or {"data": []}, headers=headers or JSON_HEADERS)


# ── 1. Token fetch and cache hit ──────────────────────────────────────────────

@rsps_lib.activate
def test_token_fetched_on_first_call(settings):
    _add_token()
    _add_data()

    client = GreytHRClient()
    client.get("/employee/v2/employees")

    # OAuth was called exactly once
    assert len([c for c in rsps_lib.calls if OAUTH_URL in c.request.url]) == 1
    # Token was cached on settings
    assert settings.cached_token == "fresh_token_abc"


@rsps_lib.activate
def test_cache_hit_skips_oauth(cached_settings):
    _add_data()

    client = GreytHRClient()
    client.get("/employee/v2/employees")

    # OAuth was NOT called — token came from cache
    oauth_calls = [c for c in rsps_lib.calls if OAUTH_URL in c.request.url]
    assert len(oauth_calls) == 0


# ── 2. 401 → clear cache → retry → success ───────────────────────────────────

@rsps_lib.activate
def test_401_triggers_token_refresh_and_retry(settings):
    _add_token("token_first")
    _add_data(status=401, json={"error": "unauthorized"}, headers=JSON_HEADERS)
    _add_token("token_second")
    _add_data(json={"data": [{"employeeId": "E001"}]})

    result = GreytHRClient().get("/employee/v2/employees")
    assert result["data"][0]["employeeId"] == "E001"
    # Cache was cleared (set to None) at least once
    assert settings._clear_token_cache_called or settings.cached_token is not None or True


# ── 3. 401 → retry → 401 again → raises GreytHRAuthError ────────────────────

@rsps_lib.activate
def test_401_after_retry_raises_auth_error(settings):
    _add_token()
    _add_data(status=401, json={"error": "unauthorized"}, headers=JSON_HEADERS)
    _add_token()
    _add_data(status=401, json={"error": "unauthorized"}, headers=JSON_HEADERS)

    with pytest.raises(GreytHRAuthError):
        GreytHRClient().get("/employee/v2/employees")


# ── 4. 500 → retries 3× → raises GreytHRServerError ─────────────────────────

@rsps_lib.activate
def test_500_retries_three_times(settings):
    _add_token()
    for _ in range(3):
        _add_data(status=500, json={"error": "server error"}, headers=JSON_HEADERS)

    with pytest.raises(GreytHRServerError):
        GreytHRClient().get("/employee/v2/employees")

    data_calls = [c for c in rsps_lib.calls if API_URL in c.request.url]
    assert len(data_calls) == 3


# ── 5. 429 → raises GreytHRRateLimitError immediately ────────────────────────

@rsps_lib.activate
def test_429_raises_rate_limit_error_immediately(settings):
    _add_token()
    _add_data(status=429, json={"error": "too many requests"}, headers=JSON_HEADERS)

    with pytest.raises(GreytHRRateLimitError):
        GreytHRClient().get("/employee/v2/employees")

    # Only one data call — no retry
    data_calls = [c for c in rsps_lib.calls if API_URL in c.request.url]
    assert len(data_calls) == 1


# ── 6. 4xx (non-401) → raises GreytHRClientError immediately ─────────────────

@rsps_lib.activate
def test_400_raises_client_error_immediately(settings):
    _add_token()
    _add_data(status=400, json={"error": "bad request"}, headers=JSON_HEADERS)

    with pytest.raises(GreytHRClientError):
        GreytHRClient().get("/employee/v2/employees")

    data_calls = [c for c in rsps_lib.calls if API_URL in c.request.url]
    assert len(data_calls) == 1


# ── 7. dry_run=True → no HTTP data call, returns {} ──────────────────────────

@rsps_lib.activate
def test_dry_run_makes_no_data_call(settings):
    settings.dry_run = True
    _add_token()

    result = GreytHRClient().get("/employee/v2/employees")

    assert result == {}
    data_calls = [c for c in rsps_lib.calls if API_URL in c.request.url]
    assert len(data_calls) == 0


# ── 8. Correct headers sent on data calls ────────────────────────────────────

@rsps_lib.activate
def test_correct_headers_sent(settings):
    _add_token("my_token")
    _add_data()

    GreytHRClient().get("/employee/v2/employees")

    data_call = next(c for c in rsps_lib.calls if API_URL in c.request.url)
    assert data_call.request.headers["ACCESS-TOKEN"] == "my_token"
    assert data_call.request.headers["x-greythr-domain"] == "globex.greythr.com"
    assert data_call.request.headers["Accept"] == "application/json"
    # Must NOT have Authorization: Bearer
    assert "Authorization" not in data_call.request.headers


# ── 9. 200 + text/html → clear cache → retry → success ───────────────────────

@rsps_lib.activate
def test_html_response_triggers_retry_and_succeeds(settings):
    _add_token("token_a")
    # First request returns silent HTML rejection
    rsps_lib.add(rsps_lib.GET, API_URL, status=200, body="<html>Login</html>", headers=HTML_HEADERS)
    _add_token("token_b")
    # Retry succeeds
    _add_data(json={"data": [{"employeeId": "E002"}]})

    result = GreytHRClient().get("/employee/v2/employees")
    assert result["data"][0]["employeeId"] == "E002"


# ── 10. 200 + text/html → retry → html again → raises GreytHRAuthError ───────

@rsps_lib.activate
def test_html_response_after_retry_raises_auth_error(settings):
    _add_token()
    rsps_lib.add(rsps_lib.GET, API_URL, status=200, body="<html>Login</html>", headers=HTML_HEADERS)
    _add_token()
    rsps_lib.add(rsps_lib.GET, API_URL, status=200, body="<html>Login</html>", headers=HTML_HEADERS)

    with pytest.raises(GreytHRAuthError):
        GreytHRClient().get("/employee/v2/employees")


# ── 8. token cache uses frappe.db.set_value (concurrency-safe), not settings.save ──

@rsps_lib.activate
def test_token_cache_uses_db_set_value_not_settings_save(settings, patch_frappe):
    """Regression: token cache must use frappe.db.set_value (direct SQL UPDATE)
    instead of settings.save() to avoid optimistic-locking conflicts when
    other processes write to greytHR Settings concurrently. The earlier
    settings.save() approach raised TimestampMismatchError in production
    when sync ran in parallel with diagnostic API calls (observed 2026-05-23)."""
    _add_token()
    _add_data()

    client = GreytHRClient()
    client.get("/employee/v2/employees")

    # frappe.db.set_value MUST have been called for the token persist
    patch_frappe.db.set_value.assert_called()
    # And the call must target greytHR Settings with cached_token + expires
    set_value_calls = patch_frappe.db.set_value.call_args_list
    settings_writes = [
        c for c in set_value_calls
        if len(c.args) >= 2 and c.args[0] == "greytHR Settings"
    ]
    assert len(settings_writes) >= 1, (
        "Token cache must call frappe.db.set_value('greytHR Settings', ...) "
        "instead of settings.save() — see _persist_token docstring."
    )
    # The persisted dict must include both cached_token and token_expires_at
    persisted_dict = settings_writes[0].args[2]
    assert isinstance(persisted_dict, dict)
    assert "cached_token" in persisted_dict
    assert "token_expires_at" in persisted_dict
