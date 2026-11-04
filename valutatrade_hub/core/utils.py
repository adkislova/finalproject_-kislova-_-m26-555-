from __future__ import annotations

import hashlib
from typing import Any

from valutatrade_hub.infra.database import DatabaseManager


def hash_password(password: str, salt: str) -> str:
    """Return a one-way pseudo-hash of the password: sha256 of password + salt."""
    return hashlib.sha256((password + salt).encode("utf-8")).hexdigest()


def load_json(filename: str, default: Any) -> Any:
    """Read a JSON file from the storage, or return default if it does not exist yet."""
    return DatabaseManager().load(filename, default)


def save_json(filename: str, data: Any) -> None:
    """Save data to a JSON file in the storage (UTF-8, indented)."""
    DatabaseManager().save(filename, data)
