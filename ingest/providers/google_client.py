"""Google auth + read-only service builders for the ingest adapters (CHA-16).

Auth resolution (first that works wins):
  1. GOOGLE_TOKEN — a saved authorized-user token.json (auto-refreshed in place).
  2. GOOGLE_OAUTH_CLIENT — an OAuth *Desktop app* client_secret.json; on first
     use runs a one-time local consent flow and writes GOOGLE_TOKEN.

Raises LiveAuthUnavailable if neither is configured/usable so callers fall back
to the offline sample dump. Read-only scopes only — Gmail and Calendar are never
written to.

Why not gcloud ADC? `gmail.readonly` is a Google *restricted* scope; the shared
gcloud OAuth client can't grant it, so a dedicated Desktop client + local token
(isolated to this app) is the correct path and doesn't disturb global ADC.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Optional

from .errors import LiveAuthUnavailable

logger = logging.getLogger(__name__)

# Read-only. Adding a scope here requires re-consent (delete GOOGLE_TOKEN).
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
]


def google_configured() -> bool:
    """True if a usable credential file is actually present on disk.

    Checks existence (not just that the env var is set) so the default paths in
    .env don't trigger live attempts before you've dropped the real files in.
    """
    for var in ("GOOGLE_TOKEN", "GOOGLE_OAUTH_CLIENT"):
        path = os.getenv(var)
        if path and Path(path).expanduser().exists():
            return True
    return False


def _save_token(token_path: Optional[str], creds: Any) -> None:
    if not token_path:
        return
    p = Path(token_path).expanduser()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(creds.to_json())
    except OSError as exc:
        logger.warning("contxt:ingest_google_token_write_failed path=%s err=%s", p, exc)


def get_credentials() -> Any:
    """Return valid read-only Google credentials, or raise LiveAuthUnavailable."""
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
    except ImportError as exc:  # pragma: no cover - libs are in requirements
        raise LiveAuthUnavailable(f"google-auth not installed: {exc}") from exc

    token_path = os.getenv("GOOGLE_TOKEN")
    client_path = os.getenv("GOOGLE_OAUTH_CLIENT")
    creds = None

    if token_path and Path(token_path).expanduser().exists():
        creds = Credentials.from_authorized_user_file(
            str(Path(token_path).expanduser()), SCOPES
        )

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _save_token(token_path, creds)
            return creds
        except Exception as exc:  # noqa: BLE001 - refresh can fail many ways
            logger.warning("contxt:ingest_google_refresh_failed err=%s", exc)

    # No usable token — mint one via a one-time local consent flow.
    if client_path and Path(client_path).expanduser().exists():
        try:
            from google_auth_oauthlib.flow import InstalledAppFlow
        except ImportError as exc:  # pragma: no cover
            raise LiveAuthUnavailable(
                f"google-auth-oauthlib not installed: {exc}"
            ) from exc
        flow = InstalledAppFlow.from_client_secrets_file(
            str(Path(client_path).expanduser()), SCOPES
        )
        creds = flow.run_local_server(port=0)  # opens a browser once
        _save_token(token_path, creds)
        return creds

    raise LiveAuthUnavailable(
        "no usable Google credentials — set GOOGLE_TOKEN (saved token.json) or "
        "GOOGLE_OAUTH_CLIENT (Desktop client_secret.json) to enable live ingest"
    )


def build_service(api: str, version: str) -> Any:
    """Build a read-only Google API client (e.g. gmail/v1, calendar/v3)."""
    try:
        from googleapiclient.discovery import build
    except ImportError as exc:  # pragma: no cover
        raise LiveAuthUnavailable(f"google-api-python-client not installed: {exc}") from exc
    return build(api, version, credentials=get_credentials(), cache_discovery=False)
