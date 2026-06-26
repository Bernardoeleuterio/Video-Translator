"""Persistent application configuration."""

from __future__ import annotations

import json
import logging
from copy import deepcopy
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT_DIR / "config.json"

DEFAULT_CONFIG: dict[str, Any] = {
    "language": {"source": "tr", "target": "pt-BR"},
    "whisper": {
        "model": "large-v3",
        "compute_type_gpu": "float16",
        "compute_type_cpu": "int8",
        "beam_size": 5,
        "vad_filter": True,
    },
    "hardware": {"use_gpu": True, "cpu_threads": 0},
    "subtitles": {
        "max_chars_per_line": 42,
        "max_lines": 2,
        "min_duration_seconds": 1.2,
        "max_duration_seconds": 6.0,
        "reading_chars_per_second": 17,
        "gap_seconds": 0.08,
    },
    "processing": {"chunk_minutes": 25, "keep_temp_audio": False},
    "interface": {
        "theme": "dark",
        "default_folder": "",
        "recent_videos": [],
        "window_width": 1100,
        "window_height": 720,
    },
}


def _deep_merge(default: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    """Merge user config into defaults while keeping new default keys available."""

    merged = deepcopy(default)
    for key, value in current.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    """Load `config.json`, creating it if necessary."""

    try:
        if not path.exists():
            save_config(DEFAULT_CONFIG, path)
            return deepcopy(DEFAULT_CONFIG)
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        return _deep_merge(DEFAULT_CONFIG, data)
    except Exception:
        logging.exception("Falha ao carregar config.json; usando valores padrao.")
        return deepcopy(DEFAULT_CONFIG)


def save_config(config: dict[str, Any], path: Path = CONFIG_PATH) -> None:
    """Persist configuration with readable indentation."""

    try:
        path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        logging.exception("Falha ao salvar configuracao em %s", path)
        raise


def add_recent_video(config: dict[str, Any], video_path: Path, limit: int = 10) -> dict[str, Any]:
    """Update recent video history, preserving the newest unique items."""

    try:
        recent = [item for item in config["interface"].get("recent_videos", []) if item != str(video_path)]
        recent.insert(0, str(video_path))
        config["interface"]["recent_videos"] = recent[:limit]
        config["interface"]["default_folder"] = str(video_path.parent)
        save_config(config)
        return config
    except Exception:
        logging.exception("Falha ao atualizar historico de videos.")
        raise
