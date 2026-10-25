"""
Аналитическая система для базы знаний по генетике (v3).

Улучшения относительно v2:
- Убран "ложный риск" (высокий потенциал / высокая активность).
- sec.title исключён из частотного анализа.
- Расширены стоп-слова.
- Добавлена карта групп (средний/макс. риск по каждой группе).
- Добавлен отчёт о пробелах (гены без таблиц/рекомендаций).
- Добавлены ключевые термины по группам.
"""

import json
import re
from collections import Counter, defaultdict
from pathlib import Path


SRC = "data/parsed_knowledge_base_clean.json"
OUT_JSON = "reports/analysis_report.json"
OUT_MD = "reports/analysis_report.md"


# ---------- Загрузка ----------

def load_base(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------- Утилиты ----------

def extract_gene_name(header: str) -> str:
    m = re.match(r'^([A-Z0-9/ ]+?)\s*[—\-–]', header)
    if m:
        return m.group(1).strip()
    return header.split()[0] if header.split() else header


RISK_COL_HINTS = ("риск", "профиль", "фенотип", "влияние")


def get_risk_columns(headers: list[str]) -> list[str]:
    cols = []
    for h in headers:
        hl = h.lower()
        if any(hint in hl for hint in RISK_COL_HINTS):
            cols.append(h)
    return cols


def extract_risk_values(section: dict) -> list[str]:
    values = []
    for tbl in section.get("tables", []):
        cols = get_risk_columns(tbl.get("headers", []))
        for row in tbl.get("rows", []):
            for c in cols:
                v = row.get(c, "").strip()
                if v:
                    values.append(v)
    return values


def extract_acmg_values(section: dict) -> list[str]:
    values = []
    for tbl in section.get("tables", []):
        for h in tbl.get("headers", []):
            if 'acmg' in h.lower():
                for row in tbl.get("rows", []):
                    v = row.get(h, "").strip()
                    if v:
                        values.append(v)
    return values


# Маркеры, по которым стоит включать bullet в анализ риска
BULLET_RISK_HINTS = [
    'metabolizer', 'риск', 'патоген', 'нарушение', 'снижен',
    'тяжел', 'тромбоз', 'инфаркт', 'кровотечен', 'рецидив',
    'неэффектив', 'токсич', 'дефицит',
]


def extract_bullet_risks(section: dict) -> list[str]:
    out = []
    for b in section.get("bullets", []):
        bl = b.lower()
        if any(h in bl for h in BULLET_RISK_HINTS):
            out.append(b)
    return out


# ---------- Оценки ----------

GOOD_PHRASES = [
    'высокий потенциал', 'высокая активность', 'высокое сродство',
    'высокая чувствительность', 'повышенная чувствительность',
    'нормальная активность', 'эффективная реактивация',
    'нормальное сродство', 'базовый', 'benign',
]

def risk_score(risk_text: str) -> int:
    """
    0..3 — 'тяжесть' риска по тексту.

    0 — базовый/норма
    1 — низкий/likely benign/trait
    2 — умеренный/risk factor/снижен
    3 — высокий/патогенный/poor metabolizer
    """
    t = risk_text.lower()

    # Если внутри есть "хорошая" фраза и нет "плохих" слов — это не риск.
    if any(g in t for g in GOOD_PHRASES):
        if not any(bad in t for bad in
                   ['риск', 'патоген', 'нарушение', 'снижен', 'тяжел']):
            return 0

    # Явные "плохие" маркеры
    if 'poor metabolizer' in t:
        return 3
    if 'ultra-rapid' in t or 'ультрабыстр' in t:
        return 3
    if 'pathogenic' in t and 'risk factor' not in t:
        return 3
    if 'тяжел' in t and 'заболева' in t:
        return 3
    if 'высок' in t and 'риск' in t:
        return 3
    if 'повышен' in t and 'риск' in t:
        return 3
    if 'риск' in t and 'тромбоз' in t:
        return 3

    # Средние
    if 'intermediate metabolizer' in t:
        return 2
    if 'risk factor' in t:
        return 2
    if 'умерен' in t or 'moderate' in t:
        return 2
    if 'снижен' in t and 'риск' in t:
        return 2

    # Низкие
    if 'likely benign' in t or 'trait' in t:
        return 1
    if 'низк' in t or 'low' in t:
        return 1

    # Хорошие
    if 'benign' in t or 'базов' in t or 'норма' in t:
        return 0
    if 'extensive metabolizer' in t:
        return 0

    return 0


def acmg_score(acmg_text: str) -> int:
    t = acmg_text.lower()
    if 'pathogenic' in t and 'risk factor' not in t:
        return 3
    if 'pathogenic' in t:
        return 3
    if 'risk factor' in t:
        return 2
    if 'likely' in t:
        return 1
    if 'trait' in t:
        return 1
    if 'benign' in t:
        return 0
    return 0


# ---------- 1. Карта генов ----------

def build_risk_map(base: list[dict]) -> dict:
    result = {}
    for group in base:
        for gene in group["genes"]:
            name = extract_gene_name(gene["header"])
            risks, acmgs = [], []
            for sec in gene["sections"]:
                risks.extend(extract_risk_values(sec))
                risks.extend(extract_bullet_risks(sec))
                acmgs.extend(extract_acmg_values(sec))
            result[name] = {
                "group": group["group"],
                "risks": risks,
                "acmgs": acmgs,
                "max_risk": max((risk_score(r) for r in risks), default=0),
                "max_acmg": max((acmg_score(a) for a in acmgs), default=0),
            }
    return result


# ---------- 2. Токсичность ----------

def compute_toxicity(risk_map: dict) -> list[dict]:
    rows = []
    for gene, info in risk_map.items():
        r_sum = sum(risk_score(r) for r in info["risks"])
        a_max = info["max_acmg"]
        r_max = info["max_risk"]
        composite = a_max * 3 + r_max + r_sum * 0.5
        rows.append({
            "gene": gene,
            "risk_sum": r_sum,
            "max_risk": r_max,
            "max_acmg": a_max,
            "score": composite,
        })
    rows.sort(key=lambda x: x["score"], reverse=True)
    return rows


# ---------- 3. Близнецы ----------

def find_twins(risk_map: dict) -> list[tuple]:
    by_profile = defaultdict(list)
    for gene, info in risk_map.items():
        key = (info["max_risk"], info["max_acmg"])
        by_profile[key].append(gene)
    return [(k, v) for k, v in by_profile.items() if len(v) > 1]


# ---------- 4. Мины ----------

def find_mines(base: list[dict]) -> list[dict]:
    mines = []
    keywords = ['критическ', 'двойной удар', 'повышается', 'усиливает',
                'накладывается', 'риск']
    for group in base:
        for tbl in group.get("interactions", {}).get("tables", []):
            headers = tbl.get("headers", [])
            if len(headers) < 2:
                continue
            combo_col, effect_col = headers[0], headers[1]
            for row in tbl["rows"]:
                combo = row.get(combo_col, "")
                effect = row.get(effect_col, "")
                if any(kw in effect.lower() for kw in keywords):
                    severity = 'critical' if ('критическ' in effect.lower()
                                              or 'двойной' in effect.lower()) else 'high'
                    mines.append({
                        "group": group["group"],
                        "combination": combo,
                        "effect": effect,
                        "severity": severity,
                    })
    return mines


# ---------- 5. Граф упоминаний ----------

def build_gene_graph(base: list[dict]) -> dict:
    all_genes = set()
    for group in base:
        for gene in group["genes"]:
            all_genes.add(extract_gene_name(gene["header"]))
    meaningful = {g for g in all_genes if len(g) >= 3 and g != "MCM6 / LCT"}

    graph = defaultdict(set)
    for group in base:
        for gene in group["genes"]:
            src = extract_gene_name(gene["header"])
            pieces = [gene.get("intro", "")]
            for sec in gene["sections"]:
                pieces.append(sec.get("title", ""))
                pieces.append(sec.get("text", ""))
                pieces.extend(sec.get("bullets", []))
                for tbl in sec.get("tables", []):
                    for row in tbl.get("rows", []):
                        pieces.extend(str(v) for v in row.values())
            blob = " ".join(pieces)
            for other in meaningful:
                if other == src:
                    continue
                if re.search(rf'(?<![A-Za-z0-9]){re.escape(other)}(?![A-Za-z0-9])', blob):
                    graph[src].add(other)
    return {k: sorted(v) for k, v in graph.items()}


# ---------- 6. Лексика ----------

STOPWORDS = {
    'и', 'в', 'на', 'с', 'по', 'для', 'при', 'из', 'к', 'о', 'об', 'от', 'до',
    'не', 'но', 'или', 'а', 'что', 'как', 'это', 'то', 'же', 'бы', 'ли',
    'так', 'все', 'у', 'их', 'его', 'её', 'мы', 'вы', 'они', 'он', 'она',
    'может', 'могут', 'быть', 'есть', 'также', 'более', 'менее', 'только',
    'если', 'то', 'the', 'a', 'an', 'of', 'in', 'to', 'and', 'or', 'is', 'are',
    'p', 'c', 'g', 't', 'n', 'rs', 'sn', 'sp', 'na',
    # служебные:
    'эффект', 'общая', 'информация', 'параметр', 'описание', 'риск',
    'генотип', 'генотипы', 'аллели', 'частота', 'название', 'полное',
    'omim', 'gene', 'rsid', 'функция', 'вариант', 'значение', 'клинический',
    'рекомендации', 'ассоциации', 'клиническое', 'применение',
    'раздел', 'подраздел', 'пункт', 'группа', 'пациента', 'пациент',
}


def lexical_density(base: list[dict], top_n: int = 30) -> list[tuple]:
    words = Counter()
    for group in base:
        for gene in group["genes"]:
            pieces = [gene.get("intro", "")]
            for sec in gene["sections"]:
                # НЕ включаем sec['title']
                pieces.append(sec.get("text", ""))
                pieces.extend(sec.get("bullets", []))
            for blob in pieces:
                for w in re.findall(r'[А-Яа-яA-Za-z]{4,}', blob.lower()):
                    if w not in STOPWORDS and not w.isdigit():
                        words[w] += 1
    return words.most_common(top_n)


# ---------- 7. Паспорт ----------

def gene_passport(base: list[dict], gene_name: str) -> dict:
    for group in base:
        for gene in group["genes"]:
            if extract_gene_name(gene["header"]).lower() != gene_name.lower():
                continue
            general, genotypes, recs = {}, [], []
            for sec in gene["sections"]:
                for tbl in sec["tables"]:
                    headers = tbl.get("headers", [])
                    if "Генотип" in headers:
                        genotypes.extend(tbl["rows"])
                    if sec["code"].endswith(".1"):
                        for row in tbl["rows"]:
                            vals = list(row.values())
                            if len(vals) >= 2:
                                general[vals[0]] = vals[1]
                recs.extend(sec.get("bullets", []))
            return {
                "name": extract_gene_name(gene["header"]),
                "header": gene["header"],
                "group": group["group"],
                "general": general,
                "genotypes": genotypes,
                "recommendations": recs,
            }
    return {}


# ---------- 8. Карта групп ----------

def build_group_map(base: list[dict], risk_map: dict) -> list[dict]:
    by_group = defaultdict(list)
    for gene, info in risk_map.items():
        by_group[info["group"]].append(gene)

    result = []
    for grp in base:
        name = grp["group"]
        genes = by_group.get(name, [])
        if not genes:
            continue
        risks = [risk_map[g]["max_risk"] for g in genes]
        acmgs = [risk_map[g]["max_acmg"] for g in genes]
        result.append({
            "group": name,
            "genes_count": len(genes),
            "avg_max_risk": round(sum(risks) / len(risks), 2),
            "max_risk_overall": max(risks),
            "avg_max_acmg": round(sum(acmgs) / len(acmgs), 2),
            "max_acmg_overall": max(acmgs),
            "genes": genes,
        })
    result.sort(key=lambda x: x["avg_max_risk"], reverse=True)
    return result


# ---------- 9. Пробелы в базе ----------

def build_gaps(base: list[dict]) -> list[dict]:
    gaps = []
    for group in base:
        for gene in group["genes"]:
            name = extract_gene_name(gene["header"])
            has_genotype_table = False
            has_recommendations = False
            for sec in gene["sections"]:
                for tbl in sec["tables"]:
                    if "Генотип" in tbl.get("headers", []):
                        has_genotype_table = True
                if sec.get("bullets"):
                    has_recommendations = True

            issues = []
            if not has_genotype_table:
                issues.append("нет таблицы генотипов")
            if not has_recommendations:
                issues.append("нет рекомендаций")
            if issues:
                gaps.append({
                    "gene": name,
                    "group": group["group"],
                    "issues": issues,
                })
    return gaps


# ---------- 10. Ключевые термины по группам ----------

def group_terms(base: list[dict], top_n: int = 10) -> dict:
    result = {}
    for group in base:
        words = Counter()
        for gene in group["genes"]:
            pieces = [gene.get("intro", "")]
            for sec in gene["sections"]:
                pieces.append(sec.get("text", ""))
                pieces.extend(sec.get("bullets", []))
            for blob in pieces:
                for w in re.findall(r'[А-Яа-яA-Za-z]{4,}', blob.lower()):
                    if w not in STOPWORDS and not w.isdigit():
                        words[w] += 1
        result[group["group"]] = words.most_common(top_n)
    return result


# ---------- 11. Отчёт ----------

def build_report(base: list[dict]) -> dict:
    risk_map = build_risk_map(base)
    toxicity = compute_toxicity(risk_map)
    twins = find_twins(risk_map)
    mines = find_mines(base)
    graph = build_gene_graph(base)
    density = lexical_density(base, top_n=25)
    group_map = build_group_map(base, risk_map)
    gaps = build_gaps(base)
    g_terms = group_terms(base, top_n=10)

    all_names = [extract_gene_name(g["header"])
                 for grp in base for g in grp["genes"]]
    passports = {n: gene_passport(base, n) for n in all_names}

    return {
        "summary": {
            "groups": len(base),
            "genes_total": len(all_names),
            "genes": all_names,
        },
        "risk_map": risk_map,
        "toxicity_ranking": toxicity,
        "twins": [{"profile": {"max_risk": k[0], "max_acmg": k[1]}, "genes": v}
                  for k, v in twins],
        "mines": mines,
        "gene_graph": graph,
        "lexical_density": density,
        "group_map": group_map,
        "gaps": gaps,
        "group_terms": g_terms,
        "passports": passports,
    }


# ---------- 12. Вывод ----------

def print_report(report: dict):
    print("=" * 78)
    print("  АНАЛИЗ БАЗЫ ЗНАНИЙ ПО ГЕНЕТИКЕ (v3)")
    print("=" * 78)
    s = report["summary"]
    print(f"\n📊 Всего: {s['groups']} групп, {s['genes_total']} генов")

    print("\n" + "─" * 78)
    print("  🔥 РЕЙТИНГ ОПАСНОСТИ")
    print("─" * 78)
    for i, row in enumerate(report["toxicity_ranking"], 1):
        bar = "█" * min(int(row["score"]), 20)
        print(f"  {i:2}. {row['gene']:15} {bar:20} "
              f"score={row['score']:5.1f}  ACMG={row['max_acmg']} "
              f"max_risk={row['max_risk']} risk_sum={row['risk_sum']}")

    print("\n" + "─" * 78)
    print("  👯  ГЕНЫ-БЛИЗНЕЦЫ")
    print("─" * 78)
    if not report["twins"]:
        print("  — не найдено")
    for t in report["twins"]:
        p = t["profile"]
        print(f"  risk={p['max_risk']}, ACMG={p['max_acmg']}: {', '.join(t['genes'])}")

    print("\n" + "─" * 78)
    print("  💣  ГЕНЕТИЧЕСКИЕ МИНЫ")
    print("─" * 78)
    for m in report["mines"]:
        sev = "🔴 CRITICAL" if m["severity"] == "critical" else "🟠 HIGH"
        print(f"  {sev}  {m['combination']}")
        print(f"      → {m['effect'][:110]}…")

    print("\n" + "─" * 78)
    print("  🕸  ГРАФ УПОМИНАНИЙ")
    print("─" * 78)
    for gene, refs in report["gene_graph"].items():
        if refs:
            print(f"  {gene:10} → {', '.join(refs)}")

    print("\n" + "─" * 78)
    print("  🗺  КАРТА ГРУПП (средний риск по группе)")
    print("─" * 78)
    for g in report["group_map"]:
        bar = "█" * int(g["avg_max_risk"] * 3)
        print(f"  {g['group'][:50]:50} {bar}")
        print(f"      генов={g['genes_count']}  "
              f"avg_risk={g['avg_max_risk']}  max_risk={g['max_risk_overall']}  "
              f"max_acmg={g['max_acmg_overall']}")

    print("\n" + "─" * 78)
    print("  🕳  ПРОБЕЛЫ В БАЗЕ")
    print("─" * 78)
    if not report["gaps"]:
        print("  — пробелов нет")
    for gap in report["gaps"]:
        print(f"  {gap['gene']:15} ({gap['group'][:35]})")
        print(f"      → {', '.join(gap['issues'])}")

    print("\n" + "─" * 78)
    print("  📚  ТОП-25 ТЕРМИНОВ (общий)")
    print("─" * 78)
    for i, (w, c) in enumerate(report["lexical_density"], 1):
        print(f"  {i:2}. {w:28} {c}")

    print("\n" + "─" * 78)
    print("  🔤  КЛЮЧЕВЫЕ ТЕРМИНЫ ПО ГРУППАМ")
    print("─" * 78)
    for grp, terms in report["group_terms"].items():
        print(f"\n  ▸ {grp}")
        print("    " + ", ".join(f"{w}({c})" for w, c in terms[:10]))

    print("\n" + "=" * 78)


# ---------- 13. Markdown ----------

def save_markdown(report: dict, path: str):
    L = ["# Анализ базы знаний по генетике (v3)", ""]
    s = report["summary"]
    L.append(f"**Групп:** {s['groups']}  ")
    L.append(f"**Генов:** {s['genes_total']}  ")
    L.append("")
    L.append("## 🔥 Рейтинг опасности")
    L.append("")
    L.append("| # | Ген | Score | ACMG | max_risk | risk_sum |")
    L.append("|---|---|---|---|---|---|")
    for i, r in enumerate(report["toxicity_ranking"], 1):
        L.append(f"| {i} | {r['gene']} | {r['score']:.1f} | "
                 f"{r['max_acmg']} | {r['max_risk']} | {r['risk_sum']} |")
    L.append("")
    L.append("## 👯 Гены-близнецы")
    L.append("")
    for t in report["twins"]:
        p = t["profile"]
        L.append(f"- risk={p['max_risk']}, ACMG={p['max_acmg']}: {', '.join(t['genes'])}")
    L.append("")
    L.append("## 💣 Генетические мины")
    L.append("")
    for m in report["mines"]:
        L.append(f"### {m['combination']}")
        L.append(f"*Группа:* {m['group']}  ")
        L.append(f"*Уровень:* `{m['severity']}`  ")
        L.append("")
        L.append(m["effect"])
        L.append("")
    L.append("## 🕸 Граф упоминаний")
    L.append("")
    for gene, refs in report["gene_graph"].items():
        if refs:
            L.append(f"- **{gene}** → {', '.join(refs)}")
    L.append("")
    L.append("## 🗺 Карта групп")
    L.append("")
    L.append("| Группа | Генов | avg_risk | max_risk | max_ACMG |")
    L.append("|---|---|---|---|---|")
    for g in report["group_map"]:
        L.append(f"| {g['group']} | {g['genes_count']} | "
                 f"{g['avg_max_risk']} | {g['max_risk_overall']} | {g['max_acmg_overall']} |")
    L.append("")
    L.append("## 🕳 Пробелы в базе")
    L.append("")
    for gap in report["gaps"]:
        L.append(f"- **{gap['gene']}** ({gap['group']}): {', '.join(gap['issues'])}")
    L.append("")
    L.append("## 📚 Топ-25 терминов")
    L.append("")
    for i, (w, c) in enumerate(report["lexical_density"], 1):
        L.append(f"{i}. `{w}` — {c}")
    L.append("")
    L.append("## 🔤 Ключевые термины по группам")
    L.append("")
    for grp, terms in report["group_terms"].items():
        L.append(f"**{grp}**")
        L.append("")
        L.append(", ".join(f"`{w}` ({c})" for w, c in terms))
        L.append("")
    Path(path).write_text("\n".join(L), encoding="utf-8")


# ---------- main ----------

def main():
    print("Загрузка базы знаний…")
    base = load_base(SRC)
    print("Анализ…\n")
    report = build_report(base)
    print_report(report)

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    save_markdown(report, OUT_MD)

    print(f"\n💾 JSON: {OUT_JSON}")
    print(f"💾 Markdown: {OUT_MD}")


if __name__ == "__main__":
    main()