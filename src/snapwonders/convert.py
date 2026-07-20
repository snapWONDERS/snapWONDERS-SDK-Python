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

"""Media conversion surface.

``POST /api/convert/session`` → TUS upload (all files at step 1) → ``POST /api/convert/job`` →
poll ``GET /api/convert/job/{uid}`` → ``GET /api/convert/job/{uid}/results`` →
``GET /api/convert/download/{asset_id}``.

Convert job options pass through untyped (the API validates them). The image format key is
``image_format`` (jpeg/png/webp/avif/heic/jxl); video is ``video_format``.
"""

from __future__ import annotations

import os
from typing import Any

from . import _base, tus
from ._http import HttpTransport
from .models import ResultFile

_CONVERT_DOWNLOAD_PREFIX = "/api/convert/download"


class ConvertJob:
    """A queued convert job; poll with :meth:`wait`, then :meth:`results`."""

    def __init__(self, transport: HttpTransport, upload_uid: str, job_uid: str) -> None:
        self._t = transport
        # Both status and results are keyed by the session's upload_uid, not the job_uid (which
        # differs for convert). Poll and fetch by upload_uid to match the API contract.
        self.upload_uid = upload_uid
        self.job_uid = job_uid
        self.status: str | None = None
        self.error: str | None = None

    def wait(self, *, poll_interval: float = 1.5, timeout: float = 900.0, strict: bool = False) -> "ConvertJob":
        final = _base.poll_job(self._t, f"/api/convert/job/{self.upload_uid}", poll_interval=poll_interval, timeout=timeout)
        self.status, self.error = final.get("status"), final.get("error")
        _base.check_terminal(final, uid=self.job_uid, strict=strict)
        return self

    def results(self) -> list[ResultFile]:
        data = self._t.request("GET", f"/api/convert/job/{self.upload_uid}/results", expected=(200,)).json()
        # The API returns `result_files`; `items` is kept as a fallback.
        items = data.get("result_files") or data.get("items") or []
        return [
            ResultFile.from_json(item, transport=self._t, download_prefix=_CONVERT_DOWNLOAD_PREFIX)
            for item in items
            if item.get("asset_id")
        ]


class ConvertSession:
    """An open convert upload session — one or more files, all at step 1."""

    def __init__(self, transport: HttpTransport, upload_uid: str) -> None:
        self._t = transport
        self.upload_uid = upload_uid

    def upload(self, file_path: str | os.PathLike[str]) -> str:
        return tus.upload_file(self._t, file_path, upload_uid=self.upload_uid, step=1)

    def files(self) -> list[dict[str, Any]]:
        return _base.extract_files(
            self._t.request("GET", f"/api/convert/session/{self.upload_uid}/files", expected=(200,)).json()
        )

    def wait_for_uploads(self, *, poll_interval: float = 1.0, timeout: float = 120.0) -> "ConvertSession":
        _base.wait_for_uploads(
            self._t, f"/api/convert/session/{self.upload_uid}/files", poll_interval=poll_interval, timeout=timeout
        )
        return self

    def start_job(self, *, expiry: str = "1d", **options: Any) -> ConvertJob:
        """Queue conversion. ``options`` are the convert encoding keys (e.g. output format, resize)."""
        body: dict[str, Any] = {"upload_uid": self.upload_uid, "expiry": expiry}
        body.update(options)
        data = self._t.request("POST", "/api/convert/job", json=body, expected=(200, 201)).json()
        return ConvertJob(self._t, self.upload_uid, data["job_uid"])


class Convert:
    """``client.convert`` — session factory plus a one-shot ``run`` helper."""

    def __init__(self, transport: HttpTransport) -> None:
        self._t = transport

    def create_session(self) -> ConvertSession:
        data = self._t.request("POST", "/api/convert/session", json={}, expected=(200, 201)).json()
        return ConvertSession(self._t, data["upload_uid"])

    def run(
        self,
        files: list[str | os.PathLike[str]],
        *,
        expiry: str = "1d",
        **options: Any,
    ) -> ConvertJob:
        """One-shot: create a session, upload every file, convert to completion."""
        if not files:
            raise ValueError("run() needs at least one file to convert")
        session = self.create_session()
        for f in files:
            session.upload(f)
        session.wait_for_uploads()
        return session.start_job(expiry=expiry, **options).wait()
