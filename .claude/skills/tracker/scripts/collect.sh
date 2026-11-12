#!/usr/bin/env bash
# Обходит список URL и для каждого печатает одну строку JSON:
# {"url", "regular_price", "sale_price", "has_credit", "error"}
# Использование: collect.sh [файл-со-ссылками]   (по умолчанию — urls.txt рядом со скиллом)
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
LIST="${1:-$HERE/../urls.txt}"
PARSER="$HERE/../../extract-price/scripts/parse_price.py"
WORK="${TMPDIR:-/tmp}/tracker"; mkdir -p "$WORK"
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36'

grep -vE '^\s*(#|$)' "$LIST" | while read -r raw; do
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
    python3 -I -c 'import json,sys; print(json.dumps({"url":sys.argv[1],"regular_price":None,"sale_price":None,"has_credit":False,"error":"страница не загрузилась (HTTP "+sys.argv[2]+")"},ensure_ascii=False))' "$url" "${code:-000}"
    continue
  fi
  python3 -I "$PARSER" "$page" | python3 -I -c 'import json,sys; r=json.load(sys.stdin); r.pop("source",None); print(json.dumps({"url":sys.argv[1],**r},ensure_ascii=False))' "$url"
done
