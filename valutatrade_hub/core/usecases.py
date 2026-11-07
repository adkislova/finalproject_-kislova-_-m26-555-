from __future__ import annotations

from datetime import UTC, datetime, timedelta

from valutatrade_hub.core.currencies import get_currency
from valutatrade_hub.core.exceptions import (
    ApiRequestError,
    InsufficientFundsError,
    RateUnavailableError,
)
from valutatrade_hub.core.models import Portfolio, User, Wallet
from valutatrade_hub.decorators import log_action
from valutatrade_hub.infra.database import DatabaseManager
from valutatrade_hub.infra.settings import SettingsLoader

settings = SettingsLoader()
db = DatabaseManager()

CRYPTO_CURRENCIES = {"BTC", "ETH"}


@log_action("REGISTER")
def register_user(username: str, password: str) -> User:
    """Register a new user and create an empty portfolio for them."""
    username = username.strip()
    created: User | None = None

    def add_user(users: list) -> list:
        nonlocal created
        if any(u["username"] == username for u in users):
            raise ValueError(f"Имя пользователя '{username}' уже занято")
        user_id = max((u["user_id"] for u in users), default=0) + 1
        created = User.create_new(user_id, username, password)
        users.append(_user_to_dict(created))
        return users

    db.update("users.json", [], add_user)
    assert created is not None
    db.update(
        "portfolios.json",
        [],
        lambda portfolios: [*portfolios, {"user_id": created.user_id, "wallets": {}}],
    )
    return created


@log_action("LOGIN")
def login_user(username: str, password: str) -> User:
    """Check the credentials and store the session for the user."""
    raw = next((u for u in db.load("users.json", []) if u["username"] == username), None)
    if raw is None:
        raise ValueError(f"Пользователь '{username}' не найден")
    user = _user_from_dict(raw)
    if not user.verify_password(password):
        raise ValueError("Неверный пароль")
    db.save("session.json", {"user_id": user.user_id, "username": user.username})
    return user


def logout_user() -> None:
    """Clear the current session."""
    db.save("session.json", {})


def get_current_user() -> User | None:
    """Return the user from the current session, or None if not logged in."""
    session = db.load("session.json", None)
    if not session:
        return None
    raw = next(
        (u for u in db.load("users.json", []) if u["user_id"] == session["user_id"]),
        None,
    )
    return _user_from_dict(raw) if raw else None


def _user_from_dict(raw: dict) -> User:
    """Build a User object from a users.json entry."""
    return User(
        user_id=raw["user_id"],
        username=raw["username"],
        hashed_password=raw["hashed_password"],
        salt=raw["salt"],
        registration_date=datetime.fromisoformat(raw["registration_date"]),
    )


def _user_to_dict(user: User) -> dict:
    """Convert a User object to a users.json entry."""
    return {
        "user_id": user.user_id,
        "username": user.username,
        "hashed_password": user.hashed_password,
        "salt": user.salt,
        "registration_date": user.registration_date.isoformat(),
    }


def _require_user() -> User:
    """Return the logged-in user or raise if there is no active session."""
    user = get_current_user()
    if user is None:
        raise ValueError("Сначала выполните login")
    return user


def show_portfolio(base_currency: str | None = None) -> dict:
    """Return the user's wallets with their values converted to the base currency."""
    user = _require_user()
    base = str(base_currency or settings.get("base_currency", "USD")).strip().upper()
    if base not in Portfolio.exchange_rates:
        raise ValueError(f"Неизвестная базовая валюта '{base}'")
    wallets = _load_portfolio(user.user_id).wallets
    if not wallets:
        return {"user": user.username, "base": base, "empty": True}
    rows = []
    total = 0.0
    for code, wallet in wallets.items():
        rate, _, _ = get_rate(code, base)
        value = wallet.balance * rate
        rows.append({"code": code, "balance": wallet.balance, "value": round(value, 2)})
        total += value
    return {
        "user": user.username,
        "base": base,
        "empty": False,
        "rows": rows,
        "total": round(total, 2),
    }


