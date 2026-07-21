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

"""Lightweight result/job value objects returned to callers.

Deliberately plain — thin views over the JSON the API returns, with convenience methods
(``download``). No validation logic; the API is authoritative. Field parsing is lenient because the
exact result JSON keys can differ slightly per product area.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ._http import HttpTransport


@dataclass(slots=True)
class ResultFile:
    """One downloadable output (a stego image, recovered secret, converted file, analyse asset…)."""

    asset_id: str
    name: str
    mime_type: str | None
    file_size: int | None
    _transport: "HttpTransport"
    _download_path: str  # e.g. "/api/job/download/{asset_id}"

    def download(self, dest: str | os.PathLike[str]) -> Path:
        """Stream this asset to ``dest`` and return the written path.

        ``dest`` may be a file path (``"out/photo.avif"``) or a directory (``"out/"``, ``"out"`` when
        it already exists), in which case the server-supplied :attr:`name` is appended.

        A **trailing separator means "directory"** even when it does not exist yet — ``Path.is_dir()``
        is False for a path yet to be created, so a trailing ``/`` must be honoured explicitly or the
        asset is written to a *file* literally named e.g. ``out``.
        """
        raw = os.fspath(dest)
        target = Path(dest)
        if raw.endswith(("/", "\\")) or target.is_dir():
            target = target / self.name
        target.parent.mkdir(parents=True, exist_ok=True)
        resp = self._transport.request("GET", self._download_path, expected=(200,))
        target.write_bytes(resp.content)
        return target

    @classmethod
    def from_json(
        cls,
        data: dict,
        *,
        transport: "HttpTransport",
        download_prefix: str,
    ) -> "ResultFile":
        asset_id = data["asset_id"]
        # Convert results carry the converted filename in `output_name` and the original in
        # `name` — prefer the converted name so a WebP output isn't saved as `photo.jpg`.
        # Stego uses `name`; analyse assets inject a name.
        name = data.get("output_name") or data.get("name") or data.get("filename") or asset_id
        return cls(
            asset_id=asset_id,
            name=name,
            mime_type=data.get("mime_type"),
            file_size=data.get("file_size") or data.get("size_bytes"),
            _transport=transport,
            _download_path=f"{download_prefix}/{asset_id}",
        )


@dataclass(slots=True)
class AnalyseItem:
    """Forensic verdict for one analysed file, plus its downloadable overlay assets.

    Field names are read leniently (``overall_grade``/``grade`` etc.) — confirm against the live
    ``/api/analyse/result/{job_uid}`` shape — exact field names can vary.
    """

    filename: str | None
    grade: str | None
    face_count: int | None
    text_region_count: int | None
    watermark_flagged: bool | None
    steganography_suspected: bool | None
    #: Forensic verdicts, when the API includes them: ``ai_generation`` (AI-generation verdict),
    #: ``c2pa`` (Content Credentials), ``camera_fingerprint`` (device match), ``findings`` (key
    #: findings). A plain dict — the exact keys grow over time; read what you need.
    verdicts: dict[str, Any] = field(default_factory=dict)
    assets: list[ResultFile] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_json(cls, data: dict, *, transport: "HttpTransport") -> "AnalyseItem":
        # Analyse assets are keyed by `category` (e.g. "ela_map", "face_overlay") — not name/type —
        # and also carry mime_type/file_size. Pass the whole asset through so those flow into
        # ResultFile, injecting a sensible display name.
        assets = [
            ResultFile.from_json(
                {**a, "name": a.get("name") or a.get("category") or a.get("type") or a["asset_id"]},
                transport=transport,
                download_prefix="/api/analyse/asset",
            )
            for a in data.get("assets", [])
            if a.get("asset_id")
        ]
        return cls(
            filename=data.get("filename") or data.get("name"),
            grade=data.get("overall_grade") or data.get("grade"),
            face_count=data.get("face_count"),
            text_region_count=data.get("text_region_count"),
            watermark_flagged=data.get("watermark_flagged"),
            steganography_suspected=data.get("steganography_suspected"),
            verdicts=data.get("verdicts") or {},
            assets=assets,
            raw=data,
        )
