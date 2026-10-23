"""
export_for_review.py (v10 - Methodologically Correct).
Исправлено замечание эксперта: разделение систем оценки (ACMG vs CPIC vs GWAS).
"""
import json
import pandas as pd
import re
from pathlib import Path

BASE_PATH = "parsed_knowledge_base_clean.json"
OUT_FILE = "GENOMIQ_Review_Export.xlsx"

# Списки генов для правильной методологической маркировки
PHARMACOGENES = {
    'CYP2C9', 'CYP2C19', 'CYP2D6', 'CYP1A2', 'SLCO1B1', 'NAT2', 'DPYD', 'UGT1A1'
}

# Гены предрасположенности (мультифакторные / полигенные)
TRAIT_GENES = {
    'ACTN3', 'MCM6 / LCT', 'COMT', 'FTO', 'PPARG', 'APOE', 'MTHFD1'
}

def _strip_md(text):
    if not isinstance(text, str):
        return text
    return re.sub(r'\*\*(.+?)\*\*', r'\1', text).strip()

def extract_gene_name(header):
    m = re.match(r'^([A-Z0-9/ ]+?)\s*[—\-–]', header)
    if m:
        return m.group(1).strip()
    return header.split()[0] if header.split() else header

def determine_real_gene(base_name, genotype, risk_text):
    if base_name != 'FUT2':
        return base_name
    if 'rs4588' in genotype or 'rs7041' in genotype:
        return 'GC'
    if 'C282Y' in genotype or 'H63D' in genotype:
        return 'HFE'
    if any(w in risk_text.lower() for w in ['перелом', 'остеопороз', 'алендронат', 'bmd']):
        return 'VDR'
    if any(w in risk_text.lower() for w in ['метотрексат', 'днт', 'фолат']):
        return 'MTHFD1'
    return 'FUT2'

def get_rsid(real_gene, gene_data):
    HARDCODED_RSIDS = {
        'GC': 'rs4588 / rs7041',
        'HFE': 'rs1800562 / rs1799945',
        'VDR': 'rs2228570 / rs1544410',
        'MTHFD1': 'rs2236225',
        'FUT2': 'rs601338',
        'CYP2C9': 'rs1799853 / rs1057910',
        'CYP2C19': 'rs4244285 / rs4986893 / rs12248560',
        'CYP2D6': 'rs3892097 / rs1065852',
        'CYP1A2': 'rs762551',
        'SLCO1B1': 'rs4149056',
        'MTHFR': 'rs1801133 / rs1801131',
        'MTR': 'rs1805087',
        'MTRR': 'rs1801394',
        'NQO1': 'rs1800566',
        'CRP': 'rs1205',
        'F2': 'rs1799963 / rs5896',
        'F5': 'rs6025',
        'LPL': 'rs328 / rs1801177',
        'PCSK9': 'rs11591147 / rs505151',
        'ACTN3': 'rs1815739',
        'MCM6 / LCT': 'rs4988235',
        'COMT': 'rs4680',
        'FTO': 'rs9939609',
        'PPARG': 'rs1801282',
        'GSTM1': 'rs3754446',
        'GSTT1': 'rs4630',
        'GSTP1': 'rs1695 (A313G)',
        'NAT2': 'rs1799929 / rs1799930 / rs1799931',
        'TP53': 'rs1800371 / rs1042522',
        'AHCY': 'rs1057123',
        'CBS': 'rs5742905',
    }
    if real_gene in HARDCODED_RSIDS:
        return HARDCODED_RSIDS[real_gene]
    return "N/A"

def get_methodological_grade(real_gene, original_acmg):
    """
    Возвращает правильную систему оценки.
    Если ген не фармакоген и не предрасположенность, ставим ACMG.
    """
    if real_gene in PHARMACOGENES:
        return "CPIC / DPWG"
    elif real_gene in TRAIT_GENES:
        return "GWAS / Evidence-based"
    else:
        return "ACMG"

def fix_biological_errors(real_gene, effect, risk):
    if real_gene == 'CRP':
        effect = effect.replace('IL-6', 'СРБ')
        risk = risk.replace('IL-6', 'СРБ')
    if real_gene == 'NQO1':
        if 'Ala/Ala' in effect: effect = 'Норма (Ala/Ala)'
        if 'Ala/Val' in effect: effect = 'Гетерозигота (Ala/Val)'
        if 'Val/Val' in effect: effect = 'Гомозигота (Val/Val)'
    return effect, risk

def get_clean_recommendations(gene):
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
    return " | ".join(final_recs) if final_recs else "Специфических рекомендаций нет"

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

                        real_gene = determine_real_gene(base_gene_name, genotype, risk)

                        if real_gene == 'CRP' and '*07:01' in genotype:
                            continue

                        effect, risk = fix_biological_errors(real_gene, phenotype, risk)
                        if not effect:
                            effect = "Норма" if "Benign" in acmg else "Гетерозигота" if "Risk" in acmg else risk

                        rsid = get_rsid(real_gene, gene)
                        # Применяем методологическую правку
                        grade = get_methodological_grade(real_gene, acmg)

                        rows.append({
                            "Группа": group_name,
                            "Ген": real_gene,
                            "rsID": rsid,
                            "Генотип": genotype,
                            "Эффект / Фенотип": effect,
                            "Клинический риск": risk if risk != effect else "",
                            "Система оценки": grade, # <--- Новое название колонки
                            "Рекомендации": rec_text
                        })

    df = pd.DataFrame(rows)

    df['norm_genotype'] = df['Генотип'].str.extract(r'^([A-Za-z\*\/]+)')[0]
    df['len'] = df['Эффект / Фенотип'].str.len() + df['Клинический риск'].str.len()

    df = df.sort_values('len', ascending=False)
    df = df.drop_duplicates(subset=["Ген", "norm_genotype"]).drop(columns=['len', 'norm_genotype'])

    df = df.sort_values(by=["Группа", "Ген", "Генотип"])

    info_df = pd.DataFrame({
        "Информация": [
            "Проект: GENOMIQ — автоматизированная интерпретация генетических данных.",
            "Цель файла: научное рецензирование базы знаний.",
            "Что проверять: корректность сопоставления генотипов (колонка 4) с клиническими эффектами и рисками.",
            "Источники: OMIM, ClinVar, PharmGKB, CPIC, FDA, EMA.",
            "Колонка 'rsID' содержит идентификаторы SNP.",
            "ВАЖНО: Система оценки разделена методологически. Для моногенных болезней — ACMG. Для фармакогенов — CPIC/DPWG. Для предрасположенностей — GWAS.",
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
                    worksheet.column_dimensions[column_cells[0].column_letter].width = min(length + 2, 60)
        print(f"✅ Готово! Всего строк: {len(df)}")
        print(f"Файл: {Path(OUT_FILE).resolve()}")
    except PermissionError:
        print("❌ ОШИБКА: Файл открыт в Excel. Закройте его и попробуйте снова.")

if __name__ == "__main__":
    main()