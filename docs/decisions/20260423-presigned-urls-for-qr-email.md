# Decision: Use S3 Presigned URLs for QR Code and Email Downloads

**Date:** 2026-04-23  
**Status:** Accepted  
**Context:** QR codes on the route-download page and download links in completion emails encode intranet-only Flask URLs (`WEB_OUTSIDE_URL`), making them inaccessible to field surveyors on mobile data or guest networks.

## Decision

Use S3-compatible presigned URLs (signed by MinIO/Quantum ActiveScale credentials) instead of Flask routes for:

1. **QR code URLs** – encode a presigned GET URL pointing directly to `vip.s3.ufz.de/<bucket>/<job_id>/route.gpx`
2. **Email download links** – same approach with a longer TTL (7 days vs. 24 hours for QR)

Keep the **in-app download button** on the Flask route (`/download/<job_id>/route.gpx`) unchanged.

## Rationale

**Why presigned URLs over exposing `/download/` publicly:**

- Presigned URLs are cryptographically signed and time-limited — they don't require public ACLs or bucket policy changes.
- The in-app button already works via Flask with proper `Content-Disposition` headers. Routing it through S3 buys nothing.
- Public `/download/` routes bypass S3 credentials and require defending against enumeration attacks on job IDs.

**Why regenerate the QR on every page load:**

- Presigned URLs have TTLs (24 hours for QR). Regenerating on every page load ensures the embedded URL is never stale.
- Cheap operation — single minio SDK call. No performance cost.

**Why the `minio` SDK over rclone:**

- `rclone` is for bulk sync; `minio` is for signing individual objects.
- `minio` is thin, proven in production against Quantum ActiveScale, and has no functional overlap with rclone.
- AWS SDK would add bloat; `minio` is S3-compatible and keeps dependencies lean.

## Implementation

### Files Modified

- **`pyproject.toml`** – Added `minio>=7.2.0,<8`
- **`cosmonaut_app/object_storage_manager.py`** – Added `get_presigned_download_url()` helper
- **`cosmonaut_app/navigation_routing.py`** – QR code now embeds a presigned URL; QR is regenerated on every `create_gpx()` call
- **`cosmonaut_app/tasks/routing_tasks.py`** – Completion email now uses a presigned URL (7-day TTL)
- **`cosmonaut_app/pages/route_download.py`** – Calls `create_qr_code_routing()` on every page load to refresh the presigned URL

### Test Coverage

- **E2E test** (`test_complete_routing_workflow.py`) passes: QR code and email generation complete successfully.
- **Dev/test environments:** Presigned URLs include `localhost` and won't work from a phone — same UX as before, not a regression.

## Decision Considered

- **Email links:** Included presigned URLs in the completion email (same scope creep risk as QR, same benefit).
- **Renaming `get_download_url()`:** Left in place. Still used by `config.py` callers outside the QR/email paths.

## Known Limitations

- Presigned URLs only work from public/semi-public endpoints (UFZ public IP range, S3 internet).
- If someone is on UFZ intranet but the S3 presigned URL expires, re-scan the QR or re-open the email.
- Dev/test with local MinIO: presigned URLs point to `localhost` and can't be accessed from a phone (expected).

## Follow-ups & Security Notes

**Presigned URLs are bearer tokens.** The implementation includes log hygiene to prevent leaking them:
- QR code URL not logged (job ID sufficient for correlation)
- Email body not logged (subject + recipient + length sufficient for debugging)
- Object keys logged only (not the signed URLs themselves)

**Credential scoping.** Current implementation signs all requests with the same S3 credentials (`OBJECT_STORAGE_ACCESS_KEY`/`OBJECT_STORAGE_SECRET_KEY`). Future work should scope these to least-privilege (e.g., read-only, object-level, time-limited). This is tracked separately.

## Verification

- Ran `./run_pytest.sh test/test_complete_routing_workflow.py` — passed.
- No regressions in other tests.
