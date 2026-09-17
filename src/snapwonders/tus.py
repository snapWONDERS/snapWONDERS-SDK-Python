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

"""Hand-rolled TUS 1.0.0 upload — the resumable upload protocol the API uses for file transfer.

Two-phase: ``POST /api/tus`` to create the upload resource, then chunked ``PATCH`` to stream the
bytes. Supports HEAD-resume (query the current offset and continue) so a dropped connection does
not restart the whole transfer. The create response ``Location`` is absolute and ``Upload-Length``
is sent on create.
"""

from __future__ import annotations

import base64
import os
import uuid
from pathlib import Path

from ._http import HttpTransport
from .exceptions import TusUploadError

TUS_VERSION = "1.0.0"
_DEFAULT_CHUNK = 5 * 1024 * 1024  # 5 MiB


def _b64(value: str) -> str:
    return base64.b64encode(value.encode("utf-8")).decode("ascii")


def _build_metadata(fields: dict[str, str]) -> str:
    """Encode an ``Upload-Metadata`` header: comma-separated ``key <base64(value)>`` pairs."""
    return ",".join(f"{key} {_b64(value)}" for key, value in fields.items())


def _encode_metadata(upload_uid: str, step: int) -> str:
    """The minimal two-field metadata (kept for tests/back-compat)."""
    return _build_metadata({"upload_uid": upload_uid, "step": str(step)})


def upload_file(
    transport: HttpTransport,
    file_path: str | os.PathLike[str],
    *,
    upload_uid: str,
    step: int,
    chunk_size: int = _DEFAULT_CHUNK,
) -> str:
    """Upload one file for ``upload_uid`` at ``step``. Returns the TUS upload URL used.

    Raises :class:`TusUploadError` on any failure.
    """
    path = Path(file_path)
    if not path.is_file():
        raise TusUploadError(f"Not a file: {path}")
    total = path.stat().st_size

    # Phase 1 — create. Send `name` so the server records the original filename (feeds
    # input_original_names / reveal-side filename recovery) and a stable `client_upload_id` so a
    # retried create does not create a duplicate upload row (TusController reads both).
    create = transport.request(
        "POST",
        "/api/tus",
        headers={
            "Tus-Resumable": TUS_VERSION,
            "Upload-Length": str(total),
            "Upload-Metadata": _build_metadata({
                "upload_uid": upload_uid,
                "step": str(step),
                "name": path.name,
                "client_upload_id": str(uuid.uuid4()),
            }),
        },
        expected=(200, 201),
    )
    location = create.headers.get("Location")
    if not location:
        raise TusUploadError("TUS create returned no Location header")
    upload_path = _to_relative(location, transport.base_url)

    # Phase 2 — stream in chunks from the current server offset (resume-safe).
    offset = _server_offset(transport, upload_path)
    with path.open("rb") as fh:
        fh.seek(offset)
        while offset < total:
            chunk = fh.read(chunk_size)
            if not chunk:
                break
            resp = transport.request(
                "PATCH",
                upload_path,
                headers={
                    "Tus-Resumable": TUS_VERSION,
                    "Upload-Offset": str(offset),
                    "Content-Type": "application/offset+octet-stream",
                },
                content=chunk,
                expected=(200, 204),
            )
            new_offset = resp.headers.get("Upload-Offset")
            offset = int(new_offset) if new_offset is not None else offset + len(chunk)

    if offset != total:
        raise TusUploadError(f"Upload incomplete: sent to offset {offset} of {total}")
    return upload_path


def _server_offset(transport: HttpTransport, upload_path: str) -> int:
    """HEAD the upload to learn how many bytes the server already has (0 for a fresh create)."""
    resp = transport.request(
        "HEAD",
        upload_path,
        headers={"Tus-Resumable": TUS_VERSION},
        expected=(200, 204),
    )
    return int(resp.headers.get("Upload-Offset", "0"))


def _to_relative(location: str, base_url: str) -> str:
    """Normalise a create ``Location`` to a base-relative path for subsequent PATCH/HEAD."""
    if location.startswith(base_url):
        return location[len(base_url):]
    if location.startswith("http://") or location.startswith("https://"):
        # Absolute but different host — keep the path portion only.
        from urllib.parse import urlparse

        return urlparse(location).path
    return location if location.startswith("/") else "/" + location
