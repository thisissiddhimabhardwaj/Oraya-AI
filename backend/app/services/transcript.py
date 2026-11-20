"""Transcript acquisition and parsing.

Sources, in order:
  1. uploaded file (.srt / .vtt / .txt) — parsed here
  2. live fetch via `youtube-transcript-api` when installed & reachable (optional)
  3. none — lecture is created with transcript_status="missing" and the UI offers upload

Timestamps are never invented: if an uploaded plain-text file has no time codes,
all segments are stored with start=end=0 and the API reports timed=False.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..config import settings


@dataclass
class ParsedSegment:
    start: float
    end: float
    text: str


class TranscriptError(Exception):
    pass


# ---------------------------------------------------------------- parsing
_TIME_HMS = re.compile(r"(\d{1,2}):(\d{2}):(\d{2})[.,](\d{3})")


def _strip_tags(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_srt(content: str) -> list[ParsedSegment]:
    segments: list[ParsedSegment] = []
    blocks = re.split(r"\n\s*\n", content.replace("\r\n", "\n").strip())
    for block in blocks:
        lines = [l for l in block.split("\n") if l.strip()]
        if not lines:
            continue
        tline = next((l for l in lines if "-->" in l), None)
        if not tline:
            continue
        start_s, end_s = [p.strip() for p in tline.split("-->")]
        text = " ".join(_strip_tags(l) for l in lines if "-->" not in l and not l.strip().isdigit())
        if not text:
            continue
        segments.append(
            ParsedSegment(_hms_to_sec(start_s), _hms_to_sec(end_s), text)
        )
    if not segments:
        raise TranscriptError("No cues found in this SubRip (.srt) file.")
    return segments


def parse_vtt(content: str) -> list[ParsedSegment]:
    content = content.replace("\r\n", "\n")
    content = re.sub(r"^WEBVTT.*?\n", "", content, flags=re.S)
    return parse_srt(content)


def _hms_to_sec(value: str) -> float:
    """Parse 'HH:MM:SS.mmm', 'MM:SS.mmm' or 'SS.mmm' (comma or dot decimal)."""
    value = value.strip().replace(",", ".")
    parts = value.split(":")
    try:
        if len(parts) == 3:
            h, m, s = parts
            return int(h) * 3600 + int(m) * 60 + float(s)
        if len(parts) == 2:
            m, s = parts
            return int(m) * 60 + float(s)
        return float(parts[0])
    except ValueError:
        return 0.0


def parse_plain_text(content: str) -> list[ParsedSegment]:
    """TXT: supports optional inline timestamps like '[03:12]', '03:12' at line start.

    Without any timestamps, segments are kept with start=end=0 (timed=False upstream).
    """
    segments: list[ParsedSegment] = []
    for raw in content.replace("\r\n", "\n").split("\n"):
        line = raw.strip()
        if not line:
            continue
        start = 0.0
        end = 0.0
        text = line
        m = re.match(r"^\[?(\d{1,2}:\d{2}(?::\d{2})?(?:[.,]\d{1,3})?)\]?\s*[-–—]?\s*(.*)$", line)
        if m:
            start = _hms_to_sec(m.group(1))
            text = m.group(2).strip()
            end = start
        if text:
            segments.append(ParsedSegment(start, end, _strip_tags(text)))
    if not segments:
        raise TranscriptError("The file appears to be empty.")
    return segments


def parse_transcript_file(filename: str, raw: bytes) -> list[ParsedSegment]:
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        content = raw.decode("latin-1", errors="replace")
    name = (filename or "").lower()
    if name.endswith(".srt"):
        return parse_srt(content)
    if name.endswith(".vtt"):
        return parse_vtt(content)
    if name.endswith(".txt"):
        return parse_plain_text(content)
    # Sniff instead of trusting the extension
    if "WEBVTT" in content[:64] or "-->" in content[:2048]:
        return parse_vtt(content) if "WEBVTT" in content[:64] else parse_srt(content)
    if re.search(r"\d{2}:\d{2}:\d{2}[,.]\d{3}\s*-->", content):
        return parse_srt(content)
    return parse_plain_text(content)


# ---------------------------------------------------------------- fetch (optional)
def fetch_from_youtube(video_id: str) -> list[ParsedSegment] | None:
    """Try the optional youtube-transcript-api dependency. Returns None when unavailable."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi  # type: ignore
    except Exception:
        return None
    try:
        api = YouTubeTranscriptApi()
        fetched = api.fetch(video_id)
        out = [
            ParsedSegment(float(s.start), float(s.start) + float(s.duration), " ".join(s.text.split()))
            for s in fetched
            if getattr(s, "text", "").strip()
        ]
        return out or None
    except Exception:
        return None


# ---------------------------------------------------------------- chaptering / topics
_STOPWORDS = set(
    """a an the and or but if then else of in on at to for from by with without as is are was were be
    been being it its this that these those we you they he she i not no so than too very can will just
    don't dont about into over under again more most some such only own same don what which who whom
    when where why how all any both each few other few s t don ll ve re m o don d ll ve re don""".split()
)


def _tokens(text: str) -> list[str]:
    return [
        w for w in re.findall(r"[a-zA-Z][a-zA-Z\-']{1,}", text.lower()) if w not in _STOPWORDS and len(w) > 2
    ]


def keyphrases(segments: list[ParsedSegment], limit: int = 12) -> list[tuple[str, int]]:
    """Frequency-based keyphrase extraction (unigrams + bigrams) — derived, not invented."""
    counts: dict[str, int] = {}
    bigrams: dict[str, int] = {}
    for seg in segments:
        toks = _tokens(seg.text)
        for t in toks:
            counts[t] = counts.get(t, 0) + 1
        for a, b in zip(toks, toks[1:]):
            bg = f"{a} {b}"
            bigrams[bg] = bigrams.get(bg, 0) + 1
    scored: list[tuple[str, int]] = []
    for bg, c in bigrams.items():
        if c >= 2:
            scored.append((bg, c * 2))
    for w, c in counts.items():
        if c >= 2:
            scored.append((w, c))
    scored.sort(key=lambda x: (-x[1], x[0]))
    picked: list[tuple[str, int]] = []
    for phrase, c in scored:
        words = phrase.split()
        if any(phrase in p[0] or p[0] in phrase for p in picked):
            continue
        picked.append((phrase.title(), c))
        if len(picked) >= limit:
            break
    return picked


def build_chapters(segments: list[ParsedSegment], target: int = 6) -> list[tuple[str, float]]:
    """Time-bounded chapter spans, each titled by its own dominant keyphrase."""
    if not segments:
        return []
    n = len(segments)
    spans = max(1, min(target, n))
    size = max(1, n // spans)
    chapters: list[tuple[str, float]] = []
    for i in range(0, n, size):
        chunk = segments[i : i + size]
        if not chunk:
            continue
        top = keyphrases(chunk, limit=1)
        title = top[0][0] if top else f"Part {len(chapters) + 1}"
        # Avoid identical consecutive titles
        if chapters and chapters[-1][0] == title:
            title = f"{title} (cont.)"
        chapters.append((title, chunk[0].start))
    return chapters


def format_ts(seconds: float) -> str:
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
