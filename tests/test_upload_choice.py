"""Which upload method gets used, and why it must stay that way.

The SDK hides the fact that the API has two upload methods. These tests pin the choice, and —
more importantly — pin the one implementation detail that looks like dead weight and is not:
direct upload must send a bytes body, never a stream.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from snapwonders import direct, upload_router  # noqa: E402


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload
        self.headers: dict[str, str] = {}

    def json(self) -> dict:
        return self._payload


class _RecordingTransport:
    """Captures what the SDK would have put on the wire."""

    base_url = "https://snapwonders.com"

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self._offset = 0  # TUS server-side offset, advanced by each PATCH

    def request(self, method, path, *, headers=None, content=None, expected=None, **kwargs):
        self.calls.append({
            "method": method,
            "path": path,
            "headers": headers or {},
            "content": content,
            "kwargs": kwargs,
        })

        if path == "/api/upload":
            return _FakeResponse({"file": {"storage_uid": "uid-from-direct"}})

        resp = _FakeResponse({})
        if method == "PATCH":
            # Acknowledge the bytes, so the SDK's completeness check can pass. Without this the
            # upload loop stalls at offset 0 and reports "Upload incomplete".
            self._offset += len(content or b"")
        resp.headers = {
            "Location": "https://snapwonders.com/api/tus/abc123",
            "Upload-Offset": str(self._offset),
        }
        return resp


def _write(tmp_path: Path, size: int) -> Path:
    p = tmp_path / "sample.bin"
    p.write_bytes(b"x" * size)
    return p


def test_small_file_uses_direct_upload(tmp_path):
    t = _RecordingTransport()
    result = upload_router.upload_file(t, _write(tmp_path, 1024), upload_uid="u1", step=1, max_upload_bytes=4096)

    assert result == "uid-from-direct"
    assert [c["path"] for c in t.calls] == ["/api/upload"], "one request, not the TUS dance"


def test_file_over_the_cap_falls_back_to_tus(tmp_path):
    t = _RecordingTransport()
    upload_router.upload_file(t, _write(tmp_path, 8192), upload_uid="u1", step=1, max_upload_bytes=4096)

    assert t.calls[0]["path"] == "/api/tus", "over the cap the resumable protocol must be used"
    assert any(c["method"] == "PATCH" for c in t.calls), "TUS must actually transfer the bytes"


def test_a_file_exactly_on_the_cap_still_goes_direct(tmp_path):
    """The limit is inclusive server-side; an off-by-one here would push files to TUS needlessly."""
    t = _RecordingTransport()
    upload_router.upload_file(t, _write(tmp_path, 4096), upload_uid="u1", step=1, max_upload_bytes=4096)

    assert [c["path"] for c in t.calls] == ["/api/upload"]


def test_server_reported_cap_overrides_the_built_in_default(tmp_path):
    """The point of reading max_upload_bytes: the cap can move without an SDK release."""
    t = _RecordingTransport()
    # Comfortably under the SDK's own default, but over what this server says it accepts.
    upload_router.upload_file(t, _write(tmp_path, 2048), upload_uid="u1", step=1, max_upload_bytes=512)

    assert t.calls[0]["path"] == "/api/tus"


def test_direct_upload_sends_bytes_not_a_stream(tmp_path):
    """The one that stops a future 'optimisation' from silently breaking every upload.

    httpx sets Content-Length for a bytes body but switches to Transfer-Encoding: chunked for a
    file-like one — and the server refuses chunked with 411, because a body with no declared
    length cannot be distinguished from one truncated in transit. Passing a file handle here
    reads as an obvious memory win and breaks uploading entirely.
    """
    t = _RecordingTransport()
    direct.upload_file(t, _write(tmp_path, 64), upload_uid="u1", step=1)

    body = t.calls[0]["content"]
    assert isinstance(body, bytes), (
        "direct upload must pass bytes so Content-Length is set; a stream makes httpx use "
        "chunked encoding, which the server rejects with 411"
    )
    assert len(body) == 64


def test_direct_upload_sends_the_headers_the_server_requires(tmp_path):
    t = _RecordingTransport()
    direct.upload_file(t, _write(tmp_path, 16), upload_uid="sess-1", step=2, content_type="image/jpeg")

    headers = t.calls[0]["headers"]
    assert headers["X-Upload-Uid"] == "sess-1"
    assert headers["X-Upload-Step"] == "2"
    assert headers["Content-Type"] == "image/jpeg"
    assert headers["X-Filename"] == "sample.bin"
    # Without this a retry after a lost response stores the file twice.
    assert headers.get("X-Client-Upload-Id")
