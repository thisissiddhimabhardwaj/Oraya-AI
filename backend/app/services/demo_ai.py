"""Deterministic, extractive demo engine.

Everything produced here is derived from the lecture's actual transcript segments —
nothing is invented (development rule #16). When GEMINI_API_KEY is configured these
functions are only used as fallbacks if a live call fails.
"""
from __future__ import annotations

import re
from collections import Counter

from .transcript import ParsedSegment, format_ts, keyphrases

Seg = tuple[int, float, float, str]  # (segment_id, start, end, text)

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")

_STOP = set(
    """a an the and or but if of in on at to for from by with as is are was were be been being it its this
    that these those we you they he she not no so than too very can will just about into over under more most
    such only own same what which who whom when where why how all any both each few other then also after
    before during while do does did done have has having i my your our their""".split()
)


def _content_tokens(text: str) -> set[str]:
    """Lowercased content words (stopwords removed) — used for overlap matching."""
    return {
        w
        for w in re.findall(r"[a-z][a-z\-']{2,}", text.lower())
        if w not in _STOP
    }


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT_SPLIT.split(text) if len(s.strip()) > 20]


def _md_escape(text: str) -> str:
    return text.replace("*", "").replace("|", "\\|").strip()


def _context_lines(segments: list[Seg], query_tokens: set[str], limit: int = 3) -> list[str]:
    """Sentences with the highest content-word overlap with the query, in time order."""
    min_overlap = 1 if len(query_tokens) < 3 else 2
    scored: list[tuple[float, int, str, float]] = []
    for i, (_, start, _, text) in enumerate(segments):
        for sent in _sentences(text):
            toks = _content_tokens(sent)
            if not toks:
                continue
            overlap = len(query_tokens & toks)
            if overlap >= min_overlap:
                scored.append((overlap / (len(toks) ** 0.5), i, sent, start))
    scored.sort(key=lambda x: -x[0])
    picked = sorted(scored[: limit * 2], key=lambda x: x[1])[:limit]
    return [f"**{format_ts(start)}** — {_md_escape(sent)}" for _, _, sent, start in picked]


# ---------------------------------------------------------------- tutor
def answer_question(
    question: str,
    segments: list[Seg],
    retrieved_quotes: list[tuple[float, str, float]],
) -> tuple[str, list[dict]]:
    """retrieved_quotes: (score, quote, start) already ranked best-first."""
    from .rag import tokenize
    q_tokens = set(tokenize(question))
    refs: list[dict] = []

    lines: list[str] = []
    usable = [(s, q, st) for s, q, st in retrieved_quotes
              if s > 0 and q.strip() and q_tokens & set(tokenize(q))][:3]

    if not usable:
        context = _context_lines(segments, q_tokens, limit=3)
        if not context:
            return (
                "I couldn't find an answer to that in this video's available transcript. "
                "The transcript is loaded, but it may not explain this topic. "
                "You can ask for an overview of the video or about a specific passage.",
                [],
            )
        lines.append("I could only partially match that, so here's the closest material:")
        lines.extend(context)
    else:
        lines.append("Here's what the lecture actually says about this:")
        for _, quote, start in usable:
            lines.append(f"**{format_ts(start)}** — {_md_escape(quote)}")
            refs.append({"start": float(start), "end": float(start), "quote": quote[:400]})

    lines.append("")
    lines.append(
        "_Transcript-only reply: these are the video's words, not a generated explanation._"
    )
    return "\n".join(lines), refs


def suggestions(segments: list[Seg], topics: list[str]) -> list[str]:
    texts = [t for _, _, _, t in segments]
    phrases = topics[:4] or [p for p, _ in keyphrases([ParsedSegment(0, 0, t) for t in texts], limit=4)]
    out = []
    for p in phrases:
        out.append(f"Explain {p} in simple terms")
        out.append(f"Why does {p} matter?")
    out.append("Summarize this lecture in 5 bullet points")
    out.append("What should I revise from this lecture?")
    return out[:6]


# ---------------------------------------------------------------- notes
def _first_sentence_per_segment(segments: list[Seg], limit: int) -> list[tuple[float, str]]:
    picked: list[tuple[float, str]] = []
    for _, start, _, text in segments:
        sents = _sentences(text)
        if sents:
            picked.append((start, sents[0]))
        if len(picked) >= limit:
            break
    return picked


