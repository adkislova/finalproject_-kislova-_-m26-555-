from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from valutatrade_hub.infra.settings import SettingsLoader


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
        """Read a JSON file from the storage, or return default if it does not exist."""
        path = self.data_dir / filename
        if not path.exists():
            return default
        with path.open(encoding="utf-8") as file:
            return json.load(file)

    def save(self, filename: str, data: Any) -> None:
        """Write data to a JSON file in the storage (UTF-8, indented)."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        with (self.data_dir / filename).open("w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
