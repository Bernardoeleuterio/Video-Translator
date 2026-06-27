from utils.youtube import extract_video_id


def test_extract_video_id() -> None:
    urls = [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "http://youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ",
        "https://www.youtube.com/embed/dQw4w9WgXcQ",
        "https://youtube.com/shorts/dQw4w9WgXcQ",
    ]
    for url in urls:
        assert extract_video_id(url) == "dQw4w9WgXcQ"

    assert extract_video_id("https://example.com") is None
