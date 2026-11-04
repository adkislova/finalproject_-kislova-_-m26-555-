from __future__ import annotations

import argparse
import shlex
import sys

from valutatrade_hub.core import usecases
from valutatrade_hub.core.currencies import get_supported_codes
from valutatrade_hub.core.exceptions import (
    ApiRequestError,
    CurrencyNotFoundError,
    InsufficientFundsError,
)


def main() -> None:
    """Run a single command from argv or start the interactive command loop."""
    parser = _build_parser()
    if len(sys.argv) > 1:
        _run_command(parser, sys.argv[1:])
        return
    print("ValutaTrade Hub — консольный валютный кошелёк")
    print("Команды: register, login, show-portfolio, buy, sell, get-rate, exit")
    while True:
        try:
            line = input("> ")
        except (EOFError, KeyboardInterrupt):
            print()
            return
        parts = shlex.split(line)
        if not parts:
            continue
        if parts[0] in ("exit", "quit"):
            return
        _run_command(parser, parts)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="valutatrade-hub")
    sub = parser.add_subparsers(dest="command", required=True)

    register = sub.add_parser("register", help="зарегистрировать нового пользователя")
    register.add_argument("--username", required=True)
    register.add_argument("--password", required=True)
    register.set_defaults(func=_cmd_register)

    login = sub.add_parser("login", help="войти в систему")
    login.add_argument("--username", required=True)
    login.add_argument("--password", required=True)
    login.set_defaults(func=_cmd_login)

    show = sub.add_parser("show-portfolio", help="показать портфель и балансы")
    show.add_argument("--base", default="USD")
    show.set_defaults(func=_cmd_show_portfolio)

    buy = sub.add_parser("buy", help="купить валюту")
    buy.add_argument("--currency", required=True)
    buy.add_argument("--amount", required=True, type=float)
    buy.set_defaults(func=_cmd_buy)

    sell = sub.add_parser("sell", help="продать валюту")
    sell.add_argument("--currency", required=True)
    sell.add_argument("--amount", required=True, type=float)
    sell.set_defaults(func=_cmd_sell)

    rate = sub.add_parser("get-rate", help="показать курс валюты")
    rate.add_argument("--from", dest="from_currency", required=True)
    rate.add_argument("--to", dest="to_currency", required=True)
    rate.set_defaults(func=_cmd_get_rate)
    return parser


def _run_command(parser: argparse.ArgumentParser, argv: list[str]) -> None:
    """Parse argv, execute the command and print business errors without a traceback."""
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return
    try:
        args.func(args)
    except InsufficientFundsError as exc:
        print(exc)
    except CurrencyNotFoundError as exc:
        print(exc)
        print(f"Поддерживаемые коды: {', '.join(get_supported_codes())}")
    except ApiRequestError as exc:
        print(exc)
        print("Повторите попытку позже или проверьте подключение к сети.")
    except usecases.RateUnavailableError as exc:
        print(exc)
    except (ValueError, TypeError) as exc:
        print(exc)


def _cmd_register(args: argparse.Namespace) -> None:
    user = usecases.register_user(args.username, args.password)
    print(
        f"Пользователь '{user.username}' зарегистрирован (id={user.user_id}). "
        f"Войдите: login --username {user.username} --password ****"
    )


def _cmd_login(args: argparse.Namespace) -> None:
    user = usecases.login_user(args.username, args.password)
    print(f"Вы вошли как '{user.username}'")


def _cmd_show_portfolio(args: argparse.Namespace) -> None:
    data = usecases.show_portfolio(args.base)
    if data["empty"]:
        print(f"У пользователя '{data['user']}' пока нет кошельков")
        return
    print(f"Портфель пользователя '{data['user']}' (база: {data['base']}):")
    for row in data["rows"]:
        balance = _fmt_balance(row["code"], row["balance"])
        print(f"- {row['code']}: {balance}  → {row['value']:,.2f} {data['base']}")
    print("-" * 33)
    print(f"ИТОГО: {data['total']:,.2f} {data['base']}")


def _cmd_buy(args: argparse.Namespace) -> None:
    data = usecases.buy_currency(args.currency, args.amount)
    print(
        f"Покупка выполнена: {data['amount']:.4f} {data['currency']} "
        f"по курсу {data['rate']:.2f} USD/{data['currency']}"
    )
    print("Изменения в портфеле:")
    print(
        f"- {data['currency']}: было {_fmt_balance(data['currency'], data['old_balance'])} "
        f"→ стало {_fmt_balance(data['currency'], data['new_balance'])}"
    )
    print(f"Оценочная стоимость покупки: {data['usd_amount']:,.2f} USD")


def _cmd_sell(args: argparse.Namespace) -> None:
    data = usecases.sell_currency(args.currency, args.amount)
    print(
        f"Продажа выполнена: {data['amount']:.4f} {data['currency']} "
        f"по курсу {data['rate']:.2f} USD/{data['currency']}"
    )
    print("Изменения в портфеле:")
    print(
        f"- {data['currency']}: было {_fmt_balance(data['currency'], data['old_balance'])} "
        f"→ стало {_fmt_balance(data['currency'], data['new_balance'])}"
    )
    print(f"Оценочная выручка: {data['usd_amount']:,.2f} USD")


def _cmd_get_rate(args: argparse.Namespace) -> None:
    from_cur = args.from_currency.strip().upper()
    to_cur = args.to_currency.strip().upper()
    rate, updated = usecases.get_rate(from_cur, to_cur)
    print(f"Курс {from_cur}→{to_cur}: {_fmt_rate(rate)} (обновлено: {updated:%Y-%m-%d %H:%M:%S})")
    print(f"Обратный курс {to_cur}→{from_cur}: {_fmt_rate(1 / rate)}")


def _fmt_balance(currency_code: str, value: float) -> str:
    """Format a balance: 4 decimals for crypto, 2 for other currencies."""
    if currency_code in usecases.CRYPTO_CURRENCIES:
        return f"{value:.4f}"
    return f"{value:,.2f}"


def _fmt_rate(rate: float) -> str:
    """Format a rate with up to 8 decimals without trailing zeros."""
    return f"{rate:.8f}".rstrip("0").rstrip(".")
