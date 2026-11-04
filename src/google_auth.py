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
            "client_id": os.environ["YT_WEB_CLIENT_ID"],
            "client_secret": os.environ["YT_WEB_CLIENT_SECRET"],
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def youtube_access_token() -> str:
    """Token covering YouTube + Sheets scopes."""
    return refresh_access_token(os.environ["YT_REFRESH_TOKEN"])


def drive_access_token() -> str:
    """Token covering drive.file only."""
    return refresh_access_token(os.environ["DRIVE_REFRESH_TOKEN"])
