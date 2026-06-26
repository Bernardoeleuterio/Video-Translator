"""Shared typed objects used by the processing pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


StageName = Literal["model", "transcription", "translation", "subtitle", "export", "done", "error"]


@dataclass(slots=True)
class ProgressEvent:
    """Progress information sent from background workers to the GUI."""

    stage: StageName
    percent: float
    message: str
    eta_seconds: float | None = None


@dataclass(slots=True)
class TranscriptSegment:
    """A time-coded speech segment returned by Whisper."""

    start: float
    end: float
    text: str


@dataclass(slots=True)
class SubtitleCue:
    """Final subtitle cue after translation and timing normalization."""

    index: int
    start: float
    end: float
    text: str


@dataclass(slots=True)
class ProcessingResult:
    """Result returned after a video is processed."""

    video_path: Path
    subtitle_path: Path
    preview: str
