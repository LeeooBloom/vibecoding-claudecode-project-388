#!/usr/bin/env python3
"""Извлекает цену из сохранённого HTML страницы.

Использование: python3 -I parse_price.py page.html
Печатает JSON: {"regular_price", "sale_price", "has_credit", "source", "error"}.
Только стандартная библиотека Python.
"""
import html
import json
import re
import sys

CURRENCY = {"₽": "RUB", "р.": "RUB", "руб": "RUB", "руб.": "RUB", "rub": "RUB",
            "$": "USD", "usd": "USD", "€": "EUR", "eur": "EUR"}
CREDIT_WORDS = ("рассрочк", "в кредит", "оплата частями", "долями", "сплит",
                "плайт", "₽/мес", "₽ в месяц", "руб./мес")


def to_number(value):
    """'3 694 ₽' / '3 694,50 р.' / 3194 -> 3694 / 3694.5 / 3194; иначе None."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    s = str(value)
    s = re.sub(r"[\s   ]", "", s)          # пробелы, неразрывные и узкие
    s = re.sub(r"(₽|руб\.?|р\.|RUB|USD|EUR|\$|€|от)", "", s, flags=re.I)
    m = re.search(r"\d+(?:[.,]\d{1,2})?", s)
    if not m:
        return None
    num = float(m.group(0).replace(",", "."))
    return int(num) if num.is_integer() else num


def json_ld_offers(page):
    """Все offers из JSON-LD с @type Product (включая @graph)."""
    found = []

    def walk(node):
        if isinstance(node, list):
            for x in node:
                walk(x)
        elif isinstance(node, dict):
            t = node.get("@type")
            if t == "Product" or (isinstance(t, list) and "Product" in t):
                offers = node.get("offers")
                for o in offers if isinstance(offers, list) else [offers]:
                    if isinstance(o, dict):
                        found.append(o)
            for v in node.values():
                walk(v)

    for raw in re.findall(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', page, re.S):
        try:
            walk(json.loads(raw))
        except ValueError:
            continue
    return found


def from_json_ld(page):
    for o in json_ld_offers(page):
        price = to_number(o.get("lowPrice") or o.get("price"))
        if price:
            return price, "json-ld"
    return None, None


def from_meta(page):
    m = re.search(r'<meta[^>]+(?:product|og):price:amount[^>]+content="([^"]+)"', page, re.I)
    return (to_number(m.group(1)), "meta") if m else (None, None)


def from_microdata(page):
    m = re.search(r'itemprop="(?:lowPrice|price)"[^>]*content="([^"]+)"', page)
    if not m:
        m = re.search(r'content="([^"]+)"[^>]*itemprop="(?:lowPrice|price)"', page)
    return (to_number(m.group(1)), "microdata") if m else (None, None)


def visible_text(page):
    t = re.sub(r"<(script|style|noscript)\b.*?</\1>", " ", page, flags=re.S | re.I)
    t = html.unescape(re.sub(r"<[^>]+>", " ", t))
    return re.sub(r"\s+", " ", t)


def from_text(text):
    prices = [to_number(p) for p in re.findall(r"\d[\d    ]{2,8}(?:,\d{2})?\s?(?:₽|руб\.?|р\.)", text)]
    prices = [p for p in prices if p and p >= 100]
    return (min(prices), "text") if prices else (None, None)


def old_price(page):
    """Зачёркнутая цена рядом с символом валюты (не время и не прочие числа)."""
    m = re.search(r'<(?:s|del|strike)\b[^>]*>\s*([\d\s   ]{3,10})\s*(?:₽|руб|р\.)', page)
    if not m:
        m = re.search(r'class="[^"]*(?:old-?price|price-?old|line-through)[^"]*"[^>]*>\s*'
                      r'([\d\s   ]{3,10})\s*(?:₽|руб|р\.)', page, re.I)
    return to_number(m.group(1)) if m else None


def main(path):
    page = open(path, encoding="utf-8", errors="replace").read()
    text = visible_text(page)
    price, source = None, None
    for finder in (from_json_ld, from_meta, from_microdata):
        price, source = finder(page)
        if price:
            break
    if not price:
        price, source = from_text(text)

    result = {"regular_price": None, "sale_price": None, "has_credit": False,
              "source": source, "error": None}
    low = text.lower()
    result["has_credit"] = any(w in low for w in CREDIT_WORDS)
    if not price:
        spa = len(text) < 3000 or "__LOADABLE_REQUIRED_CHUNKS__" in page or "awswaf" in page
        result["error"] = ("цены подгружаются JavaScript-ом или страница защищена от ботов"
                           if spa else "цена на странице не найдена")
    else:
        old = old_price(page)
        if old and old > price:
            result["regular_price"], result["sale_price"] = old, price
        else:
            result["regular_price"] = price
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: parse_price.py page.html")
    main(sys.argv[1])
