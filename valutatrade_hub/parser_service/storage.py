from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from valutatrade_hub.infra.database import DatabaseManager
from valutatrade_hub.parser_service.config import ParserConfig


def utc_now() -> str:
    """Return the current UTC time as an ISO string with Z suffix."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class RatesStorage:
    """Read/write access to rates.json (snapshot) and exchange_rates.json (history)."""

    def __init__(self) -> None:
        config = ParserConfig()
        self._db = DatabaseManager()
        self._rates_file = Path(config.RATES_FILE_PATH).name
        self._history_file = Path(config.HISTORY_FILE_PATH).name

    def load_snapshot(self) -> dict:
        """Return the current snapshot from rates.json."""
        return self._db.load(self._rates_file, {})

    def save_snapshot(
        self, rates: dict[str, float], sources: dict[str, str], updated_at: str
    ) -> None:
        """Merge fresh rates into rates.json; a pair is updated only by a fresher value."""

        def merge(data: dict) -> dict:
            pairs = dict(data.get("pairs", {}))
            for pair, rate in rates.items():
                fresh = {
                    "rate": rate,
                    "updated_at": updated_at,
                    "source": sources.get(pair, "Unknown"),
                }
                old = pairs.get(pair)
                if old is None or str(old.get("updated_at", "")) <= updated_at:
                    pairs[pair] = fresh
            return {"pairs": pairs, "last_refresh": updated_at}

        self._db.update(self._rates_file, {}, merge)

    def append_history_entry(
        self, pair: str, rate: float, source: str, meta: dict, timestamp: str
    ) -> None:
        """Append one measurement to exchange_rates.json (deduplicated by id)."""
        from_code, to_code = pair.split("_")
        entry = {
            "id": f"{from_code}_{to_code}_{timestamp}",
            "from_currency": from_code,
            "to_currency": to_code,
            "rate": rate,
            "timestamp": timestamp,
            "source": source,
            "meta": meta,
        }

        def append(entries: list) -> list:
            if any(item["id"] == entry["id"] for item in entries):
                return entries
            entries.append(entry)
            return entries

        self._db.update(self._history_file, [], append)

    def load_history(self) -> list:
        """Return the whole measurement history."""
        return self._db.load(self._history_file, [])
