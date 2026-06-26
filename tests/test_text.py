from utils.text import normalize_text, wrap_subtitle


def test_normalize_text_adds_punctuation_and_capitalization() -> None:
    assert normalize_text("  olá mundo  ") == "Olá mundo."


def test_wrap_subtitle_limits_to_two_lines() -> None:
    text = "Esta é uma legenda longa que precisa ser quebrada em no máximo duas linhas"
    wrapped = wrap_subtitle(text, max_chars_per_line=25, max_lines=2)
    lines = wrapped.splitlines()
    assert len(lines) <= 2
    assert all(len(line) <= 25 for line in lines)
