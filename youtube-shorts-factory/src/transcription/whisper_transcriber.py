"""Multilingual transcription via faster-whisper.

`large-v3` (or `turbo`) gives us best-in-class word-level timestamps
and accurate language detection — both essential for TikTok-style
captions.

Returns a dataclass with:
  • detected_language (ISO 639-1)
  • segments: [{"start","end","text","words":[{"start","end","word"}]}]
  • full_text: concatenated, original-language transcript
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

log = logging.getLogger("shorts_factory.whisper")


@dataclass
class WordTiming:
    start: float
    end: float
    word: str


@dataclass
class Segment:
    start: float
    end: float
    text: str
    words: List[WordTiming] = field(default_factory=list)


@dataclass
class Transcript:
    detected_language: str
    segments: List[Segment]
    full_text: str

    def to_clip_input(self) -> List[dict]:
        """Compact form the viral_detector expects."""
        return [
            {"start": s.start, "end": s.end, "text": s.text} for s in self.segments
        ]


class WhisperTranscriber:
    def __init__(
        self,
        model_name: str = "large-v3",
        device: str = "auto",
        compute_type: str = "auto",
    ):
        from faster_whisper import WhisperModel

        # `auto` lets ctranslate2 pick the best for the host hardware.
        self.model = WhisperModel(model_name, device=device, compute_type=compute_type)
        log.info("Loaded whisper model: %s (device=%s)", model_name, device)

    def transcribe(self, audio_path: str | Path, *, language: Optional[str] = None) -> Transcript:
        """Transcribe audio. If `language` is None, auto-detect."""
        segments_iter, info = self.model.transcribe(
            str(audio_path),
            language=language,
            word_timestamps=True,
            vad_filter=True,
            beam_size=5,
            condition_on_previous_text=False,
            temperature=[0.0, 0.2, 0.4],
        )
        segments: List[Segment] = []
        full_text_parts: List[str] = []
        for seg in segments_iter:
            words = [
                WordTiming(start=w.start, end=w.end, word=w.word)
                for w in (seg.words or [])
                if w.start is not None and w.end is not None
            ]
            segments.append(
                Segment(start=seg.start, end=seg.end, text=seg.text, words=words)
            )
            full_text_parts.append(seg.text)
        log.info(
            "Transcribed %s (lang=%s, segments=%d)",
            audio_path, info.language, len(segments),
        )
        return Transcript(
            detected_language=info.language,
            segments=segments,
            full_text="".join(full_text_parts).strip(),
        )

    @staticmethod
    def slice_for_window(t: Transcript, start_s: float, end_s: float) -> Transcript:
        """Return a new Transcript containing only words inside the window.

        Word-level slicing is critical for accurate, karaoke-style captions
        when the source clip is a sub-window of a longer video.
        """
        segs: List[Segment] = []
        for s in t.segments:
            if s.end < start_s or s.start > end_s:
                continue
            kept_words = [
                w for w in s.words if w.end > start_s and w.start < end_s
            ]
            if not kept_words and not (s.start >= start_s and s.end <= end_s):
                continue
            text = (
                " ".join(w.word.strip() for w in kept_words) if kept_words else s.text
            )
            segs.append(
                Segment(
                    start=max(s.start, start_s),
                    end=min(s.end, end_s),
                    text=text,
                    words=kept_words,
                )
            )
        full_text = " ".join(s.text.strip() for s in segs)
        return Transcript(
            detected_language=t.detected_language,
            segments=segs,
            full_text=full_text,
        )
