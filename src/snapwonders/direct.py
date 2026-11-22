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

"""Direct upload — the whole file in one request, for anything under the server's size cap.

The alternative to :mod:`snapwonders.tus`. TUS costs a create, one or more chunked PATCHes and
sometimes a HEAD; this is a single POST with the file as the request body. For the common case —
one photo, well under the cap — that is one round trip instead of three, which matters most on
the high-latency links this API is often used over (Tor and I2P).

Callers do not choose between the two. :func:`snapwonders.upload_router.upload_file` picks, using the
``max_upload_bytes`` the server reports when the session is created.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

from ._http import HttpTransport
from .exceptions import UploadError

# Mirrors the server's own fallback (`upload.direct.max_bytes`). Only used when a session
# response did not carry `max_upload_bytes` — prefer the server's figure, which can move
# without an SDK release.
DEFAULT_MAX_BYTES = 99_614_720  # 95 MiB


def upload_file(
    transport: HttpTransport,
    file_path: str | os.PathLike[str],
    *,
    upload_uid: str,
    step: int,
    content_type: str = "application/octet-stream",
) -> str:
    """Upload one file for ``upload_uid`` at ``step`` in a single request.

    Returns the ``storage_uid`` the server assigned. Raises :class:`UploadError` on failure — the same base ``TusUploadError`` inherits from,
    so callers can treat both upload paths identically.
    """
    path = Path(file_path)
    if not path.is_file():
        raise UploadError(f"Not a file: {path}")

    # Read the whole file into memory rather than handing the transport a file object.
    #
    # This is deliberate and must not be "optimised" into streaming. httpx sets Content-Length
    # when given a bytes object, but switches to Transfer-Encoding: chunked when given a
    # file-like one — and the server refuses chunked uploads with 411, because without a
    # declared length a body truncated in transit cannot be told apart from a complete one.
    # Analysing a truncated file would return confident findings about a file the user never
    # sent, which is why that rule exists. Streaming here looks like a clear win in review
    # (less memory!) and silently breaks every upload.
    #
    # The memory cost is bounded by the size check the caller already made — this path only
    # runs for files under max_upload_bytes.
    body = path.read_bytes()

    response = transport.request(
        "POST",
        "/api/upload",
        headers={
            "X-Upload-Uid": upload_uid,
            "X-Upload-Step": str(step),
            "X-Filename": path.name,
            "Content-Type": content_type,
            # Same idempotency contract as the TUS path: a retry after a lost response returns
            # the original result instead of storing the file twice.
            "X-Client-Upload-Id": str(uuid.uuid4()),
        },
        content=body,
        expected=(200, 201),
    )

    payload = response.json()
    storage_uid = (payload.get("file") or {}).get("storage_uid")
    if not storage_uid:
        raise UploadError("Direct upload returned no storage_uid")
    return storage_uid
