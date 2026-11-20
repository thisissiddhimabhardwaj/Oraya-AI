"""YouTube URL validation, video-ID parsing and public metadata retrieval."""
from __future__ import annotations

import re

import httpx

# 11-char ID per YouTube spec
VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")

_PATTERNS = [
    re.compile(r"(?:youtube\.com/watch\?(?:.*&)?v=)([A-Za-z0-9_-]{11})"),
    re.compile(r"(?:youtu\.be/)([A-Za-z0-9_-]{11})"),
    re.compile(r"(?:youtube\.com/embed/)([A-Za-z0-9_-]{11})"),
    re.compile(r"(?:youtube\.com/shorts/)([A-Za-z0-9_-]{11})"),
    re.compile(r"(?:youtube\.com/live/)([A-Za-z0-9_-]{11})"),
    re.compile(r"(?:youtube-nocookie\.com/embed/)([A-Za-z0-9_-]{11})"),
]


class InvalidURLError(ValueError):
    """Raised when a URL does not contain a valid YouTube video ID."""


def extract_video_id(url: str) -> str:
    url = url.strip()
    if VIDEO_ID_RE.match(url):  # bare ID pasted directly
        return url
    for pattern in _PATTERNS:
        m = pattern.search(url)
        if m:
            vid = m.group(1)
            if VIDEO_ID_RE.match(vid):
                return vid
    raise InvalidURLError(
        "That doesn't look like a YouTube link. Paste a full watch/shorts/youtu.be URL."
    )


def canonical_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


async def fetch_metadata(video_id: str) -> dict:
    """Public oEmbed metadata (no API key). Never raises — degrades gracefully."""
    meta = {
        "title": "",
        "channel": "",
        "thumbnail": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
        "duration": 0,
    }
    try:
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            resp = await client.get(
                "https://www.youtube.com/oembed",
                params={"url": canonical_url(video_id), "format": "json"},
            )
            if resp.status_code == 200:
                data = resp.json()
                meta["title"] = (data.get("title") or "")[:512]
                meta["channel"] = (data.get("author_name") or "")[:255]
                if data.get("thumbnail_url"):
                    meta["thumbnail"] = data["thumbnail_url"]
    except Exception:
        pass
    if not meta["title"]:
        meta["title"] = f"YouTube lecture {video_id}"
    return meta


async def probe_duration(video_id: str) -> int:
    """Best-effort duration from the watch page microformat. Returns 0 when unavailable."""
    try:
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            resp = await client.get(canonical_url(video_id))
            m = re.search(r'"lengthSeconds"\s*:\s*"(\d+)"', resp.text)
            if m:
                return int(m.group(1))
    except Exception:
        pass
    return 0
