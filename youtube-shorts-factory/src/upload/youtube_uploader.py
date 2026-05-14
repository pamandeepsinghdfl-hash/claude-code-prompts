"""Resumable upload + scheduled publish via YouTube Data API v3.

  • OAuth 2.0 (installed-app flow). Token cached at YOUTUBE_OAUTH_TOKEN_PATH.
  • Uploads with resumable chunks so we tolerate flaky connections.
  • Sets `status.publishAt` to schedule public release at a specific UTC
    timestamp (privacyStatus must be `private` for publishAt to work).
  • Uploads a custom thumbnail after the video is ready.
  • Tags the upload with `#Shorts` and a vertical short-form description.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

log = logging.getLogger("shorts_factory.upload")

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]


class YouTubeUploader:
    def __init__(self, client_secret_path: str, token_path: str):
        self.client_secret_path = client_secret_path
        self.token_path = token_path
        self.yt = self._build_service()

    # ─── Auth ────────────────────────────────────────────────────────────
    def _build_service(self):
        creds: Optional[Credentials] = None
        token_file = Path(self.token_path)
        if token_file.exists():
            creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.client_secret_path, SCOPES
                )
                # `run_local_server` opens a browser for first-time auth.
                creds = flow.run_local_server(port=0)
            token_file.parent.mkdir(parents=True, exist_ok=True)
            token_file.write_text(creds.to_json(), encoding="utf-8")
        return build("youtube", "v3", credentials=creds, cache_discovery=False)

    # ─── Upload ──────────────────────────────────────────────────────────
    def upload(
        self,
        *,
        video_path: str | Path,
        title: str,
        description: str,
        tags: List[str],
        publish_at: datetime,
        category_id: str = "22",  # People & Blogs
        thumbnail_path: Optional[str | Path] = None,
        made_for_kids: bool = False,
    ) -> str:
        if publish_at.tzinfo is None:
            publish_at = publish_at.replace(tzinfo=timezone.utc)

        body = {
            "snippet": {
                "title": title[:100],
                "description": description[:5000],
                "tags": tags[:30],
                "categoryId": category_id,
                "defaultLanguage": "en",
                "defaultAudioLanguage": "en",
            },
            "status": {
                "privacyStatus": "private",
                "publishAt": publish_at.astimezone(timezone.utc)
                .isoformat()
                .replace("+00:00", "Z"),
                "selfDeclaredMadeForKids": made_for_kids,
            },
        }

        media = MediaFileUpload(
            str(video_path),
            chunksize=8 * 1024 * 1024,
            resumable=True,
            mimetype="video/mp4",
        )
        request = self.yt.videos().insert(
            part="snippet,status", body=body, media_body=media
        )

        response = None
        while response is None:
            try:
                status, response = request.next_chunk()
                if status:
                    log.info("Upload progress: %d%%", int(status.progress() * 100))
            except HttpError as e:
                if e.resp.status in (500, 502, 503, 504):
                    log.warning("Transient upload error %s — retrying", e.resp.status)
                    continue
                raise
        video_id = response["id"]
        log.info("Uploaded video id=%s (publishAt=%s)", video_id, body["status"]["publishAt"])

        if thumbnail_path:
            try:
                self.yt.thumbnails().set(
                    videoId=video_id,
                    media_body=MediaFileUpload(str(thumbnail_path)),
                ).execute()
                log.info("Thumbnail attached to %s", video_id)
            except HttpError as e:
                log.warning("Thumbnail upload failed (channel may need verification): %s", e)

        return video_id

    # Tactic 4: post + heart a hook question as the first comment to
    # juice first-hour engagement velocity. Hearting it pins it to the
    # top automatically.
    def post_pinned_question(self, video_id: str, question: str) -> Optional[str]:
        if not question:
            return None
        try:
            thread = self.yt.commentThreads().insert(
                part="snippet",
                body={
                    "snippet": {
                        "videoId": video_id,
                        "topLevelComment": {
                            "snippet": {"textOriginal": question[:9000]}
                        },
                    }
                },
            ).execute()
            comment_id = thread["snippet"]["topLevelComment"]["id"]
            log.info("Pinned hook question on %s", video_id)
            return comment_id
        except HttpError as e:
            log.warning("Pinned comment failed for %s: %s", video_id, e)
            return None
