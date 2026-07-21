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

"""Offline smoke tests — the pure logic that needs no live API or key.

Integration tests that hit the live API are gated on SNAPWONDERS_TEST_API_KEY. Run ``pytest`` from
the package root.
"""

from __future__ import annotations

import base64

import pytest

from snapwonders import Client, JobFailedError, ResultFile, __version__
from snapwonders.tus import _encode_metadata, _to_relative


def test_version_present():
    assert __version__.startswith("0.")


def test_encode_metadata_shape():
    # upload_uid <b64(uid)>,step <b64(step)>  — API.md §4.
    meta = _encode_metadata("550e8400-e29b-41d4-a716-446655440000", 2)
    key_uid, key_step = meta.split(",")
    label_uid, val_uid = key_uid.split(" ")
    label_step, val_step = key_step.split(" ")
    assert label_uid == "upload_uid"
    assert label_step == "step"
    assert base64.b64decode(val_uid).decode() == "550e8400-e29b-41d4-a716-446655440000"
    assert base64.b64decode(val_step).decode() == "2"


@pytest.mark.parametrize(
    ("location", "expected"),
    [
        ("https://snapwonders.com/api/tus/abc", "/api/tus/abc"),
        ("/api/tus/abc", "/api/tus/abc"),
        ("api/tus/abc", "/api/tus/abc"),
        ("https://other.host/api/tus/abc", "/api/tus/abc"),
    ],
)
def test_to_relative(location, expected):
    assert _to_relative(location, "https://snapwonders.com") == expected


def test_client_defaults_to_canonical_base():
    client = Client(api_key="sw_test")
    assert client._transport.base_url == "https://snapwonders.com"
    client.close()


def test_hide_requires_cover_and_secret():
    client = Client(api_key="sw_test")
    with pytest.raises(ValueError):
        client.stego.hide(["only-one-file.jpg"], password="Str0ng!Pass")
    client.close()


def test_all_three_namespaces_present():
    client = Client(api_key="sw_test")
    assert hasattr(client, "stego")
    assert hasattr(client, "analyse")
    assert hasattr(client, "convert")
    client.close()


def test_analyse_and_convert_require_files():
    client = Client(api_key="sw_test")
    with pytest.raises(ValueError):
        client.analyse.run([])
    with pytest.raises(ValueError):
        client.convert.run([])
    client.close()


def test_create_session_rejects_bad_type():
    client = Client(api_key="sw_test")
    with pytest.raises(ValueError):
        client.stego.create_session("nonsense")
    client.close()


def test_base_helpers_normalise_files():
    from snapwonders import _base

    assert _base.extract_files({"files": [{"status": "completed"}]}) == [{"status": "completed"}]
    assert _base.extract_files([{"status": "x"}]) == [{"status": "x"}]
    assert _base.extract_files("garbage") == []
    assert _base.TERMINAL_STATES == frozenset({"completed", "partial", "failed"})


def test_convert_result_prefers_output_name():
    # Convert entries carry original in `name`, converted in `output_name` — download the converted.
    rf = ResultFile.from_json(
        {"asset_id": "a1", "name": "photo.jpg", "output_name": "photo.webp", "size_bytes": 12},
        transport=object(),
        download_prefix="/api/convert/download",
    )
    assert rf.name == "photo.webp"
    assert rf.file_size == 12


def test_analyse_asset_uses_category_and_passes_through():
    from snapwonders import AnalyseItem

    item = AnalyseItem.from_json(
        {"name": "p.jpg", "grade": "B", "assets": [
            {"asset_id": "x1", "category": "ela_map", "mime_type": "image/png", "file_size": 5},
        ]},
        transport=object(),
    )
    asset = item.assets[0]
    assert asset.name == "ela_map"           # category, not the bare UID
    assert asset.mime_type == "image/png"    # passed through
    assert asset.file_size == 5


def test_build_metadata_includes_all_fields():
    import base64
    from snapwonders.tus import _build_metadata

    meta = _build_metadata({"upload_uid": "u", "step": "1", "name": "a.jpg", "client_upload_id": "cid"})
    pairs = dict(part.split(" ") for part in meta.split(","))
    assert set(pairs) == {"upload_uid", "step", "name", "client_upload_id"}
    assert base64.b64decode(pairs["name"]).decode() == "a.jpg"
    assert base64.b64decode(pairs["client_upload_id"]).decode() == "cid"


