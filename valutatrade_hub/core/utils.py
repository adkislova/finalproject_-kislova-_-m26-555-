from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def hash_password(password: str, salt: str) -> str:
    """Return a one-way pseudo-hash of the password: sha256 of password + salt."""
    return hashlib.sha256((password + salt).encode("utf-8")).hexdigest()


def load_json(filename: str, default: Any) -> Any:
    """Read a JSON file from the data/ folder, or return default if it does not exist yet."""
    path = DATA_DIR / filename
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def save_json(filename: str, data: Any) -> None:
    """Save data to a JSON file in the data/ folder."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / filename
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
