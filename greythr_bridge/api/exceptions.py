class GreytHRError(Exception):
    """Base exception for all greytHR API errors."""

class GreytHRAuthError(GreytHRError):
    """OAuth token rejected or credentials invalid."""

class GreytHRRateLimitError(GreytHRError):
    """greytHR returned 429 — back off and retry later."""

class GreytHRServerError(GreytHRError):
    """greytHR returned 5xx — eligible for retry with backoff."""

class GreytHRClientError(GreytHRError):
    """greytHR returned 4xx (non-401) — bad request, no retry."""

class ZohoSignError(Exception):
    """Base exception for all Zoho Sign API errors."""
