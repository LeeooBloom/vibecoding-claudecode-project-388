# Трекер цен с Claude


[![hexlet-check](https://github.com/LeeooBloom/vibecoding-claudecode-project-388/actions/workflows/hexlet-check.yml/badge.svg)](https://github.com/LeeooBloom/vibecoding-claudecode-project-388/actions)

Соберите на Claude-скиллах трекер цен: он сам следит за товарами и присылает в Telegram только значимые изменения.

Учебный проект Хекслета: https://ru.hexlet.io/programs/vibecoding-claudecode


## Как это работает

Трекер собран из двух скиллов Claude Code в `.claude/skills/` и пары скриптов на стандартной библиотеке Python:

1. **`extract-price`** — по одной ссылке достаёт `{ regular_price, sale_price, has_credit }` из сырого HTML: JSON-LD, мета-теги, микроразметка, видимый текст.
2. **`tracker`** — обходит список ссылок (`scripts/collect.sh`), сравнивает прогон с прошлым (`scripts/diff.py`), по правилам [`KNOWLEDGE.md`](.claude/skills/tracker/KNOWLEDGE.md) оставляет только значимые изменения (порог ±1 % и не меньше 10 ₽, скидка, рассрочка, новые и пропавшие товары), сохраняет прогон в репозиторий [`tracker-data`](https://github.com/LeeooBloom/tracker-data) как `YYYY-MM-DD.json` и присылает сводку в Telegram через `send.py`.
3. **Sub-agent `tracker-summary`** (`.claude/agents/`, модель Haiku) — формулирует сводку из готового diff: основная модель занимается логикой трекера, дешёвая — только текстом. Запасной вариант без модели — `scripts/summary.py`. Сравнение качества и стоимости — в [`COST.md`](.claude/skills/tracker/COST.md).

Сейчас отслеживаются авиабилеты Москва → Минеральные Воды на OneTwoTrip, Kupibilet, БилетыПлюс и Ozon Travel.

## Стек

- [Claude Code](https://claude.com/claude-code) — скиллы `extract-price` и `tracker`
- Python 3 (только стандартная библиотека), Bash, curl
- GitHub MCP — хранение истории прогонов в `tracker-data`
- Telegram Bot API — уведомления

## Установка

```bash
git clone https://github.com/LeeooBloom/vibecoding-claudecode-project-388.git
cd vibecoding-claudecode-project-388
```

Внешних зависимостей нет: нужны `python3`, `bash` и `curl`.

**Telegram-бот.** Создайте бота у [@BotFather](https://t.me/BotFather) и **напишите ему первым** — иначе бот не сможет вам писать. Chat id можно узнать у [@userinfobot](https://t.me/userinfobot). Затем:

```bash
cp .env.example .env
```

и впишите в `.env` свои `TELEGRAM_BOT_TOKEN` и `TELEGRAM_CHAT_ID`. Файл `.env` в git не попадает. Вместо него можно задать те же переменные окружения.

**GitHub MCP.** Для хранения прогонов Claude Code нужен подключённый сервер `github` (проверьте `/mcp`) с правом записи в репозиторий `tracker-data`.

**Облачная сессия (claude.ai/code).** Если сообщения не уходят, а `send.py` пишет «нет связи с api.telegram.org», добавьте `api.telegram.org` в разрешённые домены окружения (Network access → Custom, флажок списка по умолчанию оставьте включённым) и начните новую сессию.

## Использование

**Проверить бота:**

```bash
python3 send.py "тест"
```

В выводе — `Отправлено.`, в Telegram — сообщение `тест`.

**Запустить трекер** — в Claude Code одной фразой:

```text
запусти трекер
```

или командой `/tracker`. Claude соберёт цены, сравнит с прошлым прогоном, закоммитит прогон в `tracker-data` и пришлёт сводку:

```text
📊 Трекер цен, 2026-11-12
Значимые изменения с прогона 2026-11-11:
• kupibilet.ru — цена выросла: 3 209 ₽ → 3 254 ₽ (+45 ₽, +1,40 %)
• ozon.ru — цена выросла: 3 210 ₽ → 3 448 ₽ (+238 ₽, +7,41 %)

Прогон: https://github.com/LeeooBloom/tracker-data/commit/…
```

На первом прогоне приходит снимок цен по каждому товару, а если значимых изменений нет — «Значимых изменений цен нет».

**Проверить цену одной страницы:** «сколько стоит &lt;ссылка&gt;» — сработает скилл `extract-price`.

**Изменить список ссылок** — строки между маркерами `<!-- urls:start -->` и `<!-- urls:end -->` в [`.claude/skills/tracker/SKILL.md`](.claude/skills/tracker/SKILL.md), или попросите Claude «добавь в трекер &lt;ссылка&gt;».

**Скрипты по отдельности** (без Claude):

```bash
.claude/skills/tracker/scripts/collect.sh > run.jsonl                    # собрать цены
python3 .claude/skills/tracker/scripts/diff.py prev.json run.jsonl > diff.json   # сравнить с прошлым прогоном (или "-" вместо prev.json)
python3 send.py "$(python3 .claude/skills/tracker/scripts/summary.py diff.json)"  # отправить сводку
```

---

<details>
<summary>Автоматические тесты Хекслета</summary>

Тесты запускаются на каждый коммит. За запуск отвечает файл `.github/workflows/hexlet-check.yml` — не удаляйте и не переименовывайте ни его, ни репозиторий.

</details>

## О Хекслете

[Хекслет](https://ru.hexlet.io/) — школа программирования: авторские программы обучения с практикой, поддержкой наставников и реальными проектами, которые остаются в резюме. Этот репозиторий — один из таких проектов.
