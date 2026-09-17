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

"""Top-level ``Client`` — the single entry point.

    from snapwonders import Client
    client = Client(api_key="sw_...")
    client.status()
    job = client.stego.hide(["secret.pdf", "cover.jpg"], password="Str0ng!Pass")
    report = client.analyse.run(["photo.jpg"])
    out = client.convert.run(["photo.jpg"], image_format="webp")

"""

from __future__ import annotations

from typing import Any

from ._http import DEFAULT_BASE_URL, HttpTransport
from .analyse import Analyse
from .convert import Convert
from .stego import Stego


class Client:
    """Authenticated client for the snapWONDERS API.

    Three product namespaces, all sharing the session/job/poll/download shape:
    ``client.stego`` (hide/reveal), ``client.analyse`` (forensics), ``client.convert`` (media).
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30.0,
    ) -> None:
        self._transport = HttpTransport(api_key, base_url=base_url, timeout=timeout)
        self.stego = Stego(self._transport)
        self.analyse = Analyse(self._transport)
        self.convert = Convert(self._transport)

    def status(self) -> dict[str, Any]:
        """``GET /api/status`` — no API key required. The 2-line quickstart that rescues leak 1."""
        return self._transport.request("GET", "/api/status", expected=(200, 503)).json()

    def close(self) -> None:
        self._transport.close()

    def __enter__(self) -> "Client":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
