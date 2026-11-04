"""Refresh-token -> access-token exchange for the two Google tokens.

Both refresh tokens were issued to the WEB OAuth client, so both are
refreshed with YT_WEB_CLIENT_ID / YT_WEB_CLIENT_SECRET.
"""
import os

import requests

TOKEN_URL = "https://oauth2.googleapis.com/token"


def refresh_access_token(refresh_token: str) -> str:
    resp = requests.post(
        TOKEN_URL,
        data={
            "client_id": os.environ["YT_WEB_CLIENT_ID"].strip(),
            "client_secret": os.environ["YT_WEB_CLIENT_SECRET"].strip(),
            "refresh_token": refresh_token.strip(),
            "grant_type": "refresh_token",
        },
        timeout=30,
    )
    if not resp.ok:
        # Google's error body carries only an error code and description
        # (never credential values), so it is safe to surface in the logs.
        raise RuntimeError(
            f"Token refresh failed: HTTP {resp.status_code}: {resp.text}"
        )
    return resp.json()["access_token"]


def youtube_access_token() -> str:
    """Token covering YouTube + Sheets scopes."""
    return refresh_access_token(os.environ["YT_REFRESH_TOKEN"])


def drive_access_token() -> str:
    """Token covering drive.file only."""
    return refresh_access_token(os.environ["DRIVE_REFRESH_TOKEN"])
