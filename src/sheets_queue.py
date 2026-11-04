"""Read and update the production queue in Google Sheets.

Sheet: spreadsheet id from QUEUE_SHEET_ID, tab "queue".
Columns A..I: id | topic | method | language | status | title | video_url | created_at | notes
"""
import os

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from google_auth import youtube_access_token

TAB = "queue"


def _service():
    creds = Credentials(token=youtube_access_token())
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def read_rows() -> list[dict]:
    svc = _service()
    result = (
        svc.spreadsheets()
        .values()
        .get(spreadsheetId=os.environ["QUEUE_SHEET_ID"], range=f"{TAB}!A1:I200")
        .execute()
    )
    values = result.get("values", [])
    if not values:
        return []
    headers = values[0]
    rows = []
    for i, raw in enumerate(values[1:], start=2):  # sheet row numbers are 1-based
        row = {h: (raw[j] if j < len(raw) else "") for j, h in enumerate(headers)}
        row["_row"] = i
        rows.append(row)
    return rows


def next_queued() -> dict | None:
    for row in read_rows():
        if (row.get("status") or "").strip().lower() == "queued":
            return row
    return None


def update_row(row_number: int, **fields: str) -> None:
    """fields keys must be column headers, e.g. status=..., title=..., video_url=..."""
    headers = ["id", "topic", "method", "language", "status", "title", "video_url", "created_at", "notes"]
    svc = _service()
    for key, value in fields.items():
        col = headers.index(key)
        letter = chr(ord("A") + col)
        svc.spreadsheets().values().update(
            spreadsheetId=os.environ["QUEUE_SHEET_ID"],
            range=f"{TAB}!{letter}{row_number}",
            valueInputOption="RAW",
            body={"values": [[value]]},
        ).execute()
