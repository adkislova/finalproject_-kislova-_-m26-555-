from __future__ import annotations

import hmac
import secrets
from datetime import datetime
from typing import ClassVar

from valutatrade_hub.core.exceptions import InsufficientFundsError
from valutatrade_hub.core.utils import hash_password, load_json


class User:
    def __init__(
        self,
        user_id: int,
        username: str,
        hashed_password: str,
        salt: str,
        registration_date: datetime,
    ) -> None:
        if isinstance(user_id, bool) or not isinstance(user_id, int) or user_id <= 0:
            raise ValueError("user_id должен быть положительным целым числом.")
        if not isinstance(salt, str) or not salt:
            raise ValueError("Соль не может быть пустой.")
        if not isinstance(registration_date, datetime):
            raise TypeError("registration_date должен быть объектом datetime.")

        self._user_id = user_id
        self.username = username  # via the setter: empty-name check
        self.hashed_password = hashed_password  # via the setter
        self._salt = salt
        self._registration_date = registration_date

    @classmethod
    def create_new(cls, user_id: int, username: str, password: str) -> User:
        """Create a new user: generates a unique salt and hashes the password."""
        cls._validate_password(password)
        salt = secrets.token_hex(8)
        return cls(
            user_id=user_id,
            username=username,
            hashed_password=hash_password(password, salt),
            salt=salt,
            registration_date=datetime.now(),
        )

    @staticmethod
    def _validate_password(password: str) -> None:
        """Check that the password is a string of at least 4 characters."""
        if not isinstance(password, str) or len(password) < 4:
            raise ValueError("Пароль должен быть не короче 4 символов.")

    @property
    def user_id(self) -> int:
        """Unique user identifier."""
        return self._user_id

    @property
    def username(self) -> str:
        """The user's name."""
        return self._username

    @username.setter
    def username(self, value: str) -> None:
        """The name must not be empty."""
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Имя пользователя не может быть пустым.")
        self._username = value.strip()

    @property
    def hashed_password(self) -> str:
        """Password hash."""
        return self._hashed_password

    @hashed_password.setter
    def hashed_password(self, value: str) -> None:
        if not isinstance(value, str) or not value:
            raise ValueError("Хеш пароля не может быть пустым.")
        self._hashed_password = value

    @property
    def salt(self) -> str:
        """Salt used for password hashing."""
        return self._salt

    @property
    def registration_date(self) -> datetime:
        """Registration date and time."""
        return self._registration_date

    def get_user_info(self) -> None:
        """Print user information."""
        print(
            f"Пользователь #{self._user_id}\n"
            f"  Имя пользователя: {self._username}\n"
            f"  Дата регистрации: {self._registration_date:%d.%m.%Y %H:%M:%S}"
        )

    def change_password(self, new_password: str) -> None:
        """Change the password: validates the length and stores a new hash (salt unchanged)."""
        self._validate_password(new_password)
        self._hashed_password = hash_password(new_password, self._salt)

    def verify_password(self, password: str) -> bool:
        """Check the given password: True if its hash matches the stored one."""
        return hmac.compare_digest(self._hashed_password, hash_password(password, self._salt))


class Wallet:
    def __init__(self, currency_code: str, balance: float = 0.0) -> None:
        if not isinstance(currency_code, str) or not currency_code.strip():
            raise ValueError("Код валюты не может быть пустым.")
        self.currency_code = currency_code.strip().upper()
        self.balance = balance  # via the setter: type and non-negativity checks

    @property
    def balance(self) -> float:
        """Current wallet balance."""
        return self._balance

    @balance.setter
    def balance(self, value: float) -> None:
        """Forbids negative values and incorrect data types."""
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("Баланс должен быть числом (int или float).")
        if value < 0:
            raise ValueError("Баланс не может быть отрицательным.")
        self._balance = float(value)

    @staticmethod
    def _validate_amount(amount: float) -> float:
        """Check that the amount is a positive number and return it as float."""
        if isinstance(amount, bool) or not isinstance(amount, (int, float)):
            raise TypeError("Сумма должна быть числом (int или float).")
        if amount <= 0:
            raise ValueError("Сумма должна быть положительным числом.")
        return float(amount)

    def deposit(self, amount: float) -> None:
        """Increase the balance by amount."""
        self.balance += self._validate_amount(amount)

    def withdraw(self, amount: float) -> None:
        """Withdraw amount from the balance if there are enough funds."""
        amount = self._validate_amount(amount)
        if amount > self._balance:
            raise InsufficientFundsError(
                available=self._balance, required=amount, code=self.currency_code
            )
        self.balance -= amount

    def get_balance_info(self) -> None:
        """Print information about the current balance."""
        print(f"Кошелёк {self.currency_code}: баланс {round(self.balance, 8)} {self.currency_code}")


class Portfolio:
    exchange_rates: ClassVar[dict[str, float]] = {
        "USD": 1.0,
        "EUR": 1.08,
        "RUB": 0.0105,
        "GBP": 1.27,
        "BTC": 97_500.0,
        "ETH": 3_600.0,
    }

    def __init__(self, user_id: int, wallets: dict[str, Wallet] | None = None) -> None:
        if isinstance(user_id, bool) or not isinstance(user_id, int) or user_id <= 0:
            raise ValueError("user_id должен быть положительным целым числом.")
        self._user_id = user_id
        self._wallets: dict[str, Wallet] = dict(wallets) if wallets else {}

    @property
    def user_id(self) -> int:
        """ID of the portfolio owner."""
        return self._user_id

    @property
    def user(self) -> User:
        """Return the portfolio owner's User object, looked up in users.json."""
        for raw in load_json("users.json", []):
            if raw.get("user_id") == self._user_id:
                return User(
                    user_id=raw["user_id"],
                    username=raw["username"],
                    hashed_password=raw["hashed_password"],
                    salt=raw["salt"],
                    registration_date=datetime.fromisoformat(raw["registration_date"]),
                )
        raise ValueError(f"Пользователь с user_id={self._user_id} не найден в users.json.")

    @property
    def wallets(self) -> dict[str, Wallet]:
        """A copy of the wallets dict."""
        return dict(self._wallets)

    def add_currency(self, currency_code: str) -> Wallet:
        """Add a new wallet with a zero balance and return it."""
        code = currency_code.strip().upper()
        if code in self._wallets:
            raise ValueError(f"Валюта {code} уже есть в портфеле.")
        wallet = Wallet(code)
        self._wallets[code] = wallet
        return wallet

    def get_wallet(self, currency_code: str) -> Wallet:
        """Return the wallet for the given currency code."""
        code = currency_code.strip().upper()
        if code not in self._wallets:
            raise ValueError(f"Валюты {code} нет в портфеле.")
        return self._wallets[code]

    def get_total_value(self, base_currency: str = "USD") -> float:
        """Return the total portfolio value in the base currency using fixed exchange rates."""
        base = base_currency.strip().upper()
        rates = self.exchange_rates
        if base not in rates:
            raise ValueError(f"Неизвестная базовая валюта: {base}")

        total_in_usd = 0.0
        for code, wallet in self._wallets.items():
            if code not in rates:
                raise ValueError(f"Нет курса для валюты {code}.")
            total_in_usd += wallet.balance * rates[code]
        return round(total_in_usd / rates[base], 2)
