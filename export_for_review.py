"""
export_for_review.py (v5 - Surgical Fix).
Умный экспорт: спасает слипшиеся гены (FUT2, VDR, GC, HFE, MTHFD1)
на основе анализа содержимого строк.
"""
import json
import pandas as pd
import re
from pathlib import Path

BASE_PATH = "parsed_knowledge_base_clean.json"
OUT_FILE = "GENOMIQ_Review_Export.xlsx"

def _strip_md(text):
    if not isinstance(text, str):
        return text
    return re.sub(r'\*\*(.+?)\*\*', r'\1', text).strip()

def extract_gene_name(header):
    m = re.match(r'^([A-Z0-9/ ]+?)\s*[—\-–]', header)
    if m:
        return m.group(1).strip()
    return header.split()[0] if header.split() else header

def get_clean_recommendations(gene):
    """Берет ТОЛЬКО практические рекомендации."""
    recs = []
    for sec in gene["sections"]:
        for b in sec.get("bullets", []):
            b_clean = _strip_md(b)
            if any(x in b_clean for x in ['et al.', 'PMID', 'PMCID', 'doi:', 'случай-контроль', 'Non-Pediatric Variant']):
                continue
            if 10 < len(b_clean) < 200:
                if any(word in b_clean.lower() for word in ['рекоменд', 'избег', 'контрол', 'принимать', 'снижен', 'мониторинг', 'доза', 'осторожно']):
                    recs.append(b_clean)

    seen = set()
    final_recs = [r for r in recs if not (r in seen or seen.add(r))]
    if not final_recs:
        return "Специфических рекомендаций нет"
    return " | ".join(final_recs)

def determine_real_gene(base_name, genotype, risk_text):
    """
    Хирургическая логика: если парсер склеил гены в Группе 3,
    мы определяем реальный ген по содержимому ячеек.
    """
    if base_name != 'FUT2':
        return base_name

    # Проверяем генотипы и риски для разлепления Группы 3
    if 'rs4588' in genotype or 'rs7041' in genotype:
        return 'GC'
    if 'C282Y' in genotype or 'H63D' in genotype:
        return 'HFE'
    if any(w in risk_text.lower() for w in ['перелом', 'остеопороз', 'алендронат', 'bmd']):
        return 'VDR'
    if any(w in risk_text.lower() for w in ['метотрексат', 'днт', 'фолат']):
        return 'MTHFD1'

    # Если не подошло ни под одно условие, значит это действительно FUT2
    return 'FUT2'

def main():
    print("Загрузка базы знаний...")
    with open(BASE_PATH, encoding="utf-8") as f:
        base = json.load(f)

    rows = []

    for group in base:
        group_name = group["group"]

        for gene in group["genes"]:
            base_gene_name = extract_gene_name(gene["header"])
            rec_text = get_clean_recommendations(gene)

            for sec in gene["sections"]:
                for tbl in sec["tables"]:
                    headers = tbl.get("headers", [])
                    if "Генотип" not in headers:
                        continue

                    for row in tbl["rows"]:
                        genotype = _strip_md(row.get("Генотип", ""))

                        if not genotype or genotype in ('—', '-', 'IM / PM', 'PM', 'UM') or len(genotype) < 2:
                            continue

                        phenotype = _strip_md(row.get("Фенотип", row.get("Функциональный эффект", "")))
                        risk = _strip_md(row.get("Клинический риск", row.get("Клинический риск СД2", row.get("Спортивный профиль", ""))))
                        acmg = _strip_md(row.get("ACMG", ""))

                        if not phenotype and not risk and not acmg:
                            continue

                        # Хирургическое определение гена
                        real_gene = determine_real_gene(base_gene_name, genotype, risk)
                        effect = phenotype if phenotype else risk

                        rows.append({
                            "Группа": group_name,
                            "Ген": real_gene,
                            "Генотип": genotype,
                            "Эффект / Фенотип": effect,
                            "Клинический риск": risk if risk != effect else "",
                            "ACMG": acmg,
                            "Рекомендации": rec_text
                        })

    df = pd.DataFrame(rows)
    df = df.drop_duplicates(subset=["Ген", "Генотип"])
    df = df.sort_values(by=["Группа", "Ген"])

    info_df = pd.DataFrame({
        "Информация": [
            "Проект: GENOMIQ — автоматизированная интерпретация генетических данных.",
            "Цель файла: научное рецензирование базы знаний.",
            "Что проверять: корректность сопоставления генотипов (колонка 3) с клиническими эффектами и рисками.",
            "Источники: OMIM, ClinVar, PharmGKB, CPIC.",
            "Примечание: Колонка 'Рекомендации' содержит только практические выжимки из гайдлайнов.",
            "Контакт: hello@tim-park.online"
        ]
    })

    print(f"Сохранение в {OUT_FILE}...")

    try:
        with pd.ExcelWriter(OUT_FILE, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name="Сводная таблица", index=False)
            info_df.to_excel(writer, sheet_name="О проекте", index=False)

            for sheetname in writer.sheets:
                worksheet = writer.sheets[sheetname]
                for column_cells in worksheet.columns:
                    length = max(len(str(cell.value or "")) for cell in column_cells)
                    worksheet.column_dimensions[column_cells[0].column_letter].width = min(length + 2, 50)
        print(f"✅ Готово! Всего строк: {len(df)}")
        print(f"Файл: {Path(OUT_FILE).resolve()}")
    except PermissionError:
        print("❌ ОШИБКА: Файл открыт в Excel. Закройте его и попробуйте снова.")

if __name__ == "__main__":
    main()