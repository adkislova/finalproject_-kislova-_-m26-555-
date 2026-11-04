from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from valutatrade_hub.infra.settings import SettingsLoader
from valutatrade_hub.logging_config import get_logger

logger = get_logger("valutatrade_hub.storage")


class DatabaseManager:
    """Singleton abstracting access to the JSON storage of the project."""

    _instance: DatabaseManager | None = None

    def __new__(cls) -> DatabaseManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
        self._settings = SettingsLoader()
        self._initialized = True

    @property
    def data_dir(self) -> Path:
        """Path to the JSON storage folder (resolved from settings)."""
        return Path(__file__).resolve().parents[2] / str(self._settings.get("data_dir", "data"))

    def load(self, filename: str, default: Any = None) -> Any:
        """Read a JSON file, or return default if it is missing or corrupted."""
        path = self.data_dir / filename
        if not path.exists():
            return default
        try:
            with path.open(encoding="utf-8") as file:
                return json.load(file)
        except json.JSONDecodeError:
            logger.warning("Файл %s повреждён, используется значение по умолчанию", filename)
            return default

    def save(self, filename: str, data: Any) -> None:
        """Write data to a JSON file atomically (via a temporary file)."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        path = self.data_dir / filename
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        with tmp_path.open("w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)

    def update(self, filename: str, default: Any, modifier: Callable[[Any], Any]) -> Any:
        """Read a JSON file, apply the modifier and write the result back safely."""
        data = modifier(self.load(filename, default))
        self.save(filename, data)
        return data
