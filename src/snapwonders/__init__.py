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

"""snapwonders — official Python client for the snapWONDERS API.

Steganography, forensic media analysis, and format conversion, wrapping the resumable upload and the
session → job → poll → download flow into a few lines.
"""

from __future__ import annotations

from .client import Client
from .exceptions import (
    ApiError,
    AuthError,
    JobFailedError,
    NetworkError,
    ProRequiredError,
    MaintenanceError,
    RateLimitError,
    SessionExpiredError,
    TusUploadError,
    UploadError,
    SnapwondersError,
)
from .models import AnalyseItem, ResultFile

__version__ = "0.1.2"

__all__ = [
    "Client",
    "ResultFile",
    "AnalyseItem",
    "SnapwondersError",
    "AuthError",
    "SessionExpiredError",
    "ProRequiredError",
    "MaintenanceError",
    "RateLimitError",
    "JobFailedError",
    "TusUploadError",
    "UploadError",
    "NetworkError",
    "ApiError",
    "__version__",
]
