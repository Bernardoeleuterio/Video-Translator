from src.subtitles import normalize_cue_timing
from src.types import TranscriptSegment


def test_normalize_cue_timing_keeps_order() -> None:
    config = {
        "subtitles": {
            "max_chars_per_line": 42,
            "max_lines": 2,
            "min_duration_seconds": 1.2,
            "max_duration_seconds": 6.0,
            "reading_chars_per_second": 17,
            "gap_seconds": 0.08,
        }
    }
    cues = normalize_cue_timing(
        [
            TranscriptSegment(0.0, 0.5, "Primeira fala"),
            TranscriptSegment(2.0, 2.4, "Segunda fala"),
        ],
        config,
    )
    assert cues[0].start == 0.0
    assert cues[0].end < cues[1].start
    assert cues[0].index == 1
    assert cues[1].index == 2
