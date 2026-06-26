"""SRT time formatting helpers."""

from __future__ import annotations


def seconds_to_srt_time(seconds: float) -> str:
    """Convert seconds to SRT timecode format."""

    seconds = max(0.0, seconds)
    millis = int(round(seconds * 1000))
    hours = millis // 3_600_000
    millis %= 3_600_000
    minutes = millis // 60_000
    millis %= 60_000
    secs = millis // 1000
    millis %= 1000
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"