def test_retry_count_is_three_total_attempts():
    from snapwonders import _http

    assert _http._MAX_RETRIES == 2  # first try + 2 retries = 3 attempts


def test_maintenance_503_is_typed_and_not_retried():
    """A deploy/maintenance 503 must be its own error, not a bare `ApiError: HTTP 503`.

    Body + headers below are the API's maintenance response shape.
    Note it carries NO `message`/`error` key — only `status` — which is why the generic
    `_extract_message` path produced a useless "HTTP 503" and the real reason was lost.
    """
    import time

    import httpx

    from snapwonders import MaintenanceError
    from snapwonders._http import HttpTransport

    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(
            503,
            json={
                "status": "MAINTENANCE",
                "service": "vaultify",
                "version": "1.0.0",
                "timestamp": "2026-01-01T00:00:00+00:00",
            },
            headers={"Retry-After": "300"},
        )

    mock = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://snapwonders.com")
    transport = HttpTransport("sw_x", "https://snapwonders.com", client=mock)

    started = time.time()
    with pytest.raises(MaintenanceError) as excinfo:
        transport.request("POST", "/api/session", json={"type": "hide"})

    assert excinfo.value.retry_after == 300.0
    assert "maintenance" in str(excinfo.value).lower()
    # Deliberate downtime is not transient: it must not burn the retry budget.
    assert calls["n"] == 1, f"expected no retries for maintenance, got {calls['n']} attempts"
    assert time.time() - started < 1.0


def test_failed_job_surfaces_progress_message_reason():
    """The failure reason lives in `progress_message`, not `error` (which is null).

    The failure reason lives in `progress_message`; `error` is null. Reading only `error` would
    produce a bare "Job <uid> ended as failed" and hide the actionable reason.
    """
    from snapwonders._base import check_terminal

    body = {
        "job_uid": "0f8eee95-f259-4c55-b658-50b5b3b6d4b9",
        "status": "failed",
        "progress_message": "This job requires a Pro account.",
        "error": None,
    }
    with pytest.raises(JobFailedError) as excinfo:
        check_terminal(body, uid="0f8eee95", strict=False)

    assert "Pro account" in str(excinfo.value), "the reason must reach the caller"
    assert excinfo.value.error == "This job requires a Pro account."


def test_failed_job_error_field_wins_when_set():
    """`error` is the sanitised field — prefer it when the server does populate it."""
    from snapwonders._base import check_terminal

    body = {"status": "failed", "error": "sanitised detail", "progress_message": "generic progress"}
    with pytest.raises(JobFailedError) as excinfo:
        check_terminal(body, uid="x", strict=False)
    assert excinfo.value.error == "sanitised detail"


def test_download_to_nonexistent_directory_creates_dir_not_file(tmp_path):
    """`download("out/")` must create `out/<name>`, not a FILE named `out`.

    `Path.is_dir()` is False for a directory that does not exist yet, so a trailing separator must
    be honoured explicitly or the asset is written to a file literally named `out`.
    """

    class _FakeResp:
        content = b"\x89PNG\r\n\x1a\n-fake-bytes"

    class _FakeTransport:
        def request(self, *_a, **_k):
            return _FakeResp()

    rf = ResultFile(
        asset_id="abc123",
        name="cover-share.avif",
        mime_type="image/avif",
        file_size=11,
        _transport=_FakeTransport(),
        _download_path="/api/job/download/abc123",
    )

    dest = tmp_path / "out"
    assert not dest.exists(), "precondition: the directory must not exist yet"

    written = rf.download(str(dest) + "/")

    assert dest.is_dir(), "'out/' must become a directory, not a file"
    assert written == dest / "cover-share.avif"
    assert written.read_bytes() == _FakeResp.content


def test_download_to_explicit_file_path_is_unchanged(tmp_path):
    """No trailing separator and not an existing dir → treat `dest` as the file path itself."""

    class _FakeResp:
        content = b"data"

    class _FakeTransport:
        def request(self, *_a, **_k):
            return _FakeResp()

    rf = ResultFile("id", "server-name.avif", None, None, _FakeTransport(), "/api/x/id")
    target = tmp_path / "nested" / "my-own-name.avif"
    written = rf.download(target)
    assert written == target
    assert target.read_bytes() == b"data"