def summary_note(title: str, chapters: list[tuple[str, float]], segments: list[Seg]) -> str:
    phrases = keyphrases([ParsedSegment(0, 0, t) for _, _, _, t in segments], limit=8)

    overview_src = _first_sentence_per_segment(segments, 3)
    overview = " ".join(_md_escape(s) for _, s in overview_src)

    lines = [f"# {title} — Summary", ""]
    lines.append("_Generated from the lecture transcript (extractive demo mode)._")
    lines.append("")
    if overview:
        lines.append("## Overview")
        lines.append(overview)
        lines.append("")

    if chapters:
        lines.append("## Sections")
        for name, start in chapters:
            lines.append(f"- **{format_ts(start)} · {name}**")
        lines.append("")

    points = _first_sentence_per_segment(segments[:: max(1, len(segments) // 5)][:5] or segments, 5)
    if points:
        lines.append("## Key points")
        for start, sent in points:
            lines.append(f"- {format_ts(start)} — {_md_escape(sent)}")
        lines.append("")

    if phrases:
        lines.append("## Key terms")
        lines.append(" · ".join(f"`{p}`" for p, _ in phrases))
        lines.append("")
    return "\n".join(lines)


def chapters_note(title: str, chapter_spans: list[tuple[str, float, list[Seg]]]) -> str:
    lines = [f"# {title} — Chapter notes", ""]
    for name, start, segs in chapter_spans:
        lines.append(f"## {format_ts(start)} · {name}")
        lines.append("")
        picks = _first_sentence_per_segment(segs, 4)
        for _, sent in picks:
            lines.append(f"- {_md_escape(sent)}")
        phrases = keyphrases([ParsedSegment(0, 0, s[3]) for s in segs], limit=4)
        if phrases:
            lines.append("")
            lines.append("Key ideas: " + ", ".join(f"`{p}`" for p, _ in phrases))
        lines.append("")
    return "\n".join(lines)


_DEF_PATTERNS = [
    re.compile(r"\b([A-Za-z][A-Za-z\- ]{2,48}?)\s+(?:is|are)\s+(?:defined as|given as|called)\s+([^.;]{10,180})[.;]", re.I),
    re.compile(r"\b([A-Za-z][A-Za-z\- ]{2,48}?)\s+(?:is|are)\s+(?:a|an|the)\s+([^.;]{10,180})[.;]", re.I),
    re.compile(r"\b(?:the term|concept of)\s+([A-Za-z][A-Za-z\- ]{2,48}?)\s+(?:refers to|means)\s+([^.;]{10,180})[.;]", re.I),
]


def definitions_note(title: str, segments: list[Seg]) -> str:
    lines = [f"# {title} — Definitions", ""]
    found = 0
    seen: set[str] = set()
    for _, start, _, text in segments:
        for pat in _DEF_PATTERNS:
            for m in pat.finditer(text):
                term = m.group(1).strip().strip(",:")
                definition = m.group(2).strip()
                key = term.lower()
                if key in seen or len(term) < 3 or len(term) > 60:
                    continue
                seen.add(key)
                lines.append(f"- **{term}** ({format_ts(start)}) — {_md_escape(definition)}")
                found += 1
                break
        if found >= 12:
            break
    if not found:
        lines.append("_No explicit definitions were found in this transcript._")
        lines.append("")
        lines.append("The lecturer may explain concepts without using \"X is a …\" phrasing.")
    return "\n".join(lines)


# ---------------------------------------------------------------- quiz
def _candidate_terms(segments: list[Seg], topics: list[str]) -> list[tuple[str, str, float]]:
    """(term, source sentence, timestamp) candidates from real transcript content."""
    topic_set = {t.lower() for t in topics}
    out: list[tuple[str, str, float]] = []
    for _, start, _, text in segments:
        for sent in _sentences(text):
            m = re.search(
                r"\b([A-Z][a-z]+(?:\s+[A-Za-z\-]+){0,3})\b(?=[^,]{0,40}(?:is|are|means|refers))", sent
            )
            if m:
                term = m.group(1).strip()
                if 3 <= len(term) <= 48:
                    out.append((term, sent, start))
                    continue
            for phrase, _c in keyphrases([ParsedSegment(0, 0, sent)], limit=2):
                if phrase.lower() in sent.lower():
                    idx = sent.lower().find(phrase.lower())
                    window = sent[max(0, idx - 40) : idx + len(phrase) + 60]
                    if re.search(r"\b(is|are|means|refers|called|used|causes|results)\b", window, re.I):
                        out.append((phrase, sent, start))
                        break
    if topic_set:
        filtered = [c for c in out if any(t in c[0].lower() or t in c[1].lower() for t in topic_set)]
        if len(filtered) >= 3:
            return filtered
    return out


def _distractor_terms(correct: str, pool: list[str], n: int = 3) -> list[str]:
    out: list[str] = []
    cl = correct.lower()
    for term in pool:
        tl = term.lower()
        if tl == cl or cl in tl or tl in cl:
            continue
        if term in out:
            continue
        # similar shape = harder distractor
        if abs(len(term) - len(correct)) <= 12:
            out.append(term)
        if len(out) >= n:
            break
    for term in pool:  # top up from anything
        if term not in out and term.lower() != cl:
            out.append(term)
        if len(out) >= n:
            break
    return out


def grade_short(answer: str, reference: str) -> bool:
    """Keyword-recall grading against the transcript's own wording."""
    a = set(re.findall(r"[a-z][a-z\-']{2,}", answer.lower()))
    r = set(re.findall(r"[a-z][a-z\-']{2,}", reference.lower()))
    r = {w for w in r if w not in {"the", "and", "that", "this", "with", "from", "were", "was"}}
    if not a or not r:
        return False
    recall = len(a & r) / len(r)
    return recall >= 0.45 or len(a & r) >= 4


def generate_quiz(
    title: str,
    segments: list[Seg],
    chapters: list[tuple[str, float]],
    count: int,
    difficulty: str,
    topics: list[str],
) -> dict:
    terms = _candidate_terms(segments, topics)
    if not terms:
        # fall back to chapter-based recall questions (still grounded in the transcript)
        terms = [(name, text, start) for (name, start), (_, _, _, text) in zip(
            chapters or [("this lecture", 0.0)], segments[:1]
        )]

    freq = Counter(t[0].lower() for t in terms)
    unique: list[tuple[str, str, float]] = []
    seen: set[str] = set()
    for term, sent, start in terms:
        if term.lower() in seen:
            continue
        seen.add(term.lower())
        unique.append((term, sent, start))

    if difficulty == "easy":
        unique.sort(key=lambda x: -freq[x[0].lower()])
    elif difficulty == "hard":
        unique.sort(key=lambda x: freq[x[0].lower()])
    unique = unique[: max(count, 3)]

    pool = [t for t, _, _ in unique]
    questions: list[dict] = []
    idx = 0
    for term, sent, start in unique:
        if len(questions) >= count:
            break
        topic = _topic_for(chapters, start)
        if idx % 3 == 2 and len(sent) > 60:
            # short-answer question
            questions.append(
                {
                    "idx": idx,
                    "type": "short",
                    "prompt": f"In your own words, explain “{term}” as the lecturer uses it.",
                    "options": None,
                    "answer": sent,
                    "explanation": f"At {format_ts(start)} the lecture says: “{_md_escape(sent)}”",
                    "topic": topic,
                    "difficulty": difficulty if difficulty != "mixed" else "medium",
                }
            )
        else:
            blanked = re.sub(re.escape(term), "_____", sent, count=1, flags=re.I)
            if blanked == sent:
                blanked = f"According to the lecture, what does “{term}” refer to?"
            options = [term] + _distractor_terms(term, pool + _fallback_distractors(term))
            order = _stable_shuffle(options, term)
            questions.append(
                {
                    "idx": idx,
                    "type": "mcq",
                    "prompt": f"Fill in the blank: {_md_escape(blanked)}" if "_____" in blanked
                    else f"Which term matches this statement from the lecture?\n\n“{_md_escape(sent)}”",
                    "options": order,
                    "answer": term,
                    "explanation": f"At {format_ts(start)} the lecture says: “{_md_escape(sent)}”",
                    "topic": topic,
                    "difficulty": difficulty if difficulty != "mixed" else "medium",
                }
            )
        idx += 1

    if not questions:
        raise ValueError("Not enough transcript content to build a quiz")
    return {"questions": questions, "title": title}


def _fallback_distractors(term: str) -> list[str]:
    generic = ["Momentum", "Entropy", "Velocity", "Voltage", "Gradient", "Catalyst", "Allele", "Theorem"]
    return [g for g in generic if g.lower() != term.lower()]


def _stable_shuffle(options: list[str], seed_text: str) -> list[str]:
    """Deterministic order that is stable per question (no randomness across reloads)."""
    pivot = sum(ord(c) for c in seed_text) % max(1, len(options))
    return options[pivot:] + options[:pivot]


def _topic_for(chapters: list[tuple[str, float]], start: float) -> str:
    current = chapters[0][0] if chapters else "General"
    for name, t in chapters:
        if t <= start + 0.01:
            current = name
        else:
            break
    return current


# ---------------------------------------------------------------- explainer script
SCENE_TYPES = ["title", "bullet_list", "formula", "diagram_flow", "comparison", "quote", "summary"]


def generate_script(
    concept: str,
    complexity: str,
    segments: list[Seg],
    chapters: list[tuple[str, float]],
) -> dict:
    q = set(re.findall(r"[a-z][a-z\-']{2,}", concept.lower()))
    relevant = sorted(
        (
            (len(q & set(re.findall(r"[a-z][a-z\-']{2,}", t.lower()))), st, t)
            for _, st, _, t in segments
        ),
        key=lambda x: -x[0],
    )[:12]
    facts = [(st, t) for score, st, t in relevant if score > 0][:6]
    if not facts:
        facts = [(st, t) for _, st, _, t in segments[:6]]

    level_line = {
        "beginner": "Let's start with the basics, no prior knowledge needed.",
        "intermediate": "We'll connect this to what you already know.",
        "advanced": "We'll go deeper into the mechanics.",
    }[complexity]

    scenes: list[dict] = []
    scenes.append(
        {
            "id": 1,
            "type": "title",
            "heading": concept,
            "narration": f"{level_line} Today: {concept}.",
            "bullets": [],
            "formula": "",
            "duration": 4,
        }
    )

    # Scene 2 — what the lecture says
    scene_facts = facts[:4]
    scenes.append(
        {
            "id": 2,
            "type": "bullet_list",
            "heading": f"What the lecture says about {concept}",
            "narration": " ".join(_shorten(t) for _, t in scene_facts[:2]) or
            f"In this lecture, {concept} is introduced as part of the main discussion.",
            "bullets": [_shorten(t, 120) for _, t in scene_facts],
            "formula": "",
            "duration": max(6, min(14, 3 * len(scene_facts))),
        }
    )

    # Scene 3 — mechanism / flow
    scenes.append(
        {
            "id": 3,
            "type": "diagram_flow",
            "heading": "How the pieces connect",
            "narration": (
                f"Follow the chain: {_shorten(facts[0][1], 160) if facts else concept} "
                f"— and that is the core idea behind {concept}."
            ),
            "bullets": [_shorten(t, 90) for _, t in facts[:3]] or [concept],
            "formula": "",
            "duration": 8,
        }
    )

    # Scene 4 — contrast / detail
    if complexity in ("intermediate", "advanced") and len(facts) >= 3:
        scenes.append(
            {
                "id": 4,
                "type": "comparison",
                "heading": "Common mix-ups",
                "narration": (
                    f"Notice the difference: {_shorten(facts[1][1], 150)} "
                    f"Meanwhile, {_shorten(facts[2][1], 150)}"
                ),
                "bullets": [_shorten(t, 100) for _, t in facts[1:3]],
                "formula": "",
                "duration": 8,
            }
        )

    # Scene 5 — takeaway
    scenes.append(
        {
            "id": len(scenes) + 1,
            "type": "summary",
            "heading": "Takeaway",
            "narration": (
                f"So remember: {concept}. "
                + (_shorten(facts[0][1], 160) if facts else "Re-watch the source lecture for the full derivation.")
            ),
            "bullets": [_shorten(t, 100) for _, t in facts[:3]] or [f"Review {concept} in the lecture"],
            "formula": "",
            "duration": 6,
        }
    )

    return {
        "concept": concept,
        "complexity": complexity,
        "level_line": level_line,
        "source_chapters": [name for name, _ in chapters[:4]],
        "scenes": scenes,
    }


def _shorten(text: str, limit: int = 160) -> str:
    text = _md_escape(text)
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut + "…"
