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

"""Shared job/upload polling primitives used by every product namespace.

Free functions rather than a class hierarchy — the polling loops are the bug-prone part, so they
live in exactly one place and are unit-testable, while each namespace keeps its own explicit,
readable session/job classes on top.
"""

from __future__ import annotations

import random
import time
from typing import Any

from ._http import HttpTransport
from .exceptions import JobFailedError, SnapwondersError

TERMINAL_STATES = frozenset({"completed", "partial", "failed"})

# Polling cadence. Fixed-interval polling is a scaling hazard: N clients that start together poll in
# lockstep, so the server sees a synchronised burst every interval (a thundering herd). Instead we
# back off (fast first checks catch quick jobs; long jobs poll progressively less) and jitter each
# wait so concurrent clients desynchronise. The server can also override the cadence centrally by
# returning `retry_after`/`poll_after` (seconds) in the status body — the SDK will obey it.
_POLL_BACKOFF = 1.6      # each wait grows by this factor …
_POLL_MAX_INTERVAL = 15.0  # … up to this ceiling
_POLL_JITTER = 0.25     # ± this fraction of random jitter on every wait


def _next_wait(current: float, status_body: dict[str, Any]) -> tuple[float, float]:
    """Return ``(sleep_seconds, next_base_interval)`` for one poll cycle.

    A server-supplied ``retry_after``/``poll_after`` (seconds) wins — it lets the API throttle all
    SDK clients centrally under load. Otherwise use the backed-off base with ± jitter.
    """
    hint = status_body.get("retry_after") or status_body.get("poll_after")
    if hint is not None:
        try:
            base = float(hint)
            return base, base  # honour the server; do not keep growing while it dictates
        except (TypeError, ValueError):
            pass
    sleep = current * random.uniform(1.0 - _POLL_JITTER, 1.0 + _POLL_JITTER)
    return sleep, min(current * _POLL_BACKOFF, _POLL_MAX_INTERVAL)


def extract_files(payload: Any) -> list[dict[str, Any]]:
    """Normalise a ``session/{uid}/files`` response to a list of file dicts."""
    if isinstance(payload, dict):
        return payload.get("files", [])
    if isinstance(payload, list):
        return payload
    return []


def wait_for_uploads(
    transport: HttpTransport,
    files_path: str,
    *,
    poll_interval: float = 1.0,
    timeout: float = 120.0,
) -> list[dict[str, Any]]:
    """Poll ``files_path`` until every uploaded file reports ``completed``."""
    deadline = time.monotonic() + timeout
    while True:
        files = extract_files(transport.request("GET", files_path, expected=(200,)).json())
        if files and all(f.get("status") == "completed" for f in files):
            return files
        if time.monotonic() > deadline:
            raise SnapwondersError(f"Uploads at {files_path} not complete within {timeout:.0f}s")
        time.sleep(poll_interval)


def poll_job(
    transport: HttpTransport,
    status_path: str,
    *,
    poll_interval: float = 1.5,
    timeout: float = 900.0,
) -> dict[str, Any]:
    """Poll ``status_path`` until the job reaches a terminal state; return the final status body.

    ``poll_interval`` is the **initial** gap between checks; it backs off (× ~1.6, capped at 15s)
    with ± jitter so many concurrent clients do not hammer the API in lockstep. A server-sent
    ``retry_after``/``poll_after`` in the status body overrides the cadence. See the module notes.
    """
    deadline = time.monotonic() + timeout
    interval = poll_interval
    while True:
        data = transport.request("GET", status_path, expected=(200,)).json()
        if data.get("status") in TERMINAL_STATES:
            return data
        if time.monotonic() > deadline:
            raise SnapwondersError(f"Job at {status_path} did not finish within {timeout:.0f}s")
        sleep, interval = _next_wait(interval, data)
        # Never sleep past the deadline — keeps the timeout honest under a long backoff/hint.
        time.sleep(min(sleep, max(0.0, deadline - time.monotonic())))


def check_terminal(status_body: dict[str, Any], *, uid: str, strict: bool) -> None:
    """Raise :class:`JobFailedError` on ``failed`` (and on ``partial`` when ``strict``).

    The human-readable reason lives in ``progress_message``, **not** ``error`` (which may be null).
    Prefer ``error`` (the sanitised field when the API sets it) and fall back to ``progress_message``.
    """
    status = status_body.get("status")
    if status == "failed" or (strict and status == "partial"):
        reason = status_body.get("error") or status_body.get("progress_message")
        message = f"Job {uid} ended as {status}"
        if reason:
            message += f": {reason}"
        raise JobFailedError(message, error=reason, status=status)
