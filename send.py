#!/usr/bin/env python3
"""Отправляет сообщение в Telegram от имени бота.

Использование:
    python3 send.py "текст сообщения"

Токен и chat id берутся из переменных окружения TELEGRAM_BOT_TOKEN и
TELEGRAM_CHAT_ID, а если их там нет — из файла .env рядом со скриптом
(формат см. в .env.example). Только стандартная библиотека Python.
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.telegram.org/bot{token}/sendMessage"
MAX_LEN = 4096  # лимит Telegram на длину одного сообщения


def load_dotenv(path):
    """Читает KEY=VALUE из .env; пустые строки и комментарии пропускает."""
    values = {}
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return values


def get_settings():
    env_file = load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or env_file.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID") or env_file.get("TELEGRAM_CHAT_ID")
    missing = [n for n, v in (("TELEGRAM_BOT_TOKEN", token), ("TELEGRAM_CHAT_ID", chat_id)) if not v]
    if missing:
        sys.exit("Не задано: " + ", ".join(missing) + ". Укажите в окружении или в .env (см. .env.example).")
    return token, chat_id


def send(text):
    token, chat_id = get_settings()
    if len(text) > MAX_LEN:
        text = text[: MAX_LEN - 1] + "…"
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
    try:
        with urllib.request.urlopen(API.format(token=token), data=data, timeout=30) as resp:
            body = json.load(resp)
    except urllib.error.HTTPError as e:
        try:
            body = json.load(e)
        except ValueError:
            body = {"description": f"HTTP {e.code}"}
    except urllib.error.URLError as e:
        sys.exit(f"Не отправлено: нет связи с api.telegram.org ({e.reason}).")
    if not body.get("ok"):
        sys.exit("Не отправлено: " + str(body.get("description", "неизвестная ошибка")))


def main(argv):
    if len(argv) != 2 or not argv[1].strip():
        sys.exit('Использование: python3 send.py "текст"')
    send(argv[1])
    print("Отправлено.")


if __name__ == "__main__":
    main(sys.argv)
