"""Answer Indeed screening questions from the configured rules + profile.

This is intentionally simple and transparent: it matches the question text
against keyword rules. It does NOT call an LLM, so behavior is predictable and
auditable. You can extend `answer_for` to plug in an LLM if you want.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class Answer:
    """Resolved answer for a screening question."""

    value: str
    confident: bool   # False => we fell back to a weak default / no match


class QuestionResolver:
    def __init__(self, screening_cfg: dict[str, Any], profile: dict[str, Any]) -> None:
        self._rules: list[dict[str, str]] = screening_cfg.get("rules", []) or []
        self._defaults: dict[str, str] = screening_cfg.get("defaults", {}) or {}
        self._profile = profile

    def answer_for(self, question: str) -> Answer:
        """Return the best answer for a free-text/choice question."""
        q = _normalize(question)

        # 1. Direct profile fields that frequently appear as their own questions.
        profile_hit = self._profile_answer(q)
        if profile_hit is not None:
            return Answer(profile_hit, confident=True)

        # 2. Keyword rules from config (first match wins).
        for rule in self._rules:
            needle = _normalize(rule.get("match", ""))
            if needle and needle in q:
                return Answer(str(rule.get("answer", "")), confident=True)

        # 3. Heuristic numeric extraction for "years of experience" style asks.
        if "year" in q and "experience" in q:
            return Answer(self._defaults.get("years_experience", "3"), confident=False)

        # 4. Yes/no leaning: questions phrased "do you / are you / can you / have you"
        #    default to "Yes" unless clearly about sponsorship/visa.
        if re.match(r"^(do|are|can|have|will|did|would)\b", q):
            if any(w in q for w in ("sponsor", "visa")):
                return Answer("No", confident=False)
            return Answer("Yes", confident=False)

        # 5. No idea.
        return Answer("", confident=False)

    def _profile_answer(self, q: str) -> str | None:
        p = self._profile
        mapping = [
            (("first name",), p.get("first_name")),
            (("last name", "surname", "family name"), p.get("last_name")),
            (("full name", "your name"), p.get("full_name")),
            (("email",), p.get("email")),
            (("phone", "mobile", "contact number"), p.get("phone")),
            (("city",), p.get("city")),
            (("state", "province"), p.get("state")),
            (("postal", "zip"), p.get("postal_code")),
            (("country",), p.get("country")),
            (("linkedin",), p.get("linkedin")),
            (("website", "portfolio"), p.get("website")),
        ]
        for needles, value in mapping:
            if value and any(n in q for n in needles):
                return str(value)
        return None


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())
