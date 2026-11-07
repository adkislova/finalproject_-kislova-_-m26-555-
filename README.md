# ValutaTrade Hub

Консольное приложение «валютный кошелёк»: пользователи регистрируются, ведут портфели из фиатных и криптовалют, покупают и продают валюту, а актуальные курсы собирает отдельный **Parser Service** из CoinGecko (криптовалюты) и ExchangeRate-API (фиатные валюты) и складывает в локальный кеш `rates.json`.

## Возможности

- Регистрация и вход: пароль хранится только как `sha256(password + salt)`, соль уникальна для каждого пользователя
- Портфель кошельков по валютам, пополнение (`deposit`), покупка/продажа: `buy` списывает USD, `sell` зачисляет выручку в USD
- Актуальные курсы: команда `update-rates` (Parser Service), локальный кеш с TTL, история замеров в `exchange_rates.json`
- Логирование доменных операций (`@log_action`) с ротацией лог-файла
- Таблицы prettytable (`currencies`, `show-rates`), дружелюбные сообщения об ошибках

## Технологии

Python 3.12, uv, ruff, prettytable, requests. Хранение — JSON-файлы в `data/` (без базы данных).

## Структура проекта

```text
finalproject_<фамилия>_<группа>/
├── data/
│   ├── users.json            # пользователи
│   ├── portfolios.json       # портфели (user_id -> кошельки)
│   ├── rates.json            # кеш курсов для Core Service
│   └── exchange_rates.json   # журнал замеров Parser Service
├── valutatrade_hub/
│   ├── logging_config.py     # настройка логов (формат, уровень, ротация)
│   ├── decorators.py         # @log_action
│   ├── core/                 # модели, usecases, валюты, исключения, utils
│   ├── infra/                # синглтоны SettingsLoader и DatabaseManager
│   ├── parser_service/       # config, api_clients, updater, storage
│   └── cli/interface.py      # все команды CLI
├── main.py                   # точка входа
├── pyproject.toml
└── uv.lock
```

## Установка

```bash
uv sync
```

**API-ключи.** Скопируйте `.env.example` в `.env` и вставьте свой ключ (бесплатный, с сайта exchangerate-api.com):

```text
EXCHANGERATE_API_KEY=ваш_ключ
```

Файл `.env` добавлен в `.gitignore` и не коммитится. CoinGecko работает без ключа.

## Запуск

```bash
uv run main.py            # интерактивный режим (REPL)
uv run valutatrade-hub    # то же самое через console-script
```

Можно выполнять и одиночные команды без REPL:

```bash
uv run main.py register --username alice --password 1234
uv run main.py get-rate --from USD --to BTC
```

## Команды CLI

| Команда | Аргументы | Описание |
|---|---|---|
| `register` | `--username`, `--password` | регистрация (пароль не короче 4 символов) |
| `login` | `--username`, `--password` | вход, сессия сохраняется между запусками |
| `deposit` | `[--currency]`, `--amount` | пополнить баланс (по умолчанию USD) |
| `logout` | — | выход из сессии |
| `show-portfolio` | `[--base <str>]` | портфель и стоимость в базовой валюте |
| `buy` | `--currency`, `--amount` | купить валюту: списывает USD, кошелёк создаётся сам |
| `sell` | `--currency`, `--amount` | продать валюту, выручка зачисляется в USD |
| `get-rate` | `--from`, `--to` | курс одной пары + обратный |
| `show-rates` | `[--currency] [--top] [--base]` | все курсы из кеша (таблица) |
| `currencies` | — | поддерживаемые валюты (таблица) |
| `update-rates` | `[--source coingecko\|exchangerate]` | обновить курсы через Parser Service |
| `schedule-rates` | `[--interval <sec>] [--source]` | автообновление курсов по таймеру (Ctrl+C — стоп) |
| `help` | — | список команд |
| `exit` | — | выход |

## Курсы и кеш

Формат `rates.json` — «снимок текущего мира»:

```json
{
  "pairs": {
    "BTC_USD": { "rate": 80076.0, "updated_at": "2026-11-04T20:20:48Z", "source": "CoinGecko" }
  },
  "last_refresh": "2026-11-04T20:20:48Z"
}
```

- Пара `X_USD` хранит, сколько **USD стоит 1 единица** валюты X.
- TTL задаётся в `pyproject.toml` (`[tool.valutatrade]` → `rates_ttl_seconds`, по умолчанию 300) и читается через `SettingsLoader`. Если кеш устарел, Core показывает резервный курс и подсказку выполнить `update-rates`.
- `exchange_rates.json` — журнал всех замеров: `id = FROM_TO_timestamp`, дубли исключены, запись атомарная.
- Parser Service запускается вручную (`update-rates`) или на отдельный источник: `update-rates --source coingecko`.
- Автообновление по таймеру: `schedule-rates --interval 300` — цикл «обновление → пауза», останавливается Ctrl+C.

## Логирование

Логи пишутся в `logs/app.log` (`RotatingFileHandler`, 1 МБ × 5 файлов), уровень — `log_level` из `[tool.valutatrade]` (INFO; для отладки — DEBUG). Каждая доменная операция логируется декоратором `@log_action`

## Качество кода

```bash
uv run ruff check .
uv run ruff format .
```

## Демо

[![Демо ValutaTrade Hub](https://asciinema.org/a/qhyxSqYc0yYFrwWl.svg)](https://asciinema.org/a/qhyxSqYc0yYFrwWl)

