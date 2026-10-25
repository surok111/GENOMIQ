"""
orcid_search.py — поиск исследователей через публичный ORCID API (v2).

Что нового относительно v1:
1. Для каждого найденного профиля делается ВТОРОЙ запрос — к полной записи
   (person + activities-summary). Оттуда тянутся:
   - email (чаще заполнен, чем в expanded-search)
   - страна (person.addresses)
   - ключевые слова (person.keywords)
   - год последней публикации (activities-summary.works)
2. Обогащение опционально (--enrich) — можно быстро собрать список без деталей.
3. Скорость: 50 профилей ≈ 30 сек с обогащением, 5 сек без.

Использование:
    python orcid_search.py --query "keyword:pharmacogenomics" --rows 50 --out test
    python orcid_search.py --query "keyword:CYP2C19" --rows 500 --enrich --only-with-email --out cyp2c19
    python orcid_search.py --query "keyword:pharmacogenomics" --rows 500 --enrich --country "USA"

Зависимости: requests (pip install requests).
"""

import argparse
import csv
import json
import sys
import time
from typing import Optional

try:
    import requests
except ImportError:
    print("Нужен пакет requests. Установите: pip install requests")
    sys.exit(1)


# ============================================================
#  Константы
# ============================================================

ORCID_SEARCH_API = "https://pub.orcid.org/v3.0/expanded-search/"
ORCID_RECORD_API = "https://pub.orcid.org/v3.0/{orcid_id}/record"

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Parsing-Gen/1.0 (mailto:admin@example.com)",
}

MAX_ROWS_PER_REQUEST = 200
SLEEP_BETWEEN = 0.1
SLEEP_ENRICH = 0.15   # пауза между обогащениями (сек)


# ============================================================
#  Поиск профилей (первый запрос)
# ============================================================

def search_orcid(query: str, max_total: int = 200) -> list[dict]:
    """Ищет профили в ORCID по запросу. Возвращает список словарей."""
    all_results = []
    start = 0

    while len(all_results) < max_total:
        rows = min(MAX_ROWS_PER_REQUEST, max_total - len(all_results))
        params = {"q": query, "rows": rows, "start": start}

        print(f"  -> поиск: start={start}, rows={rows}")
        try:
            r = requests.get(ORCID_SEARCH_API, params=params, headers=HEADERS, timeout=30)
        except requests.RequestException as e:
            print(f"  Ошибка запроса: {e}")
            break

        if r.status_code == 429:
            print("  Rate limit. Ждём 5 сек…")
            time.sleep(5)
            continue

        if r.status_code != 200:
            print(f"  HTTP {r.status_code}: {r.text[:200]}")
            break

        data = r.json()
        results = data.get("expanded-result") or []
        if not results:
            print("  Больше нет результатов")
            break

        for item in results:
            all_results.append(_parse_search_result(item))

        start += len(results)
        time.sleep(SLEEP_BETWEEN)

    return all_results


def _parse_search_result(item: dict) -> dict:
    """Парсит один результат из expanded-search."""
    orcid_id = item.get("orcid-id", "")
    given = item.get("given-names") or ""
    family = item.get("family-names") or ""
    name = f"{given} {family}".strip()

    institutions = item.get("institution-name") or []
    if isinstance(institutions, list):
        affiliation = "; ".join(str(x) for x in institutions)
    else:
        affiliation = str(institutions)

    return {
        "orcid_id": orcid_id,
        "name": name,
        "given_names": given,
        "family_name": family,
        "affiliation_search": affiliation,  # из поисковой выдачи
        # Заполним при обогащении:
        "email": "",
        "country": "",
        "keywords": "",
        "last_pub_year": "",
        "affiliation_full": "",
        "orcid_url": f"https://orcid.org/{orcid_id}" if orcid_id else "",
    }


# ============================================================
#  Обогащение полной записи (второй запрос)
# ============================================================

def enrich_profile(orcid_id: str) -> dict:
    """Тянет полную запись ORCID и извлекает email, страну, keywords, год."""
    url = ORCID_RECORD_API.format(orcid_id=orcid_id)
    empty = {"email": "", "country": "", "keywords": "", "last_pub_year": "", "affiliation_full": ""}

    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
    except requests.RequestException:
        return empty

    if r.status_code != 200:
        return empty

    try:
        data = r.json()
    except Exception:
        return empty

    out = dict(empty)

    # --- person: emails ---
    person = data.get("person") or {}

    emails_block = person.get("emails") or {}
    emails_list = emails_block.get("email") or []
    emails = [e.get("email") for e in emails_list if e.get("email")]
    out["email"] = "; ".join(emails)

    # --- person: addresses (страна) ---
    addr_block = person.get("addresses") or {}
    addr_list = addr_block.get("address") or []
    countries = []
    for a in addr_list:
        c = (a.get("country") or {}).get("value")
        if c:
            countries.append(c)
    out["country"] = "; ".join(sorted(set(countries)))

    # --- person: keywords ---
    kw_block = person.get("keywords") or {}
    kw_list = kw_block.get("keyword") or []
    keywords = [k.get("content") for k in kw_list if k.get("content")]
    out["keywords"] = "; ".join(keywords)

    # --- activities-summary: последняя публикация ---
    summary = data.get("activities-summary") or {}
    works_block = (summary.get("works") or {}).get("group") or []

    years = []
    for grp in works_block:
        for ws in grp.get("work-summary") or []:
            y = (ws.get("publication-date") or {}).get("year")
            if y and y.get("value"):
                try:
                    years.append(int(y["value"]))
                except ValueError:
                    pass
    if years:
        out["last_pub_year"] = str(max(years))

    # --- последняя аффилиация (employments) ---
    emp_block = (summary.get("employments") or {}).get("affiliation-group") or []
    last_aff = ""
    for grp in emp_block:
        for s in grp.get("summaries") or []:
            emp = s.get("employment-summary") or {}
            org = (emp.get("organization") or {}).get("name")
            if org:
                last_aff = org
    out["affiliation_full"] = last_aff

    return out


