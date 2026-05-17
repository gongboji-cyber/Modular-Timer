from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

APP_DIR = Path.home() / ".modular_timer_desktop"
STAGES_PATH = APP_DIR / "stages.json"
PREFERENCES_PATH = APP_DIR / "preferences.json"


def ensure_app_dir() -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)


def load_json(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path: Path, data: Any) -> None:
    ensure_app_dir()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