@log_action("DEPOSIT", verbose=True)
def deposit_currency(currency_code: str, amount: float) -> dict:
    """Top up a wallet balance for the logged-in user (wallet is created on demand)."""
    user = _require_user()
    currency = currency_code.strip().upper()
    if not currency:
        raise ValueError("Код валюты не может быть пустым.")
    get_currency(currency)
    if isinstance(amount, bool) or not isinstance(amount, (int, float)) or amount <= 0:
        raise ValueError("'amount' должен быть положительным числом")
    portfolio = _load_portfolio(user.user_id)
    wallet = (
        portfolio.get_wallet(currency)
        if currency in portfolio.wallets
        else portfolio.add_currency(currency)
    )
    old_balance = wallet.balance
    wallet.deposit(amount)
    _save_portfolio(portfolio)
    return {
        "username": user.username,
        "currency": currency,
        "amount": amount,
        "old_balance": old_balance,
        "new_balance": wallet.balance,
    }


@log_action("BUY", verbose=True)
def buy_currency(currency_code: str, amount: float) -> dict:
    """Buy amount of the currency for the logged-in user, debiting the USD wallet."""
    user = _require_user()
    currency = currency_code.strip().upper()
    if not currency:
        raise ValueError("Код валюты не может быть пустым.")
    get_currency(currency)
    if isinstance(amount, bool) or not isinstance(amount, (int, float)) or amount <= 0:
        raise ValueError("'amount' должен быть положительным числом")
    portfolio = _load_portfolio(user.user_id)
    wallet = (
        portfolio.get_wallet(currency)
        if currency in portfolio.wallets
        else portfolio.add_currency(currency)
    )
    try:
        rate, _, _ = get_rate(currency, "USD")
    except RateUnavailableError:
        raise ValueError(f"Не удалось получить курс для {currency}→USD") from None
    usd_wallet = (
        portfolio.get_wallet("USD") if "USD" in portfolio.wallets else portfolio.add_currency("USD")
    )
    cost = round(amount * rate, 2)
    if usd_wallet.balance < cost:
        raise InsufficientFundsError(available=usd_wallet.balance, required=cost, code="USD")
    usd_wallet.withdraw(cost)
    old_balance = wallet.balance
    wallet.deposit(amount)
    _save_portfolio(portfolio)
    return {
        "username": user.username,
        "currency": currency,
        "amount": amount,
        "old_balance": old_balance,
        "new_balance": wallet.balance,
        "rate": rate,
        "base": "USD",
        "usd_amount": cost,
        "usd_balance": usd_wallet.balance,
    }


@log_action("SELL", verbose=True)
def sell_currency(currency_code: str, amount: float) -> dict:
    """Sell amount of the currency for the logged-in user and credit USD proceeds."""
    user = _require_user()
    currency = currency_code.strip().upper()
    if not currency:
        raise ValueError("Код валюты не может быть пустым.")
    get_currency(currency)
    if isinstance(amount, bool) or not isinstance(amount, (int, float)) or amount <= 0:
        raise ValueError("'amount' должен быть положительным числом")
    portfolio = _load_portfolio(user.user_id)
    if currency not in portfolio.wallets:
        raise ValueError(
            f"У вас нет кошелька '{currency}'. Добавьте валюту: "
            "она создаётся автоматически при первой покупке."
        )
    wallet = portfolio.get_wallet(currency)
    if amount > wallet.balance:
        raise InsufficientFundsError(available=wallet.balance, required=amount, code=currency)
    try:
        rate, _, _ = get_rate(currency, "USD")
    except RateUnavailableError:
        raise ValueError(f"Не удалось получить курс для {currency}→USD") from None
    old_balance = wallet.balance
    wallet.withdraw(amount)
    proceeds = round(amount * rate, 2)
    usd_wallet = (
        portfolio.get_wallet("USD") if "USD" in portfolio.wallets else portfolio.add_currency("USD")
    )
    usd_wallet.deposit(proceeds)
    _save_portfolio(portfolio)
    return {
        "username": user.username,
        "currency": currency,
        "amount": amount,
        "old_balance": old_balance,
        "new_balance": wallet.balance,
        "rate": rate,
        "base": "USD",
        "usd_amount": proceeds,
        "usd_balance": usd_wallet.balance,
    }


