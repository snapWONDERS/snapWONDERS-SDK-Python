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

"""Low-level HTTP transport: auth header, retries, and error mapping.

This is the single place the SDK talks to the network. Everything else composes calls through
``HttpTransport``. Kept deliberately thin — no endpoint knowledge lives here.

Maps API error responses to typed exceptions — see ``raise_for_response``.
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from .exceptions import (
    ApiError,
    AuthError,
    MaintenanceError,
    NetworkError,
    ProRequiredError,
    RateLimitError,
    SessionExpiredError,
)

DEFAULT_BASE_URL = "https://snapwonders.com"
_RETRY_STATUSES = frozenset({500, 502, 503, 504})
_MAX_RETRIES = 2  # retries after the first try — 3 attempts total
_BACKOFF_CAP_S = 30.0


class HttpTransport:
    """Wraps an ``httpx.Client`` with the API key header, retry-on-5xx, and error mapping."""

    def __init__(
        self,
        api_key: str | None,
        base_url: str = DEFAULT_BASE_URL,
        *,
        timeout: float = 30.0,
        client: httpx.Client | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        headers = {"X-Api-Key": api_key} if api_key else {}
        self._client = client or httpx.Client(base_url=self._base_url, timeout=timeout, headers=headers)

    @property
    def base_url(self) -> str:
        return self._base_url

    def request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        headers: dict[str, str] | None = None,
        content: bytes | None = None,
        expected: tuple[int, ...] = (200, 201),
    ) -> httpx.Response:
        """Send a request, retrying transient 5xx with capped exponential backoff.

        ``path`` is relative to the base URL (e.g. ``/api/status``). Raises a typed exception on
        any non-``expected`` status.
        """
        attempt = 0
        while True:
            attempt += 1
            try:
                response = self._client.request(method, path, json=json, headers=headers, content=content)
            except httpx.TransportError as exc:
                # Connection refused / DNS / read timeout — retry, then surface as a typed error
                # (never let a raw httpx exception escape the SDK's own exception hierarchy).
                if attempt <= _MAX_RETRIES:
                    time.sleep(min(_BACKOFF_CAP_S, 2.0 ** (attempt - 1)))
                    continue
                raise NetworkError(f"Network error contacting {self._base_url}: {type(exc).__name__}") from exc
            # A maintenance 503 is deliberate, not transient — the server asks for ~300s. Burning
            # the retry budget over a few seconds cannot help, so surface it immediately and let
            # the caller decide whether to wait out the window.
            if (
                response.status_code in _RETRY_STATUSES
                and attempt <= _MAX_RETRIES
                and not _is_maintenance(response)
            ):
                time.sleep(min(_BACKOFF_CAP_S, 2.0 ** (attempt - 1)))
                continue
            if response.status_code not in expected:
                raise_for_response(response)
            return response

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> HttpTransport:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


def _is_maintenance(response: httpx.Response) -> bool:
    """True for the maintenance 503.

    The API returns ``{"status": "MAINTENANCE", ...}`` with a ``Retry-After`` header and no
    ``message``/``error`` key, so it needs its own check rather than falling through to
    ``_extract_message``.
    """
    if response.status_code != 503:
        return False
    try:
        body = response.json()
    except Exception:  # noqa: BLE001 — HTML or empty body
        return False
    return isinstance(body, dict) and body.get("status") == "MAINTENANCE"


def raise_for_response(response: httpx.Response) -> None:
    """Map a non-2xx response to the correct typed exception."""
    code = response.status_code
    body: Any
    try:
        body = response.json()
    except Exception:  # noqa: BLE001 — body may be binary or empty
        body = response.text

    message = _extract_message(body) or f"HTTP {code}"

    if _is_maintenance(response):
        retry_after = response.headers.get("Retry-After")
        wait = f" Retry after {retry_after}s." if retry_after else " Try again shortly."
        raise MaintenanceError(
            "snapWONDERS is temporarily unavailable for maintenance."
            + wait
            + " Your request was not processed and nothing is wrong with it.",
            retry_after=float(retry_after) if retry_after else None,
        )
    if code in (401, 403):
        raise AuthError(message)
    if code == 402:
        raise ProRequiredError(message)
    if code == 410:
        raise SessionExpiredError(message)
    if code == 429:
        retry_after = response.headers.get("Retry-After")
        raise RateLimitError(message, retry_after=float(retry_after) if retry_after else None)
    raise ApiError(message, status_code=code, body=body)


def _extract_message(body: Any) -> str | None:
    if isinstance(body, dict):
        return body.get("message") or body.get("error")
    if isinstance(body, str) and body:
        return body
    return None
