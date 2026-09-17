# Changelog

All notable changes to the `snapwonders` Python client are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.2] — 2026

- **Uploads now use a single request where they can.** The API gained a direct upload endpoint,
  and the client picks it for any file under the cap the server reports at session creation,
  falling back to the resumable TUS protocol above it. One round trip instead of three for the
  common case, which matters most on high-latency links. Nothing changes for callers:
  `client.analyse.run(["photo.jpg"])` is the same call.
- The cap is read from the session response (`max_upload_bytes`), so it can move server-side
  without a client release. The built-in figure is only a fallback.
- **New exception `UploadError`**, raised by the direct path. `TusUploadError` now inherits from
  it, so existing `except TusUploadError` code is unaffected — but catch `UploadError` if you want
  both paths.
- `session.upload()` returns the server's `storage_uid` for a direct upload and the TUS URL for a
  resumable one. Neither is needed for the normal flow (confirm with `session.files()`; jobs are
  keyed by `upload_uid`), but the value's meaning now depends on file size.
- `ResultFile.download()` takes only the final component of the server-supplied filename, so a
  response cannot choose where on your disk a file lands.

## [0.1.1] — 2026

- Documentation only: refreshed the README (published-to-PyPI status, illustrated demo).

## [0.1.0] — 2026

Initial release.

- Official Python client for the snapWONDERS API, covering all three product areas:
  `client.stego` (hide & reveal), `client.analyse` (forensic media analysis), and `client.convert`
  (media conversion).
- Resumable upload and the session → job → poll → download flow wrapped internally, so a whole job
  is a single call (e.g. `client.stego.hide([...], password=...)`). One-shot helpers plus
  step-by-step session/job control.
- Polling backs off with jitter and honours a server-supplied poll interval, to stay light under load.
- Typed exceptions (`SnapwondersError` base): `AuthError`, `ProRequiredError`, `SessionExpiredError`,
  `RateLimitError`, `MaintenanceError`, `JobFailedError`, `TusUploadError`, `NetworkError`, `ApiError`.
- Minimal dependency surface: `httpx` only.
