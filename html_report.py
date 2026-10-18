"""
html_report.py — генерация HTML-отчёта по данным patient_report.json (v13).

Ключевые отличия от v12:
- Блок фармакогенетики показывает ТОЛЬКО аннотации, релевантные пациенту.
- Если совпадений нет — выводится честное сообщение:
  "Нет данных для вашего генотипа. Изучено N ассоциаций: <список генотипов>".
- Убрана колонка "Генотип в исследовании" (врачу не нужна).
- Совпадения помечены: ✅ exact, ◐ allele.
"""

import html
from datetime import datetime
from pathlib import Path


# ---------------- Цвета по ACMG ----------------

ACMG_COLORS = {
    "pathogenic": ("#dc2626", "#fee2e2"),
    "risk factor": ("#ea580c", "#ffedd5"),
    "likely": ("#ca8a04", "#fef9c3"),
    "trait": ("#ca8a04", "#fef9c3"),
    "benign": ("#16a34a", "#dcfce7"),
    "normal": ("#16a34a", "#dcfce7"),
}


def _acmg_color(acmg_text: str):
    if not acmg_text:
        return ("#64748b", "#f1f5f9")
    t = acmg_text.lower()
    for key, colors in ACMG_COLORS.items():
        if key in t:
            return colors
    return ("#64748b", "#f1f5f9")


def _esc(s) -> str:
    return html.escape(str(s)) if s is not None else ""


def _pick_risk(row: dict) -> str:
    for k, v in row.items():
        kl = k.lower()
        if 'риск' in kl or 'профиль' in kl or 'фенотип' in kl:
            return v
    return ""


# ---------------- Фармакогенетика (v13) ----------------

def _render_pgx_block(pgx_annotations: list, no_match_info: dict = None) -> str:
    """
    Блок фармакогенетики в карточке гена.

    - Если есть совпадения — рисуем таблицу.
    - Если совпадений нет, но в базе есть аннотации — честное сообщение.
    - Если база пуста — блок не рисуем.
    """
    # Случай 1: нет совпадений, но в базе есть аннотации
    if not pgx_annotations:
        if no_match_info and no_match_info.get("total_annotations", 0) > 0:
            patient_gts = ", ".join(no_match_info.get("patient_genotypes", [])) or "—"
            base_gts = ", ".join(no_match_info.get("genotypes_in_base", [])[:25])
            return f"""
            <div class="pgx-block">
                <h4>💊 Фармакогенетика</h4>
                <div class="pgx-no-match">
                    <div class="pgx-no-match-title">Нет данных для вашего генотипа</div>
                    <div class="pgx-no-match-text">
                        В базе есть <b>{no_match_info['total_annotations']}</b> клинических
                        ассоциаций по этому гену, но ни одна не относится к вашему
                        генотипу <b>{_esc(patient_gts)}</b>.
                    </div>
                    <div class="pgx-no-match-sub">
                        Изученные генотипы в базе:
                        <span class="pgx-gt">{_esc(base_gts) or "—"}</span>
                    </div>
                </div>
            </div>
            """
        return ""

    # Случай 2: есть совпадения — рисуем таблицу
    PHENO_COLORS = {
        "toxicity": ("#dc2626", "#fee2e2"),
        "efficacy": ("#2563eb", "#dbeafe"),
        "metabolism/pk": ("#ca8a04", "#fef9c3"),
        "dosage": ("#7c3aed", "#ede9fe"),
        "other": ("#64748b", "#f1f5f9"),
    }

    exact_count = sum(1 for a in pgx_annotations if a.get("match_kind") == "exact")
    allele_count = sum(1 for a in pgx_annotations if a.get("match_kind") == "allele")

    counter_parts = []
    if exact_count:
        counter_parts.append(f"✅ точных: {exact_count}")
    if allele_count:
        counter_parts.append(f"◐ по аллели: {allele_count}")
    counter_text = " · ".join(counter_parts)

    rows_html = []
    for a in pgx_annotations:
        pheno = (a.get("phenotype") or "Other").lower()
        fg, bg = PHENO_COLORS.get(pheno, PHENO_COLORS["other"])
        pheno_label = a.get("phenotype") or "Other"

        kind = a.get("match_kind")
        if kind == "exact":
            match_icon = "✅"
            row_class = "pgx-row-exact"
        elif kind == "allele":
            match_icon = "◐"
            row_class = "pgx-row-allele"
        else:
            match_icon = ""
            row_class = ""

        matched_gts = ", ".join(a.get("matched_genotypes") or []) or "—"

        rows_html.append(f"""
            <tr class="{row_class}">
                <td class="pgx-match-col">{match_icon}</td>
                <td class="pgx-gt">{_esc(matched_gts)}</td>
                <td><span class="pgx-badge" style="color:{fg};background:{bg};">{_esc(pheno_label)}</span></td>
                <td><b>{_esc(a.get('drug', '—'))}</b></td>
                <td>{_esc(a.get('association', ''))}</td>
                <td class="pgx-pval">{_esc(a.get('pvalue', '—'))}</td>
            </tr>
        """)

    return f"""
        <div class="pgx-block">
            <h4>💊 Фармакогенетика
                <span class="pgx-count">({len(pgx_annotations)} — только ваши)</span>
                <span class="pgx-counter">{counter_text}</span>
            </h4>
            <div class="pgx-table-wrap">
                <table class="pgx-table">
                    <thead>
                        <tr>
                            <th></th>
                            <th>Ваш генотип</th>
                            <th>Категория</th>
                            <th>Препарат</th>
                            <th>Ассоциация</th>
                            <th>P-value</th>
                        </tr>
                    </thead>
                    <tbody>
                        {''.join(rows_html)}
                    </tbody>
                </table>
            </div>
        </div>
    """


