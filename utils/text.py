"""Text cleanup and subtitle wrapping helpers."""

from __future__ import annotations

import logging
import re
import textwrap


COMMON_ASR_FIXES = {
    "İstanbul": "Istambul",
    "Istanbul": "Istambul",
    "Allah Allah": "Nossa",
    "tamam": "tudo bem",
}


def normalize_text(text: str) -> str:
    """Clean spacing, obvious ASR artifacts, punctuation and capitalization."""

    try:
        value = re.sub(r"\s+", " ", text).strip()
        for wrong, right in COMMON_ASR_FIXES.items():
            value = re.sub(rf"\b{re.escape(wrong)}\b", right, value, flags=re.IGNORECASE)
        value = re.sub(r"\s+([,.!?;:])", r"\1", value)
        value = re.sub(r"([,.!?;:])([^\s])", r"\1 \2", value)
        if value and value[-1] not in ".!?":
            value += "."
        return value[:1].upper() + value[1:] if value else value
    except Exception:
        logging.exception("Falha ao normalizar texto: %s", text)
        return text.strip()


def wrap_subtitle(text: str, max_chars_per_line: int, max_lines: int = 2) -> str:
    """Wrap subtitle text into at most two readable lines."""

    try:
        cleaned = normalize_text(text)
        wrapped = textwrap.wrap(
            cleaned,
            width=max_chars_per_line,
            break_long_words=False,
            break_on_hyphens=False,
        )
        if len(wrapped) <= max_lines:
            return "\n".join(wrapped)

        allowed_chars = max_chars_per_line * max_lines
        shortened = cleaned[: max(0, allowed_chars - 1)].rstrip()
        if shortened and shortened[-1] not in ".!?":
            shortened += "..."
        return "\n".join(
            textwrap.wrap(
                shortened,
                width=max_chars_per_line,
                break_long_words=False,
                break_on_hyphens=False,
            )[:max_lines]
        )
    except Exception:
        logging.exception("Falha ao quebrar legenda em linhas.")
        return text