def enrich_all(results: list[dict]) -> list[dict]:
    """Обогащает список профилей полной информацией."""
    total = len(results)
    print(f"  Обогащение {total} профилей (по 1 запросу на каждого)…")

    for i, r in enumerate(results, 1):
        orcid_id = r.get("orcid_id")
        if not orcid_id:
            continue

        if i % 10 == 0 or i == 1:
            print(f"    [{i}/{total}] {r.get('name','?')}")

        info = enrich_profile(orcid_id)
        # email: если в поисковой выдаче уже был — оставляем, если пусто — берём из полного
        if not r.get("email") and info["email"]:
            r["email"] = info["email"]
        # остальные поля всегда обновляем
        r["country"] = info["country"]
        r["keywords"] = info["keywords"]
        r["last_pub_year"] = info["last_pub_year"]
        r["affiliation_full"] = info["affiliation_full"]

        time.sleep(SLEEP_ENRICH)

    return results


# ============================================================
#  Фильтрация
# ============================================================

def filter_results(results: list[dict],
                   only_with_email: bool = False,
                   country_contains: Optional[str] = None,
                   exclude_keywords: Optional[list[str]] = None,
                   min_year: Optional[int] = None) -> list[dict]:
    """Фильтрует список по параметрам."""
    out = []
    exclude_keywords = [k.lower() for k in (exclude_keywords or [])]

    for r in results:
        if only_with_email and not r.get("email"):
            continue

        if country_contains:
            blob = f"{r.get('country','')} {r.get('affiliation_search','')} {r.get('affiliation_full','')}"
            if country_contains.lower() not in blob.lower():
                continue

        if exclude_keywords:
            blob = (r.get("affiliation_search", "") + " " +
                    r.get("affiliation_full", "") + " " +
                    r.get("name", "")).lower()
            if any(k in blob for k in exclude_keywords):
                continue

        if min_year is not None:
            y = r.get("last_pub_year")
            try:
                if int(y) < min_year:
                    continue
            except (TypeError, ValueError):
                continue

        out.append(r)

    return out


# ============================================================
#  Сохранение
# ============================================================

def save_csv(results: list[dict], path: str):
    if not results:
        print(f"  Нечего сохранять в {path}")
        return
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)
    print(f"  CSV: {path}")


def save_json(results: list[dict], path: str):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"  JSON: {path}")


# ============================================================
#  CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Поиск исследователей через ORCID API (v2).")
    parser.add_argument("--query", required=True,
                        help='Lucene-запрос, например "keyword:pharmacogenomics"')
    parser.add_argument("--rows", type=int, default=200,
                        help="Сколько всего записей собрать (по умолчанию 200)")
    parser.add_argument("--out", default="orcid_results",
                        help="Префикс для выходных файлов (без расширения)")
    parser.add_argument("--enrich", action="store_true",
                        help="Тянуть полные профили (email, страна, keywords, год)")
    parser.add_argument("--only-with-email", action="store_true",
                        help="Оставить только тех, у кого указан email")
    parser.add_argument("--country", default=None,
                        help='Подстрока для фильтра, например "USA"')
    parser.add_argument("--exclude", default=None,
                        help='Слова через запятую, которые должны отсутствовать')
    parser.add_argument("--min-year", type=int, default=None,
                        help="Минимальный год последней публикации (например, 2023)")
    args = parser.parse_args()

    exclude_keywords = [s.strip() for s in args.exclude.split(",")] if args.exclude else None

    print("=" * 70)
    print("  ORCID SEARCH v2")
    print("=" * 70)
    print(f"  Query:          {args.query}")
    print(f"  Max rows:       {args.rows}")
    print(f"  Enrich:         {args.enrich}")
    print(f"  Only email:     {args.only_with_email}")
    print(f"  Country:        {args.country}")
    print(f"  Min year:       {args.min_year}")
    print(f"  Exclude:        {exclude_keywords}")
    print()

    # 1. Поиск
    results = search_orcid(args.query, max_total=args.rows)
    print(f"  Найдено: {len(results)}")

    # 2. Обогащение (опционально)
    if args.enrich and results:
        results = enrich_all(results)
        print(f"  Обогащено: {len(results)}")

    # 3. Фильтрация
    results = filter_results(
        results,
        only_with_email=args.only_with_email,
        country_contains=args.country,
        exclude_keywords=exclude_keywords,
        min_year=args.min_year,
    )
    print(f"  После фильтрации: {len(results)}")

    # 4. Сохранение
    save_csv(results, f"{args.out}.csv")
    save_json(results, f"{args.out}.json")

    # 5. Статистика
    if results:
        with_email = sum(1 for r in results if r.get("email"))
        print(f"\n  С email: {with_email} / {len(results)}")

    print("\nГотово.")


if __name__ == "__main__":
    main()