# ---------------- Карточка гена ----------------

def _gene_card(result: dict, status_kind: str) -> str:
    gene = _esc(result["gene"])
    group = _esc(result.get("group", ""))
    patient_result = _esc(result.get("patient_result", ""))
    comment = _esc(result.get("patient_comment", ""))
    recs = result.get("recommendations", [])

    pgx_block = _render_pgx_block(
        result.get("pgx_annotations", []),
        result.get("pgx_no_match_info"),
    )

    if status_kind == "matched":
        matches = result.get("matches", [])
        cards_inner = ""
        for m in matches:
            row = m["full_row"]
            gt = _esc(m["genotype"])
            source = _esc(m.get("source_part", ""))
            risk = _esc(_pick_risk(row))
            acmg = row.get("ACMG", "")
            fg, bg = _acmg_color(acmg)
            acmg_badge = (
                f'<span class="badge" style="color:{fg};background:{bg};">'
                f'{_esc(acmg) or "—"}</span>'
            )
            row_items = "".join(
                f'<li><b>{_esc(k)}:</b> {_esc(v)}</li>'
                for k, v in row.items() if v
            )
            cards_inner += f"""
                <div class="match">
                    <div class="match-head">
                        <span class="genotype">{gt}</span>
                        <span class="source">← {source}</span>
                        {acmg_badge}
                    </div>
                    <ul class="row-details">{row_items}</ul>
                </div>
            """

        recs_html = ""
        if recs:
            recs_html = "<div class='recs'><h4>Рекомендации из базы</h4><ul>" + \
                "".join(f"<li>{_esc(r)}</li>" for r in recs) + "</ul></div>"

        return f"""
        <div class="card matched">
            <div class="card-head">
                <div>
                    <div class="gene-name">{gene}</div>
                    <div class="gene-group">{group}</div>
                </div>
                <span class="status-icon">✅</span>
            </div>
            <div class="patient-line"><b>Результат:</b> {patient_result}</div>
            {f'<div class="patient-line comment">{comment}</div>' if comment else ''}
            {cards_inner}
            {pgx_block}
            {recs_html}
        </div>
        """

    if status_kind == "no_table":
        note = _esc(result.get("note", ""))
        recs_html = ""
        if recs:
            recs_html = "<div class='recs'><h4>Общие рекомендации</h4><ul>" + \
                "".join(f"<li>{_esc(r)}</li>" for r in recs) + "</ul></div>"
        return f"""
        <div class="card no-table">
            <div class="card-head">
                <div>
                    <div class="gene-name">{gene}</div>
                    <div class="gene-group">{group}</div>
                </div>
                <span class="status-icon">🟡</span>
            </div>
            <div class="patient-line"><b>Результат:</b> {patient_result}</div>
            {f'<div class="patient-line comment">{comment}</div>' if comment else ''}
            {f'<div class="note">{note}</div>' if note else ''}
            {pgx_block}
            {recs_html}
        </div>
        """

    # no_genotype_match
    note = _esc(result.get("note", ""))
    return f"""
    <div class="card no-match">
        <div class="card-head">
            <div>
                <div class="gene-name">{gene}</div>
                <div class="gene-group">{group}</div>
            </div>
            <span class="status-icon">⚠️</span>
        </div>
        <div class="patient-line"><b>Результат:</b> {patient_result}</div>
        {f'<div class="note">{note}</div>' if note else ''}
        {pgx_block}
    </div>
    """


