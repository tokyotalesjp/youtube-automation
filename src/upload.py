"""YouTube upload (resumable) + caption upload via the Data API."""
import os

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from google_auth import youtube_access_token


def _service():
    creds = Credentials(token=youtube_access_token())
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def upload_video(video_path: str, title: str, description: str,
                 privacy: str = "unlisted", language: str = "en") -> str:
    svc = _service()
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "categoryId": "27",  # Education — explainers; revisit per topic later
            "defaultLanguage": language,
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }
    media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True,
                            chunksize=8 * 1024 * 1024)
    request = svc.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        _, response = request.next_chunk()
    return response["id"]


def upload_captions(video_id: str, srt_path: str, language: str = "en") -> None:
    svc = _service()
    body = {"snippet": {"videoId": video_id, "language": language, "name": "", "isDraft": False}}
    media = MediaFileUpload(srt_path, mimetype="application/octet-stream", resumable=False)
    svc.captions().insert(part="snippet", body=body, media_body=media).execute()
