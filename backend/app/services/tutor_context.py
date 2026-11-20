"""Choose transcript evidence for subject overviews and conversational follow-ups."""
from __future__ import annotations

import re

from .rag import tokenize


def overview_question(question: str, title: str) -> bool:
    words = set(tokenize(question))
    generic = {"summary", "summarize", "summarise", "overview", "lecture", "video", "clip",
               "main", "key", "ideas", "points", "bullet", "bullets", "five", "5", "short", "brief"}
    if re.search(r"\b(summary|summari[sz]e|overview)\b", question, re.I) and not words - generic:
        return True
    if re.search(r"\bwhat (?:is (?:this|the) (?:video|lecture|clip) about|should I revise)\b", question, re.I):
        return True
    # A title-topic overview is not a search for the instructional words around it.
    return bool(words and words <= set(tokenize(title)) and re.search(r"\b(explain|what|why|describe)\b", question, re.I))


def retrieval_question(question: str, history: list[dict[str, str]]) -> str:
    pattern = r"\b(it|that|this|they|them|those|more|simpler|again|example)\b|^why\??$"
    follow_up = re.search(pattern, question, re.I)
    if not follow_up:
        return question
    users = [m["content"] for m in history if m.get("role") == "user"]
    previous = next((text for text in reversed(users) if not re.search(pattern, text, re.I)),
                    users[-1] if users else "")
    # Keep the preceding question's topic available for 'why?' and 'an example'.
    return f"{previous}\n{question}" if previous else question


def cited_times(answer: str) -> set[str]:
    # Models can cite one timestamp, a comma-separated group, or a range.
    groups = re.findall(r"\[([\d:,;\s–-]+)\]|\*\*(\d+(?::\d{2}){1,2})\*\*", answer)
    times = set()
    for group in groups:
        for part in group:
            for ts in re.findall(r"\d+(?::\d{2}){1,2}", part):
                pieces = [int(value) for value in ts.split(":")]
                if any(value >= 60 for value in pieces[1:]):
                    times.add(ts)  # Remain invalid rather than normalizing malformed timestamps.
                    continue
                seconds = 0
                for value in pieces:
                    seconds = seconds * 60 + value
                hours, remaining = divmod(seconds, 3600)
                minutes, seconds = divmod(remaining, 60)
                times.add(f"{hours}:{minutes:02}:{seconds:02}" if hours else f"{minutes}:{seconds:02}")
    return times


def is_refusal(answer: str) -> bool:
    return bool(re.search(
        r"(?:transcript|lecture|video|clip|excerpts?).{0,45}(?:does(?:n't| not)|do(?:n't| not)|not cover|not explain|not provide)"
        r"|(?:not covered|not explained|not enough (?:information|context)|couldn't find|cannot find)",
        answer, re.I,
    ))
