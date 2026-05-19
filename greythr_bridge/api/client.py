import frappe
import requests
from datetime import datetime, timedelta

from .exceptions import (
    GreytHRAuthError,
    GreytHRRateLimitError,
    GreytHRServerError,
    GreytHRClientError,
)
from ..utils.retry import retry
from ..utils.rate_limiter import rate_limited


class GreytHRClient:
    """
    HTTP client for the greytHR REST API.

    Auth contract (greytHR-specific — non-standard):
      - OAuth token: POST to https://{tenant_domain}/uas/v1/oauth2/client-token
        using HTTP Basic auth header (Base64 of client_id:client_secret).
        The OAuth host (tenant subdomain) and data API host (api.greythr.com) are DIFFERENT.
      - Data calls: ACCESS-TOKEN: <raw_token> header — NO "Bearer" prefix.
      - x-greythr-domain: {tenant_domain} required on every data call for tenant routing.
      - Accept: application/json required — omitting can trigger 403.
      - Silent failure trap: greytHR returns 200 + text/html when auth is rejected.
        Always validate Content-Type; treat HTML as auth failure and retry once.

    Other responsibilities:
      - Cache token in greytHR Settings DocType (TTL from expires_in; ~45 days)
      - Auto-refresh on 401 or silent HTML rejection (one retry only — no loop)
      - Retry 5xx with exponential backoff (3 attempts: 1s, 2s, 4s)
      - Surface 4xx immediately — no retry
      - Rate-limit to 10 req/sec via @rate_limited
      - Respect dry_run flag — log but do not call

    Usage:
        client = GreytHRClient()
        result = client.get("/employee/v2/employees", params={"page": 1, "size": 50})
        employees = result.get("data", [])
    """

    def __init__(self):
        self.settings = frappe.get_single("greytHR Settings")
        if not self.settings.enabled:
            raise GreytHRClientError("greytHR integration is disabled in Settings")

    # ------------------------------------------------------------------ auth

    def _get_token(self) -> str:
        """Return a valid bearer token, refreshing from greytHR OAuth if expired."""
        now = datetime.now()
        expires_at = self.settings.token_expires_at

        # Frappe Datetime fields return datetime objects OR strings depending on context.
        # Normalise to datetime for comparison; store as string to avoid Frappe's
        # internal validator iterating over the datetime object (Frappe v16 bug).
        if expires_at and isinstance(expires_at, str):
            try:
                expires_at = datetime.strptime(expires_at, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                expires_at = None

        if (
            self.settings.cached_token
            and expires_at
            and isinstance(expires_at, datetime)
            and expires_at > now + timedelta(minutes=5)
        ):
            return self.settings.get_password("cached_token")

        # Token missing or expiring soon — fetch fresh via HTTP Basic auth.
        # Credentials go in the Authorization header, NOT the POST body.
        resp = requests.post(
            f"https://{self.settings.tenant_domain}/uas/v1/oauth2/client-token",
            data={"grant_type": "client_credentials"},
            auth=(
                self.settings.client_id,
                self.settings.get_password("client_secret"),
            ),
            timeout=15,
        )
        if resp.status_code != 200:
            raise GreytHRAuthError(
                f"Token fetch failed: HTTP {resp.status_code}"
            )

        token_data = resp.json()
        expires_in = token_data.get("expires_in", 3_888_000)
        self.settings.cached_token = token_data["access_token"]
        # Store as string — Frappe v16 iterates over datetime objects during field
        # validation, causing TypeError. Always store datetimes as strings in Settings.
        self.settings.token_expires_at = (
            now + timedelta(seconds=expires_in)
        ).strftime("%Y-%m-%d %H:%M:%S")
        self.settings.save(ignore_permissions=True)
        return token_data["access_token"]

    def _clear_token_cache(self) -> None:
        """Invalidate cached token so the next call fetches a fresh one."""
        self.settings.cached_token = None
        self.settings.token_expires_at = None
        self.settings.save(ignore_permissions=True)

    # -------------------------------------------------------------- request

    @rate_limited(calls=10, period=1)
    @retry(
        exceptions=(GreytHRServerError, requests.ConnectionError),
        tries=3,
        backoff=2,
        initial_delay=1,
    )
    def _request(
        self, method: str, path: str, _auth_retry: bool = True, **kwargs
    ) -> dict:
        """
        One HTTP call with auth headers, rate-limiting, error mapping,
        and one-shot auth retry on 401 or silent HTML rejection.

        The _auth_retry flag prevents infinite loops: the recursive retry
        call passes _auth_retry=False so a second auth failure raises immediately.
        """
        if self.settings.dry_run:
            frappe.logger().info(
                f"[DRY RUN] {method} {path} kwargs={list(kwargs.keys())}"
            )
            return {}

        url = self.settings.api_base_url + path
        headers = kwargs.pop("headers", {})
        headers.update(
            {
                "ACCESS-TOKEN": self._get_token(),
                "x-greythr-domain": self.settings.tenant_domain,
                "Accept": "application/json",
            }
        )

        resp = requests.request(method, url, headers=headers, timeout=30, **kwargs)

        # greytHR silent failure: stale/missing token returns 200 + HTML login page.
        if "text/html" in resp.headers.get("Content-Type", ""):
            if _auth_retry:
                self._clear_token_cache()
                return self._request(method, path, _auth_retry=False, **kwargs)
            raise GreytHRAuthError(
                "Got HTML response after token refresh — check client_id, "
                "client_secret, and tenant_domain in greytHR Settings"
            )

        if resp.status_code == 401:
            if _auth_retry:
                self._clear_token_cache()
                return self._request(method, path, _auth_retry=False, **kwargs)
            raise GreytHRAuthError(
                "401 after token refresh — check credentials in greytHR Settings"
            )

        if resp.status_code == 429:
            raise GreytHRRateLimitError(
                "greytHR rate limit hit — request will be retried"
            )

        if 500 <= resp.status_code < 600:
            raise GreytHRServerError(
                f"greytHR server error: HTTP {resp.status_code}: {resp.text[:200]}"
            )

        if 400 <= resp.status_code < 500:
            raise GreytHRClientError(
                f"greytHR client error: HTTP {resp.status_code}: {resp.text[:200]}"
            )

        return resp.json() if resp.content else {}

    # --------------------------------------------------------- public API

    def get(self, path: str, params: dict = None) -> dict:
        return self._request("GET", path, params=params)

    def post(self, path: str, json: dict = None, files: dict = None) -> dict:
        return self._request("POST", path, json=json, files=files)

    def put(self, path: str, json: dict = None) -> dict:
        return self._request("PUT", path, json=json)


# ---------------------------------------------------------------- bench callable

@frappe.whitelist()
def test_connection():
    """
    Smoke test callable from bench.

    bench --site hr.globexdigital.ai execute greythr_bridge.api.client.test_connection
    """
    client = GreytHRClient()
    result = client.get("/employee/v2/employees", params={"page": 1, "size": 1})
    employees = result.get("data", [])
    if employees:
        # Log employee ID only — never log name or email (PII / DPDP)
        print(f"OK — first employeeId: {employees[0].get('employeeId', 'unknown')}")
    else:
        print("OK — connection works, no employees returned")