# ---------------- Полный HTML ----------------

def generate_html_report(rep: dict, output_path: str):
    """rep — словарь одного отчёта (как в reports/*_report.json)."""
    stats = rep.get("stats", {})
    results = rep.get("results", [])

    matched = [r for r in results if r.get("status") == "matched"]
    no_table = [r for r in results if r.get("status") == "no_table_in_base"]
    no_match = [r for r in results if r.get("status") == "no_genotype_match"]
    not_in_base = [r for r in results if r.get("status") == "not_in_knowledge_base"]

    matched_html = "".join(_gene_card(r, "matched") for r in matched)
    no_table_html = "".join(_gene_card(r, "no_table") for r in no_table)
    no_match_html = "".join(_gene_card(r, "no_match") for r in no_match)

    not_in_base_html = ""
    if not_in_base:
        items = "".join(
            f"<li><b>{_esc(r['gene'])}</b> — {_esc(r.get('patient_result', ''))}</li>"
            for r in not_in_base
        )
        not_in_base_html = f"""
        <section>
            <h2>❌ Гены, отсутствующие в базе знаний ({len(not_in_base)})</h2>
            <div class="not-in-base">
                <p class="hint">Эти гены есть в вашем отчёте, но их нет в текущей базе знаний.</p>
                <ul>{items}</ul>
            </div>
        </section>
        """

    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    file_name = _esc(rep.get("file", "отчёт"))

    # Статистика фармакогенетики
    total_pgx = sum(len(r.get("pgx_annotations", [])) for r in results)
    total_pgx_exact = sum(
        sum(1 for a in r.get("pgx_annotations", []) if a.get("match_kind") == "exact")
        for r in results
    )
    genes_with_no_data = sum(
        1 for r in results
        if not r.get("pgx_annotations") and r.get("pgx_no_match_info")
    )

    html_doc = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Генетический отчёт — {file_name}</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
    background: #f8fafc; color: #1e293b;
    margin: 0; padding: 24px;
    line-height: 1.55;
  }}
  .container {{ max-width: 1100px; margin: 0 auto; }}

  header {{
    background: linear-gradient(135deg, #1e40af, #3b82f6);
    color: white; padding: 28px 32px; border-radius: 14px;
    margin-bottom: 24px;
    box-shadow: 0 4px 16px rgba(30, 64, 175, 0.25);
  }}
  header h1 {{ margin: 0 0 6px; font-size: 24px; }}
  header .file {{ opacity: 0.85; font-size: 14px; }}
  header .date {{ opacity: 0.7; font-size: 13px; margin-top: 4px; }}

  .summary {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 12px; margin-bottom: 28px;
  }}
  .summary .stat {{
    background: white; padding: 14px 18px; border-radius: 10px;
    border: 1px solid #e2e8f0;
  }}
  .summary .stat .num {{ font-size: 26px; font-weight: 700; }}
  .summary .stat .label {{ font-size: 13px; color: #64748b; }}
  .stat.green .num {{ color: #16a34a; }}
  .stat.yellow .num {{ color: #ca8a04; }}
  .stat.orange .num {{ color: #ea580c; }}
  .stat.gray .num {{ color: #64748b; }}
  .stat.blue .num {{ color: #2563eb; }}
  .stat.teal .num {{ color: #0d9488; }}

  h2 {{
    font-size: 19px; margin: 32px 0 14px;
    padding-bottom: 8px; border-bottom: 2px solid #e2e8f0;
  }}

  .card {{
    background: white; border-radius: 12px; padding: 18px 22px;
    margin-bottom: 14px; border-left: 5px solid #cbd5e1;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
  }}
  .card.matched {{ border-left-color: #16a34a; }}
  .card.no-table {{ border-left-color: #ca8a04; }}
  .card.no-match {{ border-left-color: #94a3b8; }}

  .card-head {{
    display: flex; justify-content: space-between; align-items: flex-start;
    margin-bottom: 10px;
  }}
  .gene-name {{ font-size: 18px; font-weight: 700; color: #0f172a; }}
  .gene-group {{ font-size: 12px; color: #94a3b8; margin-top: 2px; }}
  .status-icon {{ font-size: 20px; }}

  .patient-line {{
    background: #f1f5f9; padding: 8px 12px; border-radius: 7px;
    margin-bottom: 10px; font-size: 14px;
  }}
  .patient-line.comment {{ font-style: italic; color: #475569; }}

  .match {{
    border-top: 1px dashed #e2e8f0;
    padding-top: 12px; margin-top: 10px;
  }}
  .match-head {{
    display: flex; flex-wrap: wrap; gap: 10px; align-items: center;
    margin-bottom: 8px;
  }}
  .genotype {{
    background: #eef2ff; color: #3730a3;
    padding: 3px 10px; border-radius: 6px;
    font-family: ui-monospace, Menlo, monospace; font-weight: 600;
  }}
  .source {{ color: #64748b; font-size: 13px; }}
  .badge {{
    padding: 3px 10px; border-radius: 6px;
    font-size: 12px; font-weight: 600;
  }}

  .row-details {{
    list-style: none; padding: 0; margin: 6px 0 0;
    font-size: 14px;
  }}
  .row-details li {{
    padding: 4px 0; border-bottom: 1px solid #f1f5f9;
  }}
  .row-details li:last-child {{ border-bottom: none; }}
  .row-details b {{ color: #334155; }}

  .recs {{ margin-top: 12px; }}
  .recs h4 {{ margin: 0 0 6px; font-size: 14px; color: #0f172a; }}
  .recs ul {{ padding-left: 18px; margin: 0; font-size: 14px; }}
  .recs ul li {{ padding: 3px 0; }}

  .note {{
    color: #64748b; font-size: 13px;
    background: #f8fafc; padding: 8px 12px; border-radius: 6px;
    margin-top: 8px;
  }}

  .not-in-base {{
    background: white; border-radius: 10px; padding: 16px 20px;
    border: 1px dashed #cbd5e1;
  }}
  .not-in-base .hint {{ color: #64748b; font-size: 13px; margin: 0 0 10px; }}
  .not-in-base ul {{ padding-left: 20px; margin: 0; font-size: 14px; }}
  .not-in-base li {{ padding: 2px 0; }}

  /* ----- Фармакогенетика ----- */
  .pgx-block {{
    margin-top: 16px;
    border-top: 2px solid #e2e8f0;
    padding-top: 12px;
  }}
  .pgx-block h4 {{
    font-size: 14px;
    margin: 0 0 10px;
    color: #0f172a;
  }}
  .pgx-count {{
    font-weight: 400;
    color: #64748b;
  }}
  .pgx-counter {{
    font-weight: 600;
    color: #16a34a;
    margin-left: 8px;
    font-size: 12px;
  }}
  .pgx-table-wrap {{
    overflow-x: auto;
  }}
  .pgx-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 12.5px;
  }}
  .pgx-table th {{
    text-align: left;
    padding: 6px 8px;
    background: #f8fafc;
    border-bottom: 1px solid #e2e8f0;
    font-weight: 600;
    color: #475569;
    font-size: 11.5px;
    text-transform: uppercase;
    letter-spacing: 0.3px;
  }}
  .pgx-table td {{
    padding: 6px 8px;
    border-bottom: 1px solid #f1f5f9;
    vertical-align: top;
  }}
  .pgx-match-col {{
    width: 28px;
    text-align: center;
    font-size: 14px;
  }}
  .pgx-row-exact {{
    background: #f0fdf4;
    border-left: 3px solid #16a34a;
  }}
  .pgx-row-exact td:first-child {{
    color: #16a34a;
    font-weight: 700;
  }}
  .pgx-row-allele {{
    background: #fefce8;
    border-left: 3px solid #ca8a04;
  }}
  .pgx-row-allele td:first-child {{
    color: #ca8a04;
    font-weight: 700;
  }}
  .pgx-badge {{
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
    white-space: nowrap;
    display: inline-block;
  }}
  .pgx-gt {{
    font-family: ui-monospace, Menlo, monospace;
    font-weight: 600;
    color: #0f172a;
    white-space: nowrap;
    font-size: 12px;
  }}
  .pgx-pval {{
    font-family: ui-monospace, Menlo, monospace;
    color: #64748b;
    white-space: nowrap;
  }}

  /* Честное "нет данных" */
  .pgx-no-match {{
    background: #f8fafc;
    border: 1px dashed #cbd5e1;
    border-radius: 8px;
    padding: 12px 16px;
    font-size: 13px;
  }}
  .pgx-no-match-title {{
    font-weight: 700;
    color: #475569;
    margin-bottom: 6px;
  }}
  .pgx-no-match-text {{
    color: #64748b;
    margin-bottom: 4px;
  }}
  .pgx-no-match-sub {{
    color: #94a3b8;
    font-size: 12px;
    margin-top: 8px;
    line-height: 1.5;
  }}

  footer {{
    margin-top: 40px; padding: 20px;
    text-align: center; color: #94a3b8; font-size: 12px;
  }}

  .print-btn {{
    position: fixed; bottom: 20px; right: 20px;
    background: #1e40af; color: white; border: none;
    padding: 12px 20px; border-radius: 10px;
    font-size: 14px; font-weight: 600; cursor: pointer;
    box-shadow: 0 4px 12px rgba(30,64,175,0.3);
  }}
  .print-btn:hover {{ background: #1d4ed8; }}

  @media print {{
    body {{ background: white; padding: 0; }}
    .print-btn {{ display: none; }}
    .card {{ box-shadow: none; border: 1px solid #e2e8f0; page-break-inside: avoid; }}
    header {{ box-shadow: none; }}
    .pgx-table-wrap {{ overflow: visible; }}
    .pgx-table {{ font-size: 11px; }}
  }}
</style>
</head>
<body>
<div class="container">

  <header>
    <h1>🧬 Генетический отчёт</h1>
    <div class="file">Источник: {file_name}</div>
    <div class="date">Сформировано: {now}</div>
  </header>

  <div class="summary">
    <div class="stat green">
      <div class="num">{stats.get('matched', 0)}</div>
      <div class="label">✅ Найдено в базе</div>
    </div>
    <div class="stat yellow">
      <div class="num">{stats.get('no_table_in_base', 0)}</div>
      <div class="label">🟡 Нет таблицы генотипов</div>
    </div>
    <div class="stat orange">
      <div class="num">{stats.get('no_genotype_match', 0)}</div>
      <div class="label">⚠️ Не сопоставлено</div>
    </div>
    <div class="stat gray">
      <div class="num">{stats.get('not_in_knowledge_base', 0)}</div>
      <div class="label">❌ Нет в базе знаний</div>
    </div>
    <div class="stat blue">
      <div class="num">{total_pgx}</div>
      <div class="label">💊 Фармакогенетика (ваших)</div>
    </div>
    <div class="stat teal">
      <div class="num">{genes_with_no_data}</div>
      <div class="label">🔍 Генов без данных</div>
    </div>
  </div>

  {f'<section><h2>✅ Интерпретированные гены ({len(matched)})</h2>{matched_html}</section>' if matched else ''}
  {f'<section><h2>🟡 Гены без таблиц генотипов ({len(no_table)})</h2>{no_table_html}</section>' if no_table else ''}
  {f'<section><h2>⚠️ Не сопоставленные генотипы ({len(no_match)})</h2>{no_match_html}</section>' if no_match else ''}
  {not_in_base_html}

  <footer>
    Отчёт сформирован автоматически. Не является медицинским диагнозом.<br>
    Для интерпретации обратитесь к врачу-генетику.
  </footer>
</div>

<button class="print-btn" onclick="window.print()">🖨 Печать / PDF</button>
</body>
</html>
"""

    Path(output_path).write_text(html_doc, encoding="utf-8")