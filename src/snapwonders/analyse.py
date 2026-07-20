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

"""Forensic analysis surface.

``POST /api/analyse/session`` → TUS upload (all files at step 1) → ``POST /api/analyse/job`` →
poll ``GET /api/analyse/job/{uid}`` → ``GET /api/analyse/result/{job_uid}`` (clean JSON with
per-file grades, counts, and downloadable overlay assets via ``GET /api/analyse/asset/{id}``).

The ``/analyse/result`` container keys are read defensively — their exact names can vary.
"""

from __future__ import annotations

import os
from typing import Any

from . import _base, tus
from ._http import HttpTransport
from .models import AnalyseItem


def _extract_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("files", "items", "results"):
            if isinstance(payload.get(key), list):
                return payload[key]
    return []


class AnalyseJob:
    """A queued analyse job; poll with :meth:`wait`, then read :meth:`results`."""

    def __init__(self, transport: HttpTransport, upload_uid: str, job_uid: str) -> None:
        self._t = transport
        # The status endpoint is keyed by the session's upload_uid; only the /result/{jobUid}
        # endpoint is keyed by job_uid. These two IDs differ, so status is polled by upload_uid.
        self.upload_uid = upload_uid
        self.job_uid = job_uid
        self.status: str | None = None
        self.error: str | None = None

    def wait(self, *, poll_interval: float = 1.5, timeout: float = 900.0, strict: bool = False) -> "AnalyseJob":
        final = _base.poll_job(self._t, f"/api/analyse/job/{self.upload_uid}", poll_interval=poll_interval, timeout=timeout)
        self.status, self.error = final.get("status"), final.get("error")
        _base.check_terminal(final, uid=self.job_uid, strict=strict)
        return self

    def results(self) -> list[AnalyseItem]:
        """Per-file forensic verdicts (grade, face/text counts, flags) + downloadable assets."""
        # This endpoint is keyed by job_uid, unlike the status poll above.
        data = self._t.request("GET", f"/api/analyse/result/{self.job_uid}", expected=(200,)).json()
        return [AnalyseItem.from_json(item, transport=self._t) for item in _extract_items(data)]


class AnalyseSession:
    """An open analyse upload session — one or more files, all at step 1."""

    def __init__(self, transport: HttpTransport, upload_uid: str) -> None:
        self._t = transport
        self.upload_uid = upload_uid

    def upload(self, file_path: str | os.PathLike[str]) -> str:
        return tus.upload_file(self._t, file_path, upload_uid=self.upload_uid, step=1)

    def files(self) -> list[dict[str, Any]]:
        return _base.extract_files(
            self._t.request("GET", f"/api/analyse/session/{self.upload_uid}/files", expected=(200,)).json()
        )

    def wait_for_uploads(self, *, poll_interval: float = 1.0, timeout: float = 120.0) -> "AnalyseSession":
        _base.wait_for_uploads(
            self._t, f"/api/analyse/session/{self.upload_uid}/files", poll_interval=poll_interval, timeout=timeout
        )
        return self

    def start_job(self, *, expiry: str = "1d", **options: Any) -> AnalyseJob:
        """Queue analysis. ``options`` = ``face_detection``, ``text_detection``,
        ``face_sensitivity`` (``standard``/``thorough``), ``forensic_depth`` (``standard``/``deep``)."""
        body: dict[str, Any] = {"upload_uid": self.upload_uid, "expiry": expiry}
        body.update(options)
        data = self._t.request("POST", "/api/analyse/job", json=body, expected=(200, 201)).json()
        return AnalyseJob(self._t, self.upload_uid, data["job_uid"])


class Analyse:
    """``client.analyse`` — session factory plus a one-shot ``run`` helper."""

    def __init__(self, transport: HttpTransport) -> None:
        self._t = transport

    def create_session(self) -> AnalyseSession:
        data = self._t.request("POST", "/api/analyse/session", json={}, expected=(200, 201)).json()
        return AnalyseSession(self._t, data["upload_uid"])

    def run(
        self,
        files: list[str | os.PathLike[str]],
        *,
        expiry: str = "1d",
        **options: Any,
    ) -> AnalyseJob:
        """One-shot: create a session, upload every file, run analysis to completion."""
        if not files:
            raise ValueError("run() needs at least one file to analyse")
        session = self.create_session()
        for f in files:
            session.upload(f)
        session.wait_for_uploads()
        return session.start_job(expiry=expiry, **options).wait()
