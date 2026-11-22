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

"""Chooses the upload method, so nothing above this layer has to know there are two.

The API offers a single-request direct upload for files under a server-declared cap, and the
resumable TUS protocol for everything else. Which one is right is a mechanical decision — file
size against ``max_upload_bytes`` — and not something a caller of this SDK should ever have to
think about, so it is made here and only here.
"""

from __future__ import annotations

import os
from pathlib import Path

from . import direct, tus
from ._http import HttpTransport


def upload_file(
    transport: HttpTransport,
    file_path: str | os.PathLike[str],
    *,
    upload_uid: str,
    step: int,
    max_upload_bytes: int | None = None,
) -> str:
    """Upload one file by whichever method fits, and return an identifier for it.

    ``max_upload_bytes`` should be the value the session-create response reported. Passing it
    means the cap can change server-side without an SDK release; omitting it falls back to the
    figure this SDK was built against.

    ⚠️ **The returned string means different things by method.** Direct upload returns the
    server's ``storage_uid``; TUS returns the upload URL it used. That difference predates this
    router — it is what each underlying function has always returned — but before direct upload
    existed, ``session.upload()`` always returned the TUS URL, so anyone relying on that value
    for a small file now gets a ``storage_uid`` instead.

    Neither value is needed for the normal flow: uploads are confirmed with
    ``session.files()`` / ``wait_for_uploads()`` and jobs are keyed by ``upload_uid``. The
    return is a diagnostic aid, and is documented rather than unified because normalising it
    would mean either discarding information or changing what ``tus.upload_file()`` returns,
    and that function is deliberately untouched.
    """
    limit = max_upload_bytes if max_upload_bytes is not None else direct.DEFAULT_MAX_BYTES
    size = Path(file_path).stat().st_size

    if size <= limit:
        return direct.upload_file(
            transport, file_path, upload_uid=upload_uid, step=step,
        )

    # Over the cap, or the caller wants resume behaviour: the protocol earns its cost here.
    return tus.upload_file(
        transport, file_path, upload_uid=upload_uid, step=step,
    )
