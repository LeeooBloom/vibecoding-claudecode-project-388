#!/usr/bin/env python3
"""Сравнивает прошлый и текущий прогон трекера и отбирает значимые изменения.

Использование:
    python3 -I diff.py <прошлый.json | -> <текущий.json|.jsonl>

  прошлый — файл прогона из tracker-data (JSON-массив); "-" — прошлого прогона нет (первый запуск).
  текущий — запись текущего прогона: JSON-массив или JSON Lines (вывод collect.sh).

Печатает JSON:
  {
    "first_run": bool,
    "changes":     [...],   # все отличия по полям, по каждому товару
    "significant": [...],   # только значимые — о них уведомлять
    "technical":   [...]    # проблемы сбора: цена не получена / снова доступна
  }

Правила значимости описаны в KNOWLEDGE.md рядом со скиллом. Константы ниже должны совпадать с ним.
"""
import json
import sys

PRICE_THRESHOLD_PCT = 1.0   # KNOWLEDGE.md, п. 1: порог ±1 %
PRICE_MIN_ABS = 10          # KNOWLEDGE.md, п. 1: и не меньше 10 ₽
FIELDS = ("regular_price", "sale_price", "has_credit")


def load_run(path):
    text = open(path, encoding="utf-8").read().strip()
    if not text:
        return []
    if text.startswith("["):
        return json.loads(text)
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def pct(old, new):
    return round((new - old) / old * 100, 2) if old else None


def price_event(field, old, new):
    """Событие для числового поля цены; None, если поле не изменилось."""
    if old == new:
        return None
    label = "Обычная цена" if field == "regular_price" else "Цена со скидкой"
    if is_num(old) and is_num(new):
        p = pct(old, new)
        significant = abs(p) >= PRICE_THRESHOLD_PCT and abs(new - old) >= PRICE_MIN_ABS
        kind = "price_down" if new < old else "price_up"
        return {"field": field, "kind": kind, "old": old, "new": new, "delta": new - old,
                "delta_pct": p, "significant": significant,
                "reason": f"{label}: {old} → {new} ({p:+.2f} %)"
                          + ("" if significant else f" — ниже порога ±{PRICE_THRESHOLD_PCT:g} % / {PRICE_MIN_ABS} ₽")}
    return {"field": field, "kind": "other", "old": old, "new": new, "significant": False,
            "reason": f"{label}: {old} → {new}"}


def compare_item(url, prev, cur):
    """Возвращает (changes, technical) для одного товара, который есть в обоих прогонах."""
    changes, technical = [], []
    cur_ok = is_num(cur.get("regular_price"))

    # regular_price: число <-> null — это проблема сбора, а не изменение цены (п. 5)
    rp_old, rp_new = prev.get("regular_price"), cur.get("regular_price")
    if is_num(rp_old) and rp_new is None:
        technical.append({"url": url, "kind": "price_missing", "old": rp_old,
                          "reason": f"Цена не получена (в прошлом прогоне было {rp_old})"})
    elif rp_old is None and is_num(rp_new):
        technical.append({"url": url, "kind": "price_back", "new": rp_new,
                          "reason": f"Цена снова доступна: {rp_new} (сравнивать не с чем)"})
    else:
        ev = price_event("regular_price", rp_old, rp_new)
        if ev:
            changes.append(ev)

    # sale_price (п. 2)
    sp_old, sp_new = prev.get("sale_price"), cur.get("sale_price")
    if sp_old is None and is_num(sp_new):
        changes.append({"field": "sale_price", "kind": "sale_started", "old": None, "new": sp_new,
                        "significant": True, "reason": f"Появилась скидка: {sp_new}"
                        + (f" (обычная {rp_new})" if is_num(rp_new) else "")})
    elif is_num(sp_old) and sp_new is None:
        changes.append({"field": "sale_price", "kind": "sale_ended", "old": sp_old, "new": None,
                        "regular_price": rp_new, "significant": cur_ok,
                        "reason": f"Скидка закончилась: было {sp_old}"
                        + (f", теперь {rp_new}" if cur_ok else " — цена не получена, данных нет")})
    else:
        ev = price_event("sale_price", sp_old, sp_new)
        if ev:
            changes.append(ev)

    # has_credit (п. 3)
    hc_old, hc_new = bool(prev.get("has_credit")), bool(cur.get("has_credit"))
    if hc_old != hc_new:
        if hc_new:
            changes.append({"field": "has_credit", "kind": "credit_added", "old": False, "new": True,
                            "significant": True, "reason": "Появилась рассрочка"})
        else:
            changes.append({"field": "has_credit", "kind": "credit_removed", "old": True, "new": False,
                            "significant": cur_ok,
                            "reason": "Рассрочка пропала"
                            + ("" if cur_ok else " — цена не получена, данные недостоверны")})
    return changes, technical


def diff(prev_run, cur_run):
    if prev_run is None:
        return {"first_run": True, "changes": [], "significant": [], "technical": []}

    prev = {r["url"]: r for r in prev_run}
    cur = {r["url"]: r for r in cur_run}
    changes, significant, technical = [], [], []

    for url, c in cur.items():                      # порядок — как в текущем прогоне
        if url not in prev:                          # п. 4: новый товар
            item = {"url": url, "kind": "new_item", "significant": True,
                    "reason": "Новый товар: " + ", ".join(f"{f}={json.dumps(c.get(f))}" for f in FIELDS),
                    "current": {f: c.get(f) for f in FIELDS}}
            changes.append(item)
            significant.append(item)
            continue
        item_changes, item_tech = compare_item(url, prev[url], c)
        technical += item_tech
        if item_changes:
            changes.append({"url": url, "fields": item_changes})
            sig = [ch for ch in item_changes if ch["significant"]]
            if sig:
                significant.append({"url": url, "fields": sig})

    for url, p in prev.items():                      # п. 4: товар пропал
        if url not in cur:
            item = {"url": url, "kind": "removed_item", "significant": True,
                    "reason": "Товар пропал из списка (в прошлом прогоне: "
                              + ", ".join(f"{f}={json.dumps(p.get(f))}" for f in FIELDS) + ")",
                    "previous": {f: p.get(f) for f in FIELDS}}
            changes.append(item)
            significant.append(item)

    return {"first_run": False, "changes": changes, "significant": significant, "technical": technical}


def main(argv):
    if len(argv) != 3:
        sys.exit("usage: diff.py <прошлый.json|-> <текущий.json|.jsonl>")
    prev_run = None if argv[1] == "-" else load_run(argv[1])
    print(json.dumps(diff(prev_run, load_run(argv[2])), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main(sys.argv)
