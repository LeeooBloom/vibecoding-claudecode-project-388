#!/usr/bin/env python3
"""Собирает из вывода diff.py короткую человекочитаемую сводку для Telegram.

Использование:
    python3 -I summary.py <diff.json> [--date YYYY-MM-DD] [--prev-date YYYY-MM-DD] [--commit-url URL]

Печатает текст сообщения: одна строка на значимое изменение (на первом
прогоне — снимок цен, одна строка на товар), затем технические
события (цена не получена / снова доступна). Если значимых изменений нет —
«Значимых изменений цен нет» (трекер всё равно отправляет сообщение, чтобы было
видно, что прогон прошёл).
"""
import argparse
import json
from urllib.parse import urlparse

LABELS = {"regular_price": "цена", "sale_price": "цена со скидкой"}


def domain(url):
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def rub(v):
    """3694 → «3 694 ₽», 3694.5 → «3 694,5 ₽»."""
    if isinstance(v, float) and not v.is_integer():
        s = f"{v:,.2f}".rstrip("0").rstrip(".")
    else:
        s = f"{int(v):,}"
    return s.replace(",", " ").replace(".", ",") + " ₽"


def signed(v, unit):
    sign = "−" if v < 0 else "+"
    num = rub(abs(v))[:-2] if unit == "₽" else f"{abs(v):.2f}".replace(".", ",")
    return f"{sign}{num} {unit}"


def effective(item):
    sp, rp = item.get("sale_price"), item.get("regular_price")
    return sp if sp is not None else rp


def field_line(ch):
    kind, field = ch["kind"], ch.get("field")
    if kind in ("price_down", "price_up"):
        verb = "снизилась" if kind == "price_down" else "выросла"
        return (f"{LABELS[field]} {verb}: {rub(ch['old'])} → {rub(ch['new'])} "
                f"({signed(ch['delta'], '₽')}, {signed(ch['delta_pct'], '%')})")
    if kind == "sale_started":
        return f"появилась скидка: {rub(ch['new'])}"
    if kind == "sale_ended":
        now = ch.get("regular_price")
        return f"скидка закончилась: было {rub(ch['old'])}" + (f", теперь {rub(now)}" if now is not None else "")
    if kind == "credit_added":
        return "появилась рассрочка"
    if kind == "credit_removed":
        return "рассрочка пропала"
    return ch.get("reason", kind)


def item_lines(item):
    d = domain(item["url"])
    if item.get("kind") == "new_item":
        price = effective(item["current"])
        return [f"• {d} — новый товар: " + (f"от {rub(price)}" if price is not None else "цена не найдена")]
    if item.get("kind") == "removed_item":
        price = effective(item["previous"])
        return [f"• {d} — убран из списка" + (f" (было {rub(price)})" if price is not None else "")]
    return [f"• {d} — {field_line(ch)}" for ch in item["fields"]]


def snapshot_line(item):
    """• домен — обычная / со скидкой 💳; «цена не найдена», если цены нет."""
    rp, sp = item.get("regular_price"), item.get("sale_price")
    if rp is None and sp is None:
        return f"• {domain(item['url'])} — цена не найдена"
    price = " / ".join(rub(v) for v in (rp, sp) if v is not None)
    return f"• {domain(item['url'])} — {price}" + (" 💳" if item.get("has_credit") else "")


def tech_line(t):
    d = domain(t["url"])
    if t["kind"] == "price_missing":
        return f"⚠️ {d} — цена не получена (было {rub(t['old'])}), сайт не ответил или защитился от бота"
    if t["kind"] == "price_back":
        return f"ℹ️ {d} — цена снова доступна: {rub(t['new'])}"
    return f"⚠️ {d} — {t.get('reason', t['kind'])}"


def build(diff, date=None, prev_date=None, commit_url=None):
    lines = ["📊 Трекер цен" + (f", {date}" if date else "")]
    if diff.get("first_run"):
        lines = ["📸 Первый прогон — снимок цен" + (f", {date}" if date else ""), ""]
        lines += [snapshot_line(item) for item in diff.get("snapshot", [])]
    elif diff["significant"]:
        lines.append("Значимые изменения" + (f" с прогона {prev_date}:" if prev_date else ":"))
        for item in diff["significant"]:
            lines += item_lines(item)
        dropped = count_insignificant(diff)
        if dropped:
            lines.append(f"Отброшено как незначимое: {dropped}")
    else:
        lines.append("Значимых изменений цен нет")
        dropped = count_insignificant(diff)
        if dropped:
            lines.append(f"(колебаний ниже порога ±1 % / 10 ₽: {dropped})")
    if diff.get("technical"):
        lines.append("")
        lines += [tech_line(t) for t in diff["technical"]]
    if commit_url:
        lines += ["", f"Прогон: {commit_url}"]
    return "\n".join(lines)


def count_insignificant(diff):
    return sum(1 for item in diff["changes"] for ch in item.get("fields", []) if not ch["significant"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("diff")
    ap.add_argument("--date")
    ap.add_argument("--prev-date")
    ap.add_argument("--commit-url")
    a = ap.parse_args()
    with open(a.diff, encoding="utf-8") as f:
        diff = json.load(f)
    print(build(diff, a.date, a.prev_date, a.commit_url))


if __name__ == "__main__":
    main()