def _load_portfolio(user_id: int) -> Portfolio:
    """Load the user's portfolio from portfolios.json (empty if there is none yet)."""
    raw = next((p for p in db.load("portfolios.json", []) if p["user_id"] == user_id), None)
    wallets = {
        code: Wallet(code, w["balance"]) for code, w in (raw or {}).get("wallets", {}).items()
    }
    return Portfolio(user_id, wallets)


def _save_portfolio(portfolio: Portfolio) -> None:
    """Insert or replace the portfolio in portfolios.json."""
    entry = {
        "user_id": portfolio.user_id,
        "wallets": {code: {"balance": w.balance} for code, w in portfolio.wallets.items()},
    }

    def replace_or_add(portfolios: list) -> list:
        for i, item in enumerate(portfolios):
            if item["user_id"] == portfolio.user_id:
                portfolios[i] = entry
                break
        else:
            portfolios.append(entry)
        return portfolios

    db.update("portfolios.json", [], replace_or_add)


def get_rate(from_currency: str, to_currency: str) -> tuple[float, datetime, bool]:
    """Return the from->to rate, its update time and whether the fresh cache was used."""
    from_cur = from_currency.strip().upper()
    to_cur = to_currency.strip().upper()
    if not from_cur or not to_cur:
        raise ValueError("Код валюты не может быть пустым.")
    if from_cur == to_cur:
        return 1.0, datetime.now(), True
    get_currency(from_cur)
    get_currency(to_cur)
    try:
        usd_per_from, ts_from, fresh_from = _get_usd_rate(from_cur)
        usd_per_to, ts_to, fresh_to = _get_usd_rate(to_cur)
    except ApiRequestError:
        raise RateUnavailableError(
            f"Курс {from_cur}→{to_cur} недоступен. Повторите попытку позже."
        ) from None
    return usd_per_from / usd_per_to, max(ts_from, ts_to), fresh_from and fresh_to


def _get_usd_rate(currency: str) -> tuple[float, datetime, bool]:
    """Return the USD rate, its update time and whether it came from fresh cache."""
    if currency == "USD":
        return 1.0, datetime.min, True
    data = db.load("rates.json", {})
    pairs = data.get("pairs") or data
    entry = pairs.get(f"{currency}_USD")
    if entry and _is_fresh(entry):
        return float(entry["rate"]), _parse_updated_at(entry["updated_at"]), True
    rate = _fetch_rate_stub(currency)
    _update_rate_cache(currency, rate)
    return rate, datetime.now(UTC).replace(tzinfo=None), False


def _fetch_rate_stub(currency: str) -> float:
    """Return a fixed USD rate for the currency (stub until the parser service exists)."""
    rates = Portfolio.exchange_rates
    if currency not in rates:
        raise ApiRequestError(f"нет данных для валюты {currency} в источнике")
    return rates[currency]


def _update_rate_cache(currency: str, rate: float) -> None:
    """Store the fetched rate in rates.json as if it came from the parser service."""
    updated_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    def add_rate(data: dict) -> dict:
        pairs = data.setdefault("pairs", {})
        pairs[f"{currency}_USD"] = {
            "rate": rate,
            "updated_at": updated_at,
            "source": "ParserService",
        }
        data["last_refresh"] = updated_at
        return data

    db.update("rates.json", {}, add_rate)


def _parse_updated_at(value: str) -> datetime:
    """Parse a rate timestamp into a naive UTC datetime for comparisons."""
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is not None:
        return parsed.astimezone(UTC).replace(tzinfo=None)
    return parsed


def _is_fresh(entry: dict) -> bool:
    """Check that the cached rate is newer than the configured TTL."""
    updated = _parse_updated_at(entry["updated_at"])
    now = datetime.now(UTC).replace(tzinfo=None)
    ttl = int(settings.get("rates_ttl_seconds", 300))
    return now - updated < timedelta(seconds=ttl)


def get_cached_rates() -> dict:
    """Return the cached rates snapshot with pairs and last_refresh (possibly empty)."""
    data = db.load("rates.json", {})
    if "pairs" in data:
        return data
    pairs = {key: value for key, value in data.items() if isinstance(value, dict)}
    return {"pairs": pairs, "last_refresh": data.get("last_refresh", "")}
