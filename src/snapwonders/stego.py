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

"""Steganography (hide / reveal) — the flagship flow.

Wraps ``POST /api/session`` → TUS upload → ``POST /api/job`` → poll ``GET /api/job/{uid}`` →
``GET /api/job/{uid}/results`` → ``GET /api/job/download/{asset_id}`` into ergonomic calls.

"""

from __future__ import annotations

import os
from typing import Any

from . import _base, upload_router
from ._http import HttpTransport
from .models import ResultFile

_JOB_DOWNLOAD_PREFIX = "/api/job/download"


class StegoJob:
    """A queued hide/reveal job; poll it with :meth:`wait`, then :meth:`results`."""

    def __init__(self, transport: HttpTransport, upload_uid: str, job_uid: str, *, job_type: str) -> None:
        self._t = transport
        # Status and results are keyed by the session's upload_uid, not the job_uid. Poll and
        # fetch by upload_uid to match the API contract.
        self.upload_uid = upload_uid
        self.job_uid = job_uid
        self.job_type = job_type
        self.status: str | None = None
        self.error: str | None = None
        self.progress_message: str | None = None

    def refresh(self) -> "StegoJob":
        data = self._t.request("GET", f"/api/job/{self.upload_uid}", expected=(200,)).json()
        self.status, self.error = data.get("status"), data.get("error")
        self.progress_message = data.get("progress_message")
        return self

    def wait(self, *, poll_interval: float = 1.5, timeout: float = 900.0, strict: bool = False) -> "StegoJob":
        """Poll until terminal. Raises :class:`JobFailedError` on ``failed`` (``partial`` when strict)."""
        final = _base.poll_job(self._t, f"/api/job/{self.upload_uid}", poll_interval=poll_interval, timeout=timeout)
        self.status, self.error = final.get("status"), final.get("error")
        self.progress_message = final.get("progress_message")
        _base.check_terminal(final, uid=self.job_uid, strict=strict)
        return self

    def results(self) -> list[ResultFile]:
        data = self._t.request("GET", f"/api/job/{self.upload_uid}/results", expected=(200,)).json()
        return [
            ResultFile.from_json(f, transport=self._t, download_prefix=_JOB_DOWNLOAD_PREFIX)
            for f in data.get("result_files", [])
        ]


class StegoSession:
    """An open hide/reveal upload session. Upload files, then start a job."""

    def __init__(self, transport: HttpTransport, upload_uid: str, *, session_type: str, max_upload_bytes: int | None = None) -> None:
        self._t = transport
        self.upload_uid = upload_uid
        self.session_type = session_type  # "hide" | "reveal"
        # Reported by the server at session creation, so the direct-upload cap can move
        # server-side without an SDK release; None falls back to the built-in figure.
        self.max_upload_bytes = max_upload_bytes

    def upload(self, file_path: str | os.PathLike[str], *, step: int) -> str:
        """Upload one file at ``step`` (1 = secret/stego input, 2 = cover for hide)."""
        return upload_router.upload_file(
            self._t, file_path,
            upload_uid=self.upload_uid, step=step,
            max_upload_bytes=self.max_upload_bytes,
        )

    def files(self) -> list[dict[str, Any]]:
        return _base.extract_files(
            self._t.request("GET", f"/api/session/{self.upload_uid}/files", expected=(200,)).json()
        )

    def wait_for_uploads(self, *, poll_interval: float = 1.0, timeout: float = 120.0) -> "StegoSession":
        _base.wait_for_uploads(
            self._t, f"/api/session/{self.upload_uid}/files", poll_interval=poll_interval, timeout=timeout
        )
        return self

    def start_job(self, *, password: str, expiry: str = "1d", **options: Any) -> StegoJob:
        """Queue the job. ``options`` are the hide-only encoding keys (ignored for reveal)."""
        body: dict[str, Any] = {"upload_uid": self.upload_uid, "password": password, "expiry": expiry}
        body.update(options)
        data = self._t.request("POST", "/api/job", json=body, expected=(200, 201)).json()
        return StegoJob(self._t, self.upload_uid, data["job_uid"], job_type=data.get("job_type", self.session_type))


class Stego:
    """``client.stego`` — session factory plus the one-shot ``hide`` / ``reveal`` helpers."""

    def __init__(self, transport: HttpTransport) -> None:
        self._t = transport

    def create_session(self, session_type: str) -> StegoSession:
        if session_type not in ("hide", "reveal"):
            raise ValueError("session_type must be 'hide' or 'reveal'")
        data = self._t.request("POST", "/api/session", json={"type": session_type}, expected=(200, 201)).json()
        return StegoSession(self._t, data["upload_uid"], session_type=session_type, max_upload_bytes=data.get("max_upload_bytes"))

    def hide(
        self,
        files: list[str | os.PathLike[str]],
        *,
        password: str,
        expiry: str = "1d",
        **options: Any,
    ) -> StegoJob:
        """One-shot: create a hide session, upload secret(s) then cover, run to completion.

        Convention: the **last** path is the cover (step 2); all earlier paths are secrets (step 1).
        """
        if len(files) < 2:
            raise ValueError("hide() needs at least one secret and one cover (>=2 files)")
        session = self.create_session("hide")
        *secrets, cover = files
        for secret in secrets:
            session.upload(secret, step=1)
        session.upload(cover, step=2)
        session.wait_for_uploads()
        return session.start_job(password=password, expiry=expiry, **options).wait()

    def reveal(
        self,
        stego_file: str | os.PathLike[str],
        *,
        password: str,
        expiry: str = "1d",
    ) -> StegoJob:
        """One-shot: create a reveal session, upload the stego file, run to completion."""
        session = self.create_session("reveal")
        session.upload(stego_file, step=1)
        session.wait_for_uploads()
        return session.start_job(password=password, expiry=expiry).wait()
