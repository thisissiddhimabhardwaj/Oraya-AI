"""Retrieval-augmented generation helpers.

Two retrieval backends behind one interface:
  * semantic — Gemini embeddings (`gemini-embedding-001`) when GEMINI_API_KEY is set
  * lexical   — in-process TF-IDF + cosine, always available (demo mode / no key)

Nothing is persisted server-side for vectors here; production swaps the cache for
pgvector (see docs/ARCHITECTURE.md §6).
"""
from __future__ import annotations

import math
import re
import time
from dataclasses import dataclass

from .ai import ai
from ..config import settings

_TOKEN_RE = re.compile(r"[^\W_]+(?:['’-][^\W_]+)*", re.UNICODE)
_STOP = set(
    """a an the and or for are is was were be been being but not you i me my all can her our
    out get has have had him his how now see who did does do its it let say she too use that
    with this will your from they know want good much some very when come make just like
    into look than over also after work well even because any these give most us of in on
    at to as by about which what why please explain describe tell simple simply terms
    mean means matter understand""".split()
)


def tokenize(text: str) -> list[str]:
    words = [re.sub(r"['’]s$", "", w.lower()) for w in _TOKEN_RE.findall(text)]
    return [w for w in words if w not in _STOP]


@dataclass
class Passage:
    segment_ids: list[int]
    start: float
    end: float
    text: str


@dataclass
class ScoredPassage:
    passage: Passage
    score: float
    quote: str
    quote_source: Passage | None = None


