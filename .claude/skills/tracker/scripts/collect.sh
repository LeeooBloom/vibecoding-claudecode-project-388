#!/usr/bin/env bash
# Обходит список URL и печатает запись прогона: одна строка JSON на товар (JSON Lines)
#   {"url": ..., "regular_price": ..., "sale_price": ..., "has_credit": ...}
# stdout — только записи прогона; предупреждения «⚠️ Цена не найдена: URL — причина» идут в stderr.
# Использование: collect.sh [файл-со-ссылками]
# Без аргумента берёт список из SKILL.md — между маркерами <!-- urls:start --> и <!-- urls:end -->.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
SKILL_MD="$HERE/../SKILL.md"
PARSER="$HERE/../../extract-price/scripts/parse_price.py"
WORK="${TMPDIR:-/tmp}/tracker"; mkdir -p "$WORK"
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36'

list_urls() {
  if [ $# -ge 1 ]; then
    grep -vE '^\s*(#|$)' "$1"
  else
    sed -n '/<!-- urls:start -->/,/<!-- urls:end -->/p' "$SKILL_MD" | grep -E '^https?://'
  fi
}

list_urls "$@" | awk '!seen[$0]++' | while read -r raw; do
  # убрать рекламные метки (utm_*, yclid, etext, ...): берём URL до '?'
  url="${raw%%\?*}"
  page="$WORK/page.html"; rm -f "$page"
  # cookie-jar: антибот-редиректы (например, 307 у Ozon) ставят cookie и ждут её при повторе
  for attempt in 1 2; do
    code=$(curl -sSL --max-time 30 -A "$UA" -H 'Accept-Language: ru' \
           -c "$WORK/cookies.txt" -b "$WORK/cookies.txt" \
           -o "$page" -w '%{http_code}' "$url" 2>/dev/null)
    [ "$code" = "200" ] && [ -s "$page" ] && break
    [ "$attempt" = 1 ] && sleep 3
  done
  if [ "$code" != "200" ] || [ ! -s "$page" ]; then
    result="{\"regular_price\": null, \"sale_price\": null, \"has_credit\": false, \"error\": \"страница не загрузилась (HTTP ${code:-000})\"}"
  else
    result=$(python3 -I "$PARSER" "$page")
  fi
  printf '%s' "$result" | python3 -I -c '
import json, sys
r = json.load(sys.stdin)
url = sys.argv[1]
print(json.dumps({"url": url, "regular_price": r.get("regular_price"),
                  "sale_price": r.get("sale_price"), "has_credit": bool(r.get("has_credit"))},
                 ensure_ascii=False))
if r.get("error"):
    print("⚠️ Цена не найдена: " + url + " — " + r["error"], file=sys.stderr)
' "$url"
done