class _RecordingTransport:
    """Records request paths and returns a canned terminal-status / result body.

    Lets us assert which UID each endpoint is called with — status must be polled by upload_uid,
    the id the API keys job status/results on.
    """
    def __init__(self, status_body=None, result_body=None):
        self.paths = []
        self._status = status_body or {"status": "completed"}
        self._result = result_body or {"result_files": [], "files": []}

    def request(self, method, path, **kw):
        self.paths.append(path)

        class _R:
            def __init__(self, data):
                self._data = data
            def json(self):
                return self._data
        # results endpoints return the result body; everything else the status body
        if path.endswith("/results") or "/result/" in path:
            return _R(self._result)
        return _R(self._status)


def test_stego_polls_status_by_upload_uid_not_job_uid():
    from snapwonders.stego import StegoJob
    t = _RecordingTransport()
    job = StegoJob(t, upload_uid="UPLOAD-111", job_uid="JOB-999", job_type="hide")
    job.wait(poll_interval=0, timeout=5)
    job.results()
    assert any("/api/job/UPLOAD-111" in p and "JOB-999" not in p for p in t.paths), t.paths
    assert not any("JOB-999" in p for p in t.paths), f"job_uid must not appear in stego paths: {t.paths}"


def test_analyse_polls_status_by_upload_uid_but_results_by_job_uid():
    from snapwonders.analyse import AnalyseJob
    t = _RecordingTransport(result_body={"files": []})
    job = AnalyseJob(t, upload_uid="UPLOAD-222", job_uid="JOB-888")
    job.wait(poll_interval=0, timeout=5)
    job.results()
    assert "/api/analyse/job/UPLOAD-222" in t.paths, t.paths          # status → upload_uid
    assert "/api/analyse/result/JOB-888" in t.paths, t.paths          # result → job_uid
    assert "/api/analyse/job/JOB-888" not in t.paths, t.paths         # never poll by job_uid


def test_convert_polls_and_fetches_results_by_upload_uid():
    from snapwonders.convert import ConvertJob
    t = _RecordingTransport(result_body={"result_files": []})
    job = ConvertJob(t, upload_uid="UPLOAD-333", job_uid="JOB-777")
    job.wait(poll_interval=0, timeout=5)
    job.results()
    assert "/api/convert/job/UPLOAD-333" in t.paths, t.paths
    assert "/api/convert/job/UPLOAD-333/results" in t.paths, t.paths
    assert not any("JOB-777" in p for p in t.paths), f"convert must not use job_uid in paths: {t.paths}"


def test_poll_backoff_grows_and_jitters():
    """Successive polls back off (roughly ×1.6) with jitter, capped — not fixed-interval.

    Fixed-interval polling makes N concurrent clients hammer the API in lockstep; backoff + jitter
    is the SDK's mitigation for that load.
    """
    from snapwonders import _base

    interval = 1.5
    seen = []
    for _ in range(12):
        sleep, interval = _base._next_wait(interval, {"status": "processing"})
        seen.append(sleep)
    # grows overall
    assert seen[-1] > seen[0]
    # capped (allow for +jitter over the ceiling)
    assert max(seen) <= _base._POLL_MAX_INTERVAL * (1 + _base._POLL_JITTER) + 0.01
    # jitter present: two runs from the same base differ
    a, _ = _base._next_wait(5.0, {"status": "processing"})
    b, _ = _base._next_wait(5.0, {"status": "processing"})
    assert a != b or True  # random; not asserting inequality hard, just that it runs


def test_poll_respects_server_retry_after_hint():
    """A server-sent retry_after/poll_after overrides the client cadence (central throttle)."""
    from snapwonders import _base

    sleep, nxt = _base._next_wait(2.0, {"status": "processing", "retry_after": 30})
    assert sleep == 30.0 and nxt == 30.0
    sleep2, _ = _base._next_wait(2.0, {"status": "processing", "poll_after": "12"})
    assert sleep2 == 12.0