class Retriever:
    """TF-IDF cosine by default; semantic embeddings when a Gemini key is configured."""

    def __init__(self) -> None:
        self._cache: dict[int, dict] = {}
        self._semantic_retry_after = 0.0

    def invalidate(self, lecture_id: int) -> None:
        self._cache.pop(lecture_id, None)

    def retrieve(
        self,
        lecture_id: int,
        segments: list[tuple[int, float, float, str]],
        query: str,
        k: int = 6,
    ) -> list[ScoredPassage]:
        """segments: (segment_id, start, end, text)"""
        if not segments:
            return []
        passages = self._to_passages(segments)
        query_tokens = tokenize(query)
        if not query_tokens:
            return []

        # Exact transcript matches should not wait for an external embedding service.
        idf, doc_vecs = self._tfidf([tokenize(p.text) for p in passages])
        qvec = self._tfidf_vector(query_tokens, idf, len(passages))
        scores = [_cosine(qvec, dv) for dv in doc_vecs]
        min_shared = 1 if len(set(query_tokens)) < 3 else 2
        qset = set(query_tokens)
        for i, passage in enumerate(passages):
            if len(qset & set(tokenize(passage.text))) < min_shared:
                scores[i] = 0.0
        if not any(scores) and settings.gemini_enabled and time.monotonic() >= self._semantic_retry_after:
            vecs = self._semantic_vectors(lecture_id, [p.text for p in passages], query)
            if vecs is not None:
                passage_vecs, query_vec = vecs
                scores = [s if s >= 0.65 else 0.0 for s in (_cosine(query_vec, pv) for pv in passage_vecs)]

        ranked = sorted(zip(passages, scores), key=lambda x: -x[1])[:k]
        out: list[ScoredPassage] = []
        for p, s in ranked:
            if s <= 0:
                continue
            quote = self._best_sentence(p, query_tokens)
            out.append(ScoredPassage(passage=p, score=round(s, 4), quote=quote,
                                     quote_source=self._quote_source(p, quote, segments)))
        return out

    def overview(self, segments: list[tuple[int, float, float, str]], k: int = 5, topic: str = "") -> list[ScoredPassage]:
        """Representative context across the video, without a misleading keyword gate."""
        passages = self._to_passages(segments)
        if len(passages) > k:
            passages = [passages[round(i * (len(passages) - 1) / (k - 1))] for i in range(k)]
        out = []
        for p in passages:
            sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", p.text)
                         if len(tokenize(s)) >= 2]
            if not sentences:
                sentences = [p.text[:240]]
            chosen = sentences[:3] if len(passages) == 1 else sentences[:1]
            subject = set(tokenize(topic))
            relevant = [s for s in sentences if subject & set(tokenize(s))]
            if len(passages) == 1 and relevant and relevant[0] not in chosen:
                chosen.append(relevant[0])
            for quote in chosen:
                quote = quote[:400]
                out.append(ScoredPassage(passage=p, score=1.0, quote=quote,
                                        quote_source=self._quote_source(p, quote, segments)))
        return out[:k]

    @staticmethod
    def _quote_source(passage: Passage, quote: str, segments: list[tuple[int, float, float, str]]) -> Passage:
        offset = passage.text.find(quote)
        cursor = 0
        matched = []
        for segment in segments:
            if segment[0] not in passage.segment_ids:
                continue
            end = cursor + len(segment[3])
            if end > offset and cursor < offset + len(quote):
                matched.append(segment)
            cursor = end + 1
        return Retriever._make(matched) if matched else passage

    # ------------------------------------------------------------ internals
    def _to_passages(self, segments: list[tuple[int, float, float, str]]) -> list[Passage]:
        passages: list[Passage] = []
        buf: list[tuple[int, float, float, str]] = []
        size = 0
        for seg in segments:
            buf.append(seg)
            size += len(seg[3])
            if size >= 460:
                passages.append(self._make(buf))
                buf, size = [], 0
        if buf:
            passages.append(self._make(buf))
        return passages

    @staticmethod
    def _make(buf: list[tuple[int, float, float, str]]) -> Passage:
        return Passage(
            segment_ids=[b[0] for b in buf],
            start=buf[0][1],
            end=buf[-1][2],
            text=" ".join(b[3] for b in buf),
        )

    @staticmethod
    def _best_sentence(passage: Passage, query_tokens: list[str]) -> str:
        sentences = re.split(r"(?<=[.!?])\s+", passage.text)
        if not sentences:
            return passage.text[:240]
        best, best_score = sentences[0], -1.0
        qset = set(query_tokens)
        for s in sentences:
            toks = set(tokenize(s))
            score = len(qset & toks) / (math.sqrt(len(toks) or 1))
            if score > best_score:
                best, best_score = s, score
        return best[:400]

    def _tfidf(self, docs: list[list[str]]) -> tuple[dict[str, float], list[dict[str, float]]]:
        n = len(docs)
        df: dict[str, int] = {}
        for d in docs:
            for t in set(d):
                df[t] = df.get(t, 0) + 1
        idf = {t: math.log((n + 1) / (c + 1)) + 1 for t, c in df.items()}
        vecs = []
        for d in docs:
            tf: dict[str, int] = {}
            for t in d:
                tf[t] = tf.get(t, 0) + 1
            vec = {t: (1 + math.log(c)) * idf[t] for t, c in tf.items() if t in idf}
            vecs.append(vec)
        return idf, vecs

    def _tfidf_vector(self, tokens: list[str], idf: dict[str, float], n_docs: int) -> dict[str, float]:
        tf: dict[str, int] = {}
        for t in tokens:
            tf[t] = tf.get(t, 0) + 1
        return {t: (1 + math.log(c)) * idf.get(t, math.log((n_docs + 1) / 1) + 1) for t, c in tf.items()}

    def _semantic_vectors(
        self, lecture_id: int, texts: list[str], query: str
    ) -> tuple[list[dict[str, float]], dict[str, float]] | None:
        cached = self._cache.get(lecture_id)
        if cached and cached.get("texts") == tuple(texts):
            passage_vecs = cached["passages"]
        else:
            try:
                passage_vecs = ai.embed(texts, task_type="RETRIEVAL_DOCUMENT")
            except Exception:
                self._semantic_retry_after = time.monotonic() + 60
                return None
            self._cache[lecture_id] = {"texts": tuple(texts), "passages": passage_vecs}
        try:
            query_vec = ai.embed([query], task_type="RETRIEVAL_QUERY")[0]
        except Exception:
            self._semantic_retry_after = time.monotonic() + 60
            return None
        return passage_vecs, query_vec


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    dot = 0.0
    small, large = (a, b) if len(a) <= len(b) else (b, a)
    for k, v in small.items():
        if k in large:
            dot += v * large[k]
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


retriever = Retriever()
