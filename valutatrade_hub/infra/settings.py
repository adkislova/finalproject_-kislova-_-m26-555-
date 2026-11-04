from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any, ClassVar


class SettingsLoader:
    """Singleton that loads and caches project configuration from pyproject.toml."""

    DEFAULTS: ClassVar[dict[str, Any]] = {
        "data_dir": "data",
        "rates_ttl_seconds": 300,
        "base_currency": "USD",
        "log_file": "logs/app.log",
        "log_level": "INFO",
        "log_format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    }

    _instance: SettingsLoader | None = None

    def __new__(cls) -> SettingsLoader:

        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
        self._config = self._load()
        self._initialized = True

    def get(self, key: str, default: Any = None) -> Any:
        """Return the setting value by key, or default when the key is not set."""
        return self._config.get(key, default)

    def reload(self) -> None:
        """Re-read the configuration file."""
        self._config = self._load()

    def _load(self) -> dict[str, Any]:
        """Merge DEFAULTS with the [tool.valutatrade] section of pyproject.toml."""
        config = dict(self.DEFAULTS)
        pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
        if pyproject.exists():
            with pyproject.open("rb") as file:
                data = tomllib.load(file)
            config.update(data.get("tool", {}).get("valutatrade", {}))
        return config
