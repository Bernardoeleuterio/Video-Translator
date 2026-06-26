from utils.timecode import seconds_to_srt_time


def test_seconds_to_srt_time() -> None:
    assert seconds_to_srt_time(0) == "00:00:00,000"
    assert seconds_to_srt_time(65.432) == "00:01:05,432"
    assert seconds_to_srt_time(3661.005) == "01:01:01,005"
