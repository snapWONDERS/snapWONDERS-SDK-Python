#
# snapWONDERS API — Python SDK
# API version: 1.0
#
# Copyright (c) 2026 Kenneth Springer @ snapWONDERS. MIT Licensed — see LICENSE.
# The MIT licence covers this client library only; the snapWONDERS API it calls is proprietary.
#
# Author: Kenneth Springer @ snapWONDERS <kenneth@snapwonders.com> (https://kennethbspringer.au)
#
# All the snapWONDERS API services are available over the Clearnet / **Web** and Dark Web **Tor** and **I2P**
# Read details: https://snapwonders.com/developers
#
#

"""Typed exceptions for the snapWONDERS API client.

Every error the SDK raises is one of these, so callers can branch on failure kind rather than
inspecting HTTP status codes. Mapping from the wire is done in ``_http.raise_for_response``.
"""

from __future__ import annotations


class SnapwondersError(Exception):
    """Base class for every error raised by the SDK."""


class AuthError(SnapwondersError):
    """Missing, malformed, unknown, or revoked API key (HTTP 401/403)."""


class SessionExpiredError(SnapwondersError):
    """The 24-hour upload session window has passed (HTTP 410)."""


class ProRequiredError(SnapwondersError):
    """A Pro-only option (e.g. ``vault_profile_id``) was used on a free account (HTTP 402)."""


class MaintenanceError(SnapwondersError):
    """snapWONDERS is temporarily unavailable for maintenance (HTTP 503 + ``status: MAINTENANCE``).

    Distinct from a transient 5xx: the service is deliberately unavailable and there is nothing wrong
    with the caller's request. The API sends a ``Retry-After``, surfaced here as ``retry_after`` so
    the caller can wait properly or fail fast.
    """

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class RateLimitError(SnapwondersError):
    """Rate limited (HTTP 429). ``retry_after`` is seconds if the server supplied it."""

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class JobFailedError(SnapwondersError):
    """A hide/reveal/analyse/convert job finished as ``failed`` (or ``partial`` when strict).

    ``error`` carries the safe, server-sanitised description from the job status response.
    """

    def __init__(self, message: str, *, error: str | None = None, status: str | None = None) -> None:
        super().__init__(message)
        self.error = error
        self.status = status


class UploadError(SnapwondersError):
    """A file could not be uploaded, by whichever method was used.

    Named for what it is: the SDK has two upload paths (direct and TUS) and a caller does not
    choose between them, so an error naming one protocol would be misleading half the time.
    """


class TusUploadError(UploadError):
    """A TUS create/PATCH/resume step failed."""


class NetworkError(SnapwondersError):
    """A transport-level failure (connection refused, DNS, timeout) after retries were exhausted."""


class ApiError(SnapwondersError):
    """Any other non-2xx API response. ``status_code`` and ``body`` are attached for inspection."""

    def __init__(self, message: str, *, status_code: int, body: object = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body
