"""SRT generation and timing normalization."""

from __future__ import annotations

import logging
from pathlib import Path

from src.types import SubtitleCue, TranscriptSegment
from utils.text import wrap_subtitle
from utils.timecode import seconds_to_srt_time


def normalize_cue_timing(
    segments: list[TranscriptSegment],
    config: dict,
) -> list[SubtitleCue]:
    """Improve subtitle readability by enforcing duration and gap limits."""

    try:
        subtitle_config = config["subtitles"]
        min_duration = float(subtitle_config.get("min_duration_seconds", 1.2))
        max_duration = float(subtitle_config.get("max_duration_seconds", 6.0))
        cps = float(subtitle_config.get("reading_chars_per_second", 17))
        gap = float(subtitle_config.get("gap_seconds", 0.08))
        max_chars = int(subtitle_config.get("max_chars_per_line", 42))
        max_lines = int(subtitle_config.get("max_lines", 2))

        cues: list[SubtitleCue] = []
        for index, segment in enumerate(segments):
            text = wrap_subtitle(segment.text, max_chars, max_lines)
            readable_duration = max(min_duration, min(max_duration, len(text.replace("\n", "")) / cps))
            start = max(0.0, segment.start)
            end = max(segment.end, start + readable_duration)
            end = min(end, start + max_duration)

            if index + 1 < len(segments):
                next_start = segments[index + 1].start
                if end > next_start - gap:
                    end = max(start + min_duration, next_start - gap)

            cues.append(SubtitleCue(index=len(cues) + 1, start=start, end=end, text=text))
        return cues
    except Exception:
        logging.exception("Falha ao normalizar tempos das legendas.")
        raise


def write_srt(cues: list[SubtitleCue], output_path: Path) -> None:
    """Write cues to a UTF-8 SRT file."""

    try:
        lines: list[str] = []
        for cue in cues:
            lines.extend(
                [
                    str(cue.index),
                    f"{seconds_to_srt_time(cue.start)} --> {seconds_to_srt_time(cue.end)}",
                    cue.text,
                    "",
                ]
            )
        output_path.write_text("\n".join(lines), encoding="utf-8")
    except Exception:
        logging.exception("Falha ao escrever arquivo SRT em %s", output_path)
        raise


def build_preview(cues: list[SubtitleCue], limit: int = 8) -> str:
    """Return a compact preview of the first generated subtitles."""

    try:
        preview_lines: list[str] = []
        for cue in cues[:limit]:
            preview_lines.append(
                f"{cue.index}\n"
                f"{seconds_to_srt_time(cue.start)} --> {seconds_to_srt_time(cue.end)}\n"
                f"{cue.text}\n"
            )
        return "\n".join(preview_lines).strip()
    except Exception:
        logging.exception("Falha ao criar pre-visualizacao.")
        return ""
