from __future__ import annotations

from datetime import datetime, timedelta

from valutatrade_hub.core.exceptions import RateUnavailableError
from valutatrade_hub.core.models import Portfolio, User, Wallet
from valutatrade_hub.core.utils import load_json, save_json

RATE_TTL_SECONDS = 300
CRYPTO_CURRENCIES = {"BTC", "ETH"}


def register_user(username: str, password: str) -> User:
    """Register a new user and create an empty portfolio for them."""
    username = username.strip()
    users = load_json("users.json", [])
    if any(u["username"] == username for u in users):
        raise ValueError(f"Имя пользователя '{username}' уже занято")
    user_id = max((u["user_id"] for u in users), default=0) + 1
    user = User.create_new(user_id, username, password)
    users.append(
        {
            "user_id": user.user_id,
            "username": user.username,
            "hashed_password": user.hashed_password,
            "salt": user.salt,
            "registration_date": user.registration_date.isoformat(),
        }
    )
    save_json("users.json", users)
    portfolios = load_json("portfolios.json", [])
    portfolios.append({"user_id": user.user_id, "wallets": {}})
    save_json("portfolios.json", portfolios)
    return user


def login_user(username: str, password: str) -> User:
    """Check the credentials and store the session for the user."""
    raw = next((u for u in load_json("users.json", []) if u["username"] == username), None)
    if raw is None:
        raise ValueError(f"Пользователь '{username}' не найден")
    user = _user_from_dict(raw)
    if not user.verify_password(password):
        raise ValueError("Неверный пароль")
    save_json("session.json", {"user_id": user.user_id, "username": user.username})
    return user


def get_current_user() -> User | None:
    """Return the user from the current session, or None if not logged in."""
    session = load_json("session.json", None)
    if not session:
        return None
    raw = next(
        (u for u in load_json("users.json", []) if u["user_id"] == session["user_id"]),
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


def _require_user() -> User:
    """Return the logged-in user or raise if there is no active session."""
    user = get_current_user()
    if user is None:
        raise ValueError("Сначала выполните login")
    return user


def show_portfolio(base_currency: str = "USD") -> dict:
    """Return the user's wallets with their values converted to the base currency."""
    user = _require_user()
    base = base_currency.strip().upper()
    if base not in Portfolio.exchange_rates:
        raise ValueError(f"Неизвестная базовая валюта '{base}'")
    wallets = _load_portfolio(user.user_id).wallets
    if not wallets:
        return {"user": user.username, "base": base, "empty": True}
    rows = []
    total = 0.0
    for code, wallet in wallets.items():
        rate, _ = get_rate(code, base)
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


def buy_currency(currency_code: str, amount: float) -> dict:
    """Buy amount of the currency for the logged-in user (wallet is created on demand)."""
    user = _require_user()
    currency = currency_code.strip().upper()
    if not currency:
        raise ValueError("Код валюты не может быть пустым.")
    if isinstance(amount, bool) or not isinstance(amount, (int, float)) or amount <= 0:
        raise ValueError("'amount' должен быть положительным числом")
    portfolio = _load_portfolio(user.user_id)
    wallet = (
        portfolio.get_wallet(currency)
        if currency in portfolio.wallets
        else portfolio.add_currency(currency)
    )
    try:
        rate, _ = get_rate(currency, "USD")
    except RateUnavailableError:
        raise ValueError(f"Не удалось получить курс для {currency}→USD") from None
    old_balance = wallet.balance
    wallet.deposit(amount)
    _save_portfolio(portfolio)
    return {
        "currency": currency,
        "amount": amount,
        "old_balance": old_balance,
        "new_balance": wallet.balance,
        "rate": rate,
        "usd_amount": round(amount * rate, 2),
    }


def sell_currency(currency_code: str, amount: float) -> dict:
    """Sell amount of the currency for the logged-in user and credit USD proceeds."""
    user = _require_user()
    currency = currency_code.strip().upper()
    if not currency:
        raise ValueError("Код валюты не может быть пустым.")
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
        raise ValueError(
            f"Недостаточно средств: доступно {wallet.balance:.4f} {currency}, "
            f"требуется {amount:.4f} {currency}"
        )
    try:
        rate, _ = get_rate(currency, "USD")
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
        "currency": currency,
        "amount": amount,
        "old_balance": old_balance,
        "new_balance": wallet.balance,
        "rate": rate,
        "usd_amount": proceeds,
    }


def _load_portfolio(user_id: int) -> Portfolio:
    """Load the user's portfolio from portfolios.json (empty if there is none yet)."""
    raw = next((p for p in load_json("portfolios.json", []) if p["user_id"] == user_id), None)
    wallets = {
        code: Wallet(code, w["balance"]) for code, w in (raw or {}).get("wallets", {}).items()
    }
    return Portfolio(user_id, wallets)


def _save_portfolio(portfolio: Portfolio) -> None:
    """Insert or replace the portfolio in portfolios.json."""
    portfolios = load_json("portfolios.json", [])
    entry = {
        "user_id": portfolio.user_id,
        "wallets": {code: {"balance": w.balance} for code, w in portfolio.wallets.items()},
    }
    for i, item in enumerate(portfolios):
        if item["user_id"] == portfolio.user_id:
            portfolios[i] = entry
            break
    else:
        portfolios.append(entry)
    save_json("portfolios.json", portfolios)


def get_rate(from_currency: str, to_currency: str) -> tuple[float, datetime]:
    """Return the current from->to rate and its update time (cache first, then the stub)."""
    from_cur = from_currency.strip().upper()
    to_cur = to_currency.strip().upper()
    if not from_cur or not to_cur:
        raise ValueError("Код валюты не может быть пустым.")
    if from_cur == to_cur:
        return 1.0, datetime.now()
    try:
        usd_per_from, ts_from = _get_usd_rate(from_cur)
        usd_per_to, ts_to = _get_usd_rate(to_cur)
    except RateUnavailableError:
        raise RateUnavailableError(
            f"Курс {from_cur}→{to_cur} недоступен. Повторите попытку позже."
        ) from None
    return usd_per_from / usd_per_to, max(ts_from, ts_to)


def _get_usd_rate(currency: str) -> tuple[float, datetime]:
    """Return how many USD one unit of the currency costs, using cache or the stub."""
    if currency == "USD":
        return 1.0, datetime.min
    entry = load_json("rates.json", {}).get(f"{currency}_USD")
    if entry and _is_fresh(entry):
        return float(entry["rate"]), datetime.fromisoformat(entry["updated_at"])
    rate = _fetch_rate_stub(currency)
    _update_rate_cache(currency, rate)
    return rate, datetime.now()


def _fetch_rate_stub(currency: str) -> float:
    """Return a fixed USD rate for the currency (stub until the parser service exists)."""
    rates = Portfolio.exchange_rates
    if currency not in rates:
        raise RateUnavailableError(f"Нет курса для валюты {currency}")
    return rates[currency]


def _update_rate_cache(currency: str, rate: float) -> None:
    """Store the fetched rate in rates.json as if it came from the parser service."""
    now = datetime.now()
    data = load_json("rates.json", {})
    data[f"{currency}_USD"] = {"rate": rate, "updated_at": now.isoformat(timespec="seconds")}
    data["source"] = "ParserService"
    data["last_refresh"] = now.isoformat(timespec="seconds")
    save_json("rates.json", data)


def _is_fresh(entry: dict) -> bool:
    """Check that the cached rate is newer than RATE_TTL_SECONDS."""
    updated = datetime.fromisoformat(entry["updated_at"])
    return datetime.now() - updated < timedelta(seconds=RATE_TTL_SECONDS)
