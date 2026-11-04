from __future__ import annotations

import functools
import inspect
from collections.abc import Callable
from typing import Any

from valutatrade_hub.infra.database import DatabaseManager
from valutatrade_hub.logging_config import get_logger

logger = get_logger("valutatrade_hub.actions")

_FLOAT_FORMATS = {"amount": ".4f", "rate": ".2f", "was": ".4f", "became": ".4f"}


def log_action(action: str, *, verbose: bool = False) -> Callable:
    """Log a domain operation at INFO and re-raise any exception."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            params = inspect.signature(func).bind(*args, **kwargs).arguments
            try:
                result = func(*args, **kwargs)
            except Exception as exc:
                logger.info(
                    "%s %s result=ERROR error_type=%s error_message=%s",
                    action,
                    _fields_str(_call_fields(params)),
                    type(exc).__name__,
                    exc,
                )
                raise
            logger.info("%s %s result=OK", action, _fields_str(_ok_fields(result, params, verbose)))
            return result

        return wrapper

    return decorator


def _ok_fields(result: Any, params: dict, verbose: bool) -> dict[str, Any]:
    """Collect log fields from the call parameters and the operation result."""
    fields = _call_fields(params)
    if isinstance(result, dict):
        for key in ("currency", "amount", "rate", "base"):
            if key in result:
                fields[key] = result[key]
        if verbose and "old_balance" in result:
            fields["was"] = result["old_balance"]
            fields["became"] = result["new_balance"]
    return fields


def _call_fields(params: dict) -> dict[str, Any]:
    """Collect the fields known before the operation runs (user, currency, amount)."""
    fields: dict[str, Any] = {}
    user = params.get("username") or _session_user()
    if user:
        fields["user"] = str(user)
    if params.get("currency_code"):
        fields["currency"] = params["currency_code"]
    if "amount" in params:
        fields["amount"] = params["amount"]
    return fields


def _session_user() -> str | None:
    """Return the username from the current session file, if any."""
    session = DatabaseManager().load("session.json", None)
    return str(session.get("username")) if session else None


def _fields_str(fields: dict[str, Any]) -> str:
    """Render the log fields as key=value pairs."""
    return " ".join(f"{key}={_value_str(key, value)}" for key, value in fields.items())


def _value_str(key: str, value: Any) -> str:
    """Format one log value: floats by field, strings quoted, rest as-is."""
    if isinstance(value, str):
        return f"'{value}'"
    if isinstance(value, (int, float)):
        return f"{value:{_FLOAT_FORMATS.get(key, '.4f')}}"
    return str(value)
