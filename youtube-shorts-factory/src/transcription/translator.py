"""Translate non-English transcripts to natural, mobile-friendly English.

Order of preference:
  1. DeepL (if DEEPL_API_KEY provided) — best quality, sentence-level.
  2. LLM (Groq / OpenAI / Anthropic) — fluent, idiomatic, context-aware.

We translate at the SEGMENT level so word-level timing stays intact
for the caption layer. For karaoke-style highlighting we then split
the English segment text evenly across its original word timings — a
pragmatic compromise that looks great in practice for fast-paced
short-form video.
"""
from __future__ import annotations

import logging
import os
from typing import List

from ..analysis.llm_client import LLMClient
from .whisper_transcriber import Segment, Transcript, WordTiming

log = logging.getLogger("shorts_factory.translate")


SYSTEM_PROMPT = """You translate short video transcripts into natural,
fluent English subtitles. You preserve meaning and emotional tone, keep
sentences short and punchy, and never invent content. If the source is
already English, lightly clean filler words (um, uh, like) but keep
the speaker's voice intact.""".strip()


class Translator:
    def __init__(self, llm: LLMClient):
        self.llm = llm
        self.deepl = None
        deepl_key = os.getenv("DEEPL_API_KEY")
        if deepl_key:
            try:
                import deepl
                self.deepl = deepl.Translator(deepl_key)
                log.info("DeepL translator enabled")
            except Exception as e:  # noqa: BLE001
                log.warning("DeepL init failed, falling back to LLM: %s", e)

    def to_english(self, transcript: Transcript) -> Transcript:
        if transcript.detected_language.lower().startswith("en"):
            return self._clean_english_in_place(transcript)

        # Translate each segment, preserving original word timing.
        english_segments: List[Segment] = []
        for seg in transcript.segments:
            en_text = self._translate_segment(seg.text, transcript.detected_language)
            redistributed = _redistribute_words(en_text, seg)
            english_segments.append(
                Segment(start=seg.start, end=seg.end, text=en_text, words=redistributed)
            )
        return Transcript(
            detected_language="en",
            segments=english_segments,
            full_text=" ".join(s.text.strip() for s in english_segments),
        )

    # ─── Internals ───────────────────────────────────────────────────────
    def _translate_segment(self, text: str, source_lang: str) -> str:
        text = text.strip()
        if not text:
            return ""
        if self.deepl:
            try:
                res = self.deepl.translate_text(text, target_lang="EN-US")
                return res.text  # type: ignore[union-attr]
            except Exception as e:  # noqa: BLE001
                log.warning("DeepL failed; using LLM: %s", e)
        user = (
            f"Source language: {source_lang}\n"
            f"Translate to natural English for mobile subtitles. Keep it punchy.\n"
            f"---\n{text}\n---\nReturn ONLY the English translation."
        )
        return self.llm.chat(SYSTEM_PROMPT, user, max_tokens=400, temperature=0.3).strip()

    def _clean_english_in_place(self, t: Transcript) -> Transcript:
        cleaned: List[Segment] = []
        for s in t.segments:
            cleaned_text = (
                s.text.replace(" um ", " ")
                .replace(" uh ", " ")
                .replace(" like, ", " ")
                .strip()
            )
            cleaned.append(
                Segment(start=s.start, end=s.end, text=cleaned_text, words=s.words)
            )
        return Transcript(
            detected_language="en",
            segments=cleaned,
            full_text=" ".join(s.text for s in cleaned),
        )


def _redistribute_words(en_text: str, original_segment: Segment) -> List[WordTiming]:
    """Spread English words evenly across the original segment's timespan.

    This won't perfectly align words to original phonemes (impossible across
    languages), but it produces clean, even karaoke timing that looks great
    on Shorts. Word-count parity isn't required.
    """
    words = [w for w in en_text.strip().split() if w]
    if not words:
        return []
    total = max(original_segment.end - original_segment.start, 0.001)
    per = total / len(words)
    out: List[WordTiming] = []
    t = original_segment.start
    for w in words:
        out.append(WordTiming(start=t, end=t + per, word=w))
        t += per
    return out
