"""
html_report.py — clean Apple-style medical HTML report.
Critical alerts, doctor's note, PHI-safe header, print-friendly CSS.
"""

import html
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from interpreter import BASE_PATH, build_doctors_note, collect_critical_alerts

# Strict 3-level clinical color system.
LEVEL_RED = "#ff3b30"
LEVEL_ORANGE = "#ff9500"
LEVEL_GRAY = "#86868b"


def _risk_level_from_text(*parts: str) -> str:
    blob = " ".join(str(p or "") for p in parts).lower()
    if any(
        w in blob
        for w in (
            "pathogenic",
            "противопоказ",
            "не активируется",
            "contraindic",
        )
    ):
        return "red"
    if any(
        w in blob
        for w in (
            "risk factor",
            "снижен",
            "доз",
            "миопат",
            "промежуточ",
            "intermediate",
        )
    ):
        return "orange"
    return "gray"


def _level_color(level: str) -> str:
    return {
        "red": LEVEL_RED,
        "orange": LEVEL_ORANGE,
        "gray": LEVEL_GRAY,
    }.get(level, LEVEL_GRAY)


def _acmg_color(acmg_text: str):
    level = _risk_level_from_text(acmg_text)
    c = _level_color(level)
    return (c, "#ffffff")


def _esc(s) -> str:
    return html.escape(str(s)) if s is not None else ""


_PHI_PATTERNS = [
    re.compile(r"(?i)\b(?:ф\.?\s*и\.?\s*о\.?|fio|имя|фамилия|patient\s*name)\s*[:=]\s*[^\n|;]+"),
    re.compile(r"(?i)\b(?:адрес|address|прописка)\s*[:=]\s*[^\n|;]+"),
    re.compile(r"(?i)\b(?:полис|policy|страх(?:овой)?(?:\s*номер)?|passport|паспорт)\s*[:=]\s*\S+"),
    re.compile(r"\b[А-ЯЁ][а-яё]{2,}(?:\s+[А-ЯЁ][а-яё]+){0,2}\s+[А-ЯЁ]\.\s*[А-ЯЁ]\.?"),
    re.compile(r"\bPID\|[^\n\r]+"),
]


def _redact_phi(text: str) -> str:
    if not text:
        return ""
    out = str(text)
    for pat in _PHI_PATTERNS:
        out = pat.sub("[REDACTED]", out)
    return out


def _looks_like_person_name(value: str) -> bool:
    v = (value or "").strip()
    if not v:
        return False
    if re.fullmatch(r"PAT[-_A-Z0-9]+", v, re.I):
        return False
    if re.search(r"\d", v):
        return False
    return bool(re.search(r"[А-ЯЁа-яёA-Za-z]{2,}\s+[А-ЯЁа-яёA-Za-z]{2,}", v))


def _safe_header_identity(rep: dict) -> tuple[str, str]:
    """Return (patient_id_or_empty, file_name) with names stripped."""
    raw_id = str(rep.get("patient_id") or rep.get("Patient_ID") or "").strip()
    if _looks_like_person_name(raw_id) or any(k in (raw_id.lower()) for k in ("имя", "иванов")):
        raw_id = "[REDACTED]"
    elif raw_id and _redact_phi(raw_id) == "[REDACTED]":
        raw_id = "[REDACTED]"
    file_name = str(rep.get("file") or "отчёт")
    if _looks_like_person_name(file_name):
        file_name = "[REDACTED]"
    return raw_id, file_name


def _acmg_text_for_result(r: dict) -> str:
    row = r.get("full_row") or {}
    if isinstance(row, dict) and row.get("ACMG"):
        return str(row.get("ACMG") or "")
    for m in r.get("matches") or []:
        fr = m.get("full_row") or {}
        if isinstance(fr, dict) and fr.get("ACMG"):
            return str(fr.get("ACMG") or "")
    return ""


def _render_critical_alerts(results: list) -> str:
    alerts = collect_critical_alerts(results)
    if not alerts:
        return ""
    if len(alerts) == 1:
        a = alerts[0]
        body = f"""
      <div class="critical-copy">
        <p class="critical-lead">⚠️ ВНИМАНИЕ: {_esc(a['text'])} ({_esc(a['gene'])})</p>
      </div>
        """
    else:
        items = "".join(
            f"<li><b>{_esc(a['gene'])}</b> — {_esc(a['text'])}</li>" for a in alerts
        )
        body = f"""
      <div class="critical-copy">
        <p class="critical-lead">⚠️ ВНИМАНИЕ</p>
        <ul>{items}</ul>
      </div>
        """
    return f"""
    <section class="critical-alerts" id="critical-alerts">
      {body}
    </section>
    """


def _render_doctors_note(results: list) -> str:
    note = build_doctors_note(results)
    if not note:
        return ""
    return f"""
    <section class="doctors-note" id="doctors-note">
      <h2>Рекомендуемый текст заключения</h2>
      <blockquote class="doctors-note-text">{_esc(note)}</blockquote>
    </section>
    """


def _pick_risk(row: dict) -> str:
    for k, v in row.items():
        kl = k.lower()
        if "риск" in kl or "профиль" in kl or "фенотип" in kl:
            return v
    return ""


def _is_genotype_label(key: str) -> bool:
    hl = (key or "").strip().lower()
    return hl in {"генотип", "genotype"} or hl.startswith("генотип")


def _display_row_value(key: str, value, patient_gt) -> str:
    """Генотип column: patient's matched diplotype, not the whole KB cell."""
    if patient_gt and _is_genotype_label(key):
        return patient_gt
    return value


_DETAIL_KEYS = {
    "генотип",
    "фенотип",
    "функция",
    "клинический риск",
    "acmg",
    "аллели",
    "phenotype",
    "genotype",
}


def _is_emphasis_field(key: str) -> bool:
    kl = (key or "").strip().lower()
    return "риск" in kl or "рекоменд" in kl


def _is_critical_risk(value: str) -> bool:
    low = (value or "").lower()
    return any(
        w in low
        for w in (
            "противопоказ",
            "высокий",
            "тромбоз",
            "кровотеч",
            "pathogenic",
            "не активируется",
        )
    )


def _render_detail_box(label: str, value: str, *, emphasis: bool = False, critical: bool = False) -> str:
    classes = ["detail-box"]
    if emphasis:
        classes.append("detail-emphasis")
    if critical:
        classes.append("detail-critical")
    return (
        f'<div class="{" ".join(classes)}">'
        f'<div class="detail-label">{_esc(label)}</div>'
        f'<div class="detail-value">{_esc(value)}</div>'
        f"</div>"
    )


def _render_row_detail_boxes(row: dict, patient_gt) -> str:
    boxes = []
    for k, v in row.items():
        if not v:
            continue
        kl = k.strip().lower()
        # Genotype & ACMG shown once elsewhere on the card.
        if _is_genotype_label(k) or kl == "acmg":
            continue
        display = _display_row_value(k, v, patient_gt)
        emphasis = _is_emphasis_field(k)
        critical = emphasis and _is_critical_risk(str(display))
        boxes.append(
            _render_detail_box(k, str(display), emphasis=emphasis, critical=critical)
        )
    if not boxes:
        return ""
    return '<div class="detail-grid">' + "".join(boxes) + "</div>"


def _filter_recs(recs: list) -> list:
    out = []
    for r in recs or []:
        t = str(r).strip()
        if not t or t == "Специфических рекомендаций нет":
            continue
        out.append(t)
    return out


def _render_recs_boxes(recs: list) -> str:
    recs = _filter_recs(recs)
    if not recs:
        return ""
    items = "".join(f"<li>{_esc(r)}</li>" for r in recs)
    return f"""
        <div class="recs detail-box detail-emphasis">
            <div class="detail-label">Рекомендации</div>
            <div class="detail-value"><ul class="recs-list">{items}</ul></div>
        </div>
    """


def _pgx_category_color(pheno: str) -> str:
    p = (pheno or "").lower()
    if "toxic" in p:
        return LEVEL_RED
    if "dosage" in p or "dose" in p:
        return LEVEL_ORANGE
    return LEVEL_GRAY


def _render_pgx_block(pgx_annotations: list, no_match_info: dict = None) -> str:
    if not pgx_annotations:
        if no_match_info and no_match_info.get("total_annotations", 0) > 0:
            patient_gts = ", ".join(no_match_info.get("patient_genotypes", [])) or "—"
            base_gts = ", ".join(no_match_info.get("genotypes_in_base", [])[:25])
            return f"""
            <div class="pgx-block">
                <h4>Фармакогенетика</h4>
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

    rows_html = []
    for a in pgx_annotations:
        pheno_label = a.get("phenotype") or "Other"
        fg = _pgx_category_color(pheno_label)
        matched_gts = ", ".join(a.get("matched_genotypes") or []) or "—"
        pval = a.get("pvalue") or "—"
        tip = (
            f"Генотип: {matched_gts} · P-value: {pval}"
            f" · Match: {a.get('match_kind') or '—'}"
        )
        assoc = a.get("association") or ""
        short_assoc = assoc if len(str(assoc)) <= 120 else str(assoc)[:117] + "…"
        rows_html.append(f"""
            <tr title="{_esc(tip)}">
                <td><b>{_esc(a.get('drug', '—'))}</b></td>
                <td><span class="pgx-badge" style="color:{fg};border-color:{fg};">{_esc(pheno_label)}</span></td>
                <td>{_esc(short_assoc)}</td>
            </tr>
        """)

    return f"""
        <div class="pgx-block">
            <h4>Фармакогенетика <span class="pgx-count">({len(pgx_annotations)})</span></h4>
            <div class="pgx-table-wrap">
                <table class="pgx-table">
                    <thead>
                        <tr>
                            <th>Препарат</th>
                            <th>Категория</th>
                            <th>Ассоциация</th>
                        </tr>
                    </thead>
                    <tbody>
                        {''.join(rows_html)}
                    </tbody>
                </table>
            </div>
        </div>
    """


def _render_live_db(live: Optional[dict]) -> str:
    if not live:
        return ""
    omim = live.get("omim") or []
    stats = live.get("clinvar_stats") or {}
    highlights = live.get("clinvar_highlights") or []
    pgx = live.get("clinpgx_annotations") or []
    labels = live.get("clinpgx_labels") or []

    omim_html = ""
    if omim:
        items = []
        for e in omim[:4]:
            title = _esc(e.get("title") or e.get("mim_number"))
            url = _esc(e.get("url") or f"https://omim.org/entry/{e.get('mim_number')}")
            ph = e.get("phenotypes") or []
            ph_txt = "; ".join(
                str(p.get("phenotype")) for p in ph[:4] if p.get("phenotype")
            )
            extra = f"<div class='live-sub'>{_esc(ph_txt)}</div>" if ph_txt else ""
            items.append(
                f"<li><a href='{url}' target='_blank' rel='noreferrer'>OMIM {_esc(e.get('mim_number'))}</a> — {title}{extra}</li>"
            )
        omim_html = "<h5>OMIM</h5><ul>" + "".join(items) + "</ul>"

    clinvar_html = ""
    if stats or highlights:
        bits = []
        if stats.get("total") is not None:
            bits.append(f"всего {stats.get('total', 0)}")
        if stats.get("pathogenic"):
            bits.append(f"P {stats['pathogenic']}")
        if stats.get("likely_pathogenic"):
            bits.append(f"LP {stats['likely_pathogenic']}")
        if stats.get("vus"):
            bits.append(f"VUS {stats['vus']}")
        if stats.get("conflicting"):
            bits.append(f"конфликт {stats['conflicting']}")
        rows = []
        for v in highlights[:6]:
            cls = _esc(v.get("classification") or "—")
            title = _esc(v.get("title") or v.get("variation_id"))
            url = _esc(v.get("url") or "")
            rsid = _esc(v.get("rsid") or "")
            link = f"<a href='{url}' target='_blank' rel='noreferrer'>{title}</a>" if url else title
            rows.append(f"<li><span class='live-cls'>{cls}</span> {link} {rsid}</li>")
        clinvar_html = (
            "<h5>ClinVar</h5>"
            + (f"<div class='live-sub'>{_esc(' · '.join(bits))}</div>" if bits else "")
            + ("<ul>" + "".join(rows) + "</ul>" if rows else "")
        )

    pgx_html = ""
    if pgx or labels:
        rows = []
        for a in pgx[:6]:
            level = _esc(a.get("level") or "—")
            drugs = _esc(a.get("drugs") or "—")
            types = _esc(a.get("types") or "")
            url = _esc(a.get("url") or "")
            variant = _esc(a.get("variant") or "")
            inner = f"<b>{level}</b> {drugs} <span class='live-sub'>{types} {variant}</span>"
            if url:
                inner = f"<a href='{url}' target='_blank' rel='noreferrer'>{inner}</a>"
            rows.append(f"<li>{inner}</li>")
        lab_bits = ", ".join(_esc(x.get("name")) for x in labels[:5] if x.get("name"))
        pgx_html = (
            "<h5>ClinPGx</h5>"
            + ("<ul>" + "".join(rows) + "</ul>" if rows else "")
            + (f"<div class='live-sub'>FDA labels: {lab_bits}</div>" if lab_bits else "")
        )

    if not (omim_html or clinvar_html or pgx_html):
        return ""
    synced = _esc(live.get("last_synced_at") or "")
    return f"""
        <div class="live-db">
            <h4>Внешние базы</h4>
            {f'<div class="live-sub">синхронизировано: {synced}</div>' if synced else ''}
            {omim_html}{clinvar_html}{pgx_html}
        </div>
    """


def _render_why_content(result: dict) -> str:
    why = result.get("why") or {}
    sentence = (why.get("sentence") or "").strip()
    if not sentence and not why.get("source") and not why.get("evidence"):
        return ""
    items = []
    if why.get("source"):
        items.append(f"<li><b>Source:</b> {_esc(why['source'])}</li>")
    if why.get("evidence"):
        items.append(f"<li><b>Evidence:</b> {_esc(why['evidence'])}</li>")
    if why.get("annotation"):
        items.append(f"<li><b>Annotation:</b> {_esc(why['annotation'])}</li>")
    body = f'<p class="why-sentence">{_esc(sentence)}</p>' if sentence else ""
    if items:
        body += "<ul>" + "".join(items) + "</ul>"
    return f'<div class="why-body">{body}</div>'


def _render_more_block(*parts: str) -> str:
    body = "".join(p for p in parts if p)
    if not body.strip():
        return ""
    return f"""
        <details class="more">
            <summary>Подробнее</summary>
            <div class="more-collapse">
                <div class="more-inner">{body}</div>
            </div>
        </details>
    """


def _card_risk_class(result: dict) -> str:
    acmg = _acmg_text_for_result(result)
    risk_bits = []
    for m in result.get("matches") or []:
        row = m.get("full_row") or {}
        if isinstance(row, dict):
            risk_bits.append(_pick_risk(row))
    level = _risk_level_from_text(acmg, *risk_bits)
    return f"risk-{level}"


def _gene_card(result: dict, status_kind: str) -> str:
    gene = _esc(result["gene"])
    group = _esc(result.get("group", ""))
    patient_result = _esc(_redact_phi(result.get("patient_result", "")))
    comment = _esc(_redact_phi(result.get("patient_comment", "")))
    recs_html = _render_recs_boxes(result.get("recommendations", []))
    why_content = _render_why_content(result)
    pgx_block = _render_pgx_block(
        result.get("pgx_annotations", []),
        result.get("pgx_no_match_info"),
    )
    live_block = _render_live_db(result.get("live_db"))
    more = _render_more_block(why_content, pgx_block, live_block)
    risk_class = _card_risk_class(result)
    comment_html = (
        f'<div class="card-comment">{comment}</div>' if comment else ""
    )

    status_label = {
        "matched": "Matched",
        "matched_annotation": "Annotation",
        "no_table": "No table",
        "no_match": "Unmatched",
    }.get(status_kind, "")

    if status_kind == "matched":
        matches = result.get("matches", [])
        cards_inner = ""
        for m in matches:
            row = m["full_row"]
            gt = _esc(m["genotype"])
            acmg = row.get("ACMG", "")
            fg, _bg = _acmg_color(acmg)
            acmg_badge = (
                f'<span class="badge" style="color:{fg};border-color:{fg};">'
                f'{_esc(acmg) or "—"}</span>'
                if acmg
                else ""
            )
            detail_boxes = _render_row_detail_boxes(row, m.get("genotype"))
            cards_inner += f"""
                <div class="match">
                    <div class="match-head">
                        <span class="genotype">{gt}</span>
                        {acmg_badge}
                    </div>
                    {detail_boxes}
                </div>
            """
        return f"""
        <article class="card matched {risk_class}" id="gene-{re.sub(r'[^A-Za-z0-9_-]+', '', str(result.get('gene') or ''))}">
            <div class="card-head">
                <div>
                    <h3 class="gene-name">{gene}</h3>
                    <div class="gene-group">{group}</div>
                </div>
                <span class="status-label">{status_label}</span>
            </div>
            {comment_html}
            {cards_inner}
            {recs_html}
            {more}
        </article>
        """

    genotype_chip = (
        f'<div class="match-head solo"><span class="genotype">{patient_result}</span></div>'
        if patient_result
        else ""
    )
    note = _esc(result.get("note", ""))
    note_html = f'<div class="note">{note}</div>' if note else ""

    return f"""
        <article class="card {status_kind.replace('_', '-')} {risk_class}" id="gene-{re.sub(r'[^A-Za-z0-9_-]+', '', str(result.get('gene') or ''))}">
            <div class="card-head">
                <div>
                    <h3 class="gene-name">{gene}</h3>
                    <div class="gene-group">{group}</div>
                </div>
                <span class="status-label">{status_label}</span>
            </div>
            {genotype_chip}
            {comment_html}
            {note_html}
            {recs_html}
            {more}
        </article>
    """


def _report_css() -> str:
    return """
  :root {
    --bg: #f5f5f7;
    --text: #1d1d1f;
    --muted: #86868b;
    --line: #d2d2d7;
    --accent: #1d1d1f;
    --danger: #ff3b30;
    --warn: #ff9500;
    --font-serif: "Times New Roman", Times, serif;
    --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  }
  * { box-sizing: border-box; }
  html { scroll-behavior: smooth; }
  body {
    margin: 0;
    padding: 0;
    font-family: var(--font-serif);
    font-size: 16px;
    line-height: 1.6;
    color: var(--text);
    background: var(--bg);
  }
  .container {
    max-width: 1400px;
    margin: 0 auto;
    padding: 48px 28px 80px;
  }

  .ui-sans,
  .detail-label,
  .status-label,
  .badge,
  .pgx-badge,
  .pgx-table,
  .pgx-table th,
  .pgx-table td,
  .meta-key,
  .summary .label,
  .more summary,
  .manual-field label,
  .manual-add-btn,
  .manual-analyze,
  .manual-cancel,
  .print-btn,
  .live-cls,
  .live-sub,
  .pgx-count,
  .pgx-counter {
    font-family: var(--font-sans) !important;
  }

  header.report-header {
    background: transparent;
    color: var(--text);
    padding: 8px 0 0;
    margin-bottom: 32px;
  }
  header.report-header h1 {
    font-size: 42px;
    font-weight: 500;
    letter-spacing: -0.02em;
    margin: 0 0 16px;
  }
  header .meta {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0;
    color: var(--muted);
    font-size: 13px;
    letter-spacing: 0.02em;
    background: #ffffff;
    border: 1px solid #e5e5ea;
    border-radius: 12px;
    padding: 10px 4px;
  }
  header .meta .meta-item {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 16px;
    color: var(--muted);
  }
  header .meta .meta-item + .meta-item {
    border-left: 1px solid #d2d2d7;
  }
  header .meta .meta-key {
    text-transform: uppercase;
    font-size: 10px;
    letter-spacing: 0.08em;
    color: #aeaeb2;
  }
  header .meta .meta-val {
    color: var(--text);
    font-weight: 700;
    font-family: var(--font-serif);
  }

  .summary {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 16px;
    margin: 0 0 40px;
  }
  @media (max-width: 700px) {
    .summary { grid-template-columns: 1fr; }
  }
  .summary .stat {
    background: #ffffff;
    border: 1px solid #e5e5ea;
    border-radius: 20px;
    padding: 22px 20px;
    text-align: left;
  }
  .summary .stat .num {
    font-size: 40px;
    font-weight: 700;
    color: var(--text);
    line-height: 1;
    letter-spacing: -0.03em;
  }
  .summary .stat .label {
    margin-top: 10px;
    font-size: 12px;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }
  .summary .stat.stat-attention .num { color: var(--danger); }

  h2 {
    font-size: 28px;
    font-weight: 500;
    letter-spacing: -0.01em;
    margin: 48px 0 20px;
    padding: 0;
    border: none;
    color: var(--text);
  }

  .critical-alerts {
    background: #000000;
    color: #ffffff;
    border: 1px solid #333;
    border-radius: 16px;
    padding: 24px 28px;
    margin: 0 0 36px;
  }
  .critical-copy { min-width: 0; }
  .critical-alerts .critical-lead {
    font-size: 18px;
    margin: 0 0 8px;
    letter-spacing: 0.01em;
  }
  .critical-alerts ul {
    margin: 8px 0 0;
    padding-left: 20px;
    font-size: 15px;
    line-height: 1.55;
  }
  .critical-alerts li { padding: 4px 0; color: #f5f5f7; }
  .critical-alerts b { color: #ffffff; font-weight: 700; }

  .gene-section h2 { margin-bottom: 20px; }
  .gene-cards {
    display: grid;
    grid-template-columns: 1fr;
    gap: 24px;
    align-items: stretch;
  }
  @media (min-width: 900px) {
    .gene-cards { grid-template-columns: 1fr 1fr; }
  }

  .card {
    background: #ffffff;
    border: 1px solid #e5e5ea;
    border-radius: 16px;
    border-left: 3px solid var(--line);
    padding: 28px 24px;
    margin: 0;
    height: 100%;
    display: flex;
    flex-direction: column;
    box-shadow: none;
  }
  .card.risk-red { border-left-color: var(--danger); }
  .card.risk-orange { border-left-color: var(--warn); }
  .card.risk-gray { border-left-color: var(--muted); }

  .card-head {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 16px;
    margin-bottom: 16px;
  }
  .gene-name {
    font-size: 32px;
    font-weight: 500;
    letter-spacing: -0.02em;
    margin: 0;
    color: var(--text);
  }
  .gene-group {
    margin-top: 6px;
    font-size: 13px;
    color: var(--muted);
  }
  .status-label {
    font-size: 11px;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--muted);
    border: 1px solid var(--line);
    border-radius: 980px;
    padding: 4px 12px;
    white-space: nowrap;
    background: #fbfbfd;
  }
  .card-comment {
    font-style: italic;
    color: var(--muted);
    font-size: 14px;
    margin: 0 0 12px;
  }

  .match { margin-top: 4px; }
  .match + .match {
    border-top: 1px solid #e5e5ea;
    padding-top: 16px;
    margin-top: 16px;
  }
  .match-head {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    align-items: center;
    margin-bottom: 12px;
  }
  .match-head.solo { margin-bottom: 14px; }
  .genotype {
    background: #f5f5f7;
    color: var(--text);
    border: 1px solid var(--line);
    padding: 6px 12px;
    border-radius: 10px;
    font-weight: 700;
    font-size: 16px;
  }
  .badge {
    padding: 3px 10px;
    border-radius: 980px;
    border: 1px solid var(--line);
    background: #fbfbfd;
    font-size: 12px;
    font-weight: 700;
  }
  .badge.badge-matched {
    color: var(--warn);
    border-color: var(--warn);
    background: rgba(255, 149, 0, 0.08);
  }

  .detail-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: 8px;
  }
  .detail-box {
    background: #f5f5f7;
    border: 1px solid #e5e5ea;
    border-radius: 10px;
    padding: 12px 16px;
  }
  .detail-box.detail-emphasis { border-left: 3px solid #1d1d1f; }
  .detail-box.detail-critical { border-left: 3px solid var(--danger); }
  .detail-label {
    font-size: 11px;
    font-weight: 500;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: #86868b;
    margin-bottom: 4px;
  }
  .detail-value {
    font-size: 15px;
    font-weight: 700;
    color: #1d1d1f;
    line-height: 1.45;
  }
  .recs-list {
    margin: 0;
    padding-left: 18px;
    font-weight: 700;
  }
  .recs-list li { padding: 3px 0; }
  .recs { margin-top: 14px; }

  .more {
    margin-top: auto;
    padding-top: 16px;
  }
  .more summary {
    cursor: pointer;
    list-style: none;
    display: inline-block;
    margin: 0;
    padding: 8px 16px;
    background: #1d1d1f;
    color: #ffffff;
    border-radius: 980px;
    font-size: 13px;
    font-weight: 500;
    user-select: none;
  }
  .more summary::-webkit-details-marker { display: none; }
  .more summary:hover,
  .more[open] summary { background: #424245; }
  .more-collapse {
    display: grid;
    grid-template-rows: 0fr;
    transition: grid-template-rows 0.28s ease;
  }
  .more[open] .more-collapse { grid-template-rows: 1fr; }
  .more-inner {
    overflow: hidden;
    min-height: 0;
  }
  .more[open] .more-inner { padding-top: 14px; }

  .why-body {
    padding: 14px 16px;
    background: #f5f5f7;
    border: 1px solid #e5e5ea;
    border-radius: 10px;
    font-size: 14px;
    color: var(--text);
    margin-bottom: 12px;
  }
  .why-sentence { margin: 0 0 10px; line-height: 1.55; font-weight: 700; }
  .why-body ul { padding-left: 18px; margin: 0; color: var(--muted); }
  .why-body li { padding: 3px 0; }

  .live-db h4, .pgx-block h4 {
    font-size: 16px;
    font-weight: 500;
    margin: 0 0 10px;
    color: var(--text);
  }
  .live-db ul {
    padding-left: 18px;
    margin: 0;
    font-size: 14px;
  }
  .live-db {
    margin-top: 12px;
    padding: 14px 0 0;
    border-top: 1px solid #e5e5ea;
  }
  .live-db h5 {
    margin: 12px 0 4px;
    font-size: 11px;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    font-family: var(--font-sans);
  }
  .live-db a { color: var(--text); text-decoration: underline; text-underline-offset: 2px; }
  .live-cls {
    display: inline-block;
    font-size: 11px;
    border: 1px solid var(--line);
    border-radius: 4px;
    padding: 1px 6px;
    margin-right: 4px;
  }
  .live-sub { color: var(--muted); font-size: 13px; margin: 4px 0; }

  .note {
    color: var(--muted);
    font-size: 14px;
    margin-top: 8px;
  }

  .not-in-base {
    background: #ffffff;
    border: 1px solid #e5e5ea;
    border-radius: 16px;
    padding: 24px 28px;
  }
  .not-in-base .hint { color: var(--muted); font-size: 14px; margin: 0 0 12px; }
  .not-in-base ul { padding-left: 18px; margin: 0; font-size: 15px; }

  .pgx-block {
    margin-top: 12px;
    border-top: 1px solid #e5e5ea;
    padding-top: 14px;
  }
  .pgx-count, .pgx-counter {
    font-weight: 400;
    color: var(--muted);
    font-size: 13px;
  }
  .pgx-table-wrap { overflow-x: auto; }
  .pgx-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
  }
  .pgx-table th {
    text-align: left;
    padding: 10px 8px;
    background: transparent;
    border-bottom: 1px solid var(--line);
    font-weight: 500;
    color: var(--muted);
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .pgx-table td {
    padding: 10px 8px;
    border-bottom: 1px solid #ececef;
    vertical-align: top;
  }
  .pgx-badge {
    padding: 2px 8px;
    border-radius: 980px;
    border: 1px solid var(--line);
    font-size: 11px;
    font-weight: 700;
    background: #fbfbfd;
    display: inline-block;
  }
  .pgx-gt { font-weight: 700; white-space: nowrap; }
  .pgx-no-match {
    background: #f5f5f7;
    border: 1px solid #e5e5ea;
    border-radius: 10px;
    padding: 14px 16px;
    font-size: 14px;
  }
  .pgx-no-match-title { font-weight: 700; margin-bottom: 6px; }
  .pgx-no-match-text, .pgx-no-match-sub { color: var(--muted); }

  .doctors-note {
    background: transparent;
    border: none;
    border-radius: 0;
    padding: 8px 0 8px 24px;
    margin: 56px 0 24px;
    border-left: 2px solid #000;
  }
  .doctors-note h2 {
    margin: 0 0 16px;
    font-size: 24px;
  }
  .doctors-note-text {
    margin: 0;
    font-size: 18px;
    line-height: 1.7;
    color: var(--text);
    user-select: text;
    -webkit-user-select: text;
  }

  footer {
    margin-top: 48px;
    padding: 24px 0 0;
    border-top: 1px solid var(--line);
    text-align: center;
    color: var(--muted);
    font-size: 13px;
    line-height: 1.55;
  }

  .print-btn {
    position: fixed;
    bottom: 24px;
    right: 24px;
    background: #1d1d1f;
    color: #fff;
    border: none;
    padding: 6px 16px;
    border-radius: 980px;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
  }
  .print-btn:hover { background: #424245; }

  .manual-add-wrap {
    margin-top: 28px;
    display: flex;
    justify-content: center;
  }
  .manual-add-btn {
    background: #ffffff;
    color: #1d1d1f;
    border: 1px solid #d2d2d7;
    border-radius: 980px;
    padding: 10px 22px;
    font-size: 15px;
    font-weight: 500;
    cursor: pointer;
  }
  .manual-add-btn:hover {
    background: #fbfbfd;
    border-color: #aeaeb2;
  }

  .manual-modal {
    display: none;
    position: fixed;
    inset: 0;
    z-index: 1000;
    align-items: center;
    justify-content: center;
    padding: 24px;
    background: rgba(0, 0, 0, 0.36);
    backdrop-filter: blur(6px);
    -webkit-backdrop-filter: blur(6px);
  }
  .manual-modal.is-open { display: flex; }
  .manual-modal-panel {
    width: 100%;
    max-width: 420px;
    background: #ffffff;
    border: 1px solid #e5e5ea;
    border-radius: 18px;
    padding: 28px 26px 24px;
    box-shadow: 0 20px 50px rgba(0,0,0,0.18);
  }
  .manual-modal-panel h3 {
    margin: 0 0 6px;
    font-size: 22px;
    font-weight: 500;
    letter-spacing: -0.02em;
  }
  .manual-modal-sub {
    margin: 0 0 20px;
    font-size: 13px;
    color: var(--muted);
  }
  .manual-field { margin-bottom: 14px; }
  .manual-field label {
    display: block;
    font-size: 11px;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: #86868b;
    margin-bottom: 6px;
  }
  .manual-field input {
    width: 100%;
    padding: 11px 14px;
    border: 1px solid #d2d2d7;
    border-radius: 12px;
    background: #ffffff;
    color: var(--text);
    font-size: 16px;
    font-family: var(--font-serif);
    outline: none;
  }
  .manual-field input:focus {
    border-color: #1d1d1f;
    box-shadow: 0 0 0 3px rgba(29,29,31,0.08);
  }
  .manual-modal-actions {
    display: flex;
    gap: 10px;
    justify-content: flex-end;
    margin-top: 20px;
  }
  .manual-cancel {
    background: transparent;
    border: none;
    color: #86868b;
    font-size: 14px;
    cursor: pointer;
    padding: 10px 14px;
    border-radius: 980px;
  }
  .manual-cancel:hover { color: #1d1d1f; background: #f5f5f7; }
  .manual-analyze {
    background: #1d1d1f;
    color: #ffffff;
    border: none;
    border-radius: 980px;
    padding: 10px 20px;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
  }
  .manual-analyze:hover { background: #424245; }

  @media print {
    * { box-shadow: none !important; transform: none !important; }
    html { scroll-behavior: auto; }
    body {
      background: #fff !important;
      color: #000;
      padding: 0;
      font-size: 12pt;
    }
    .container { padding: 0; max-width: none; }
    header.report-header { border-bottom: 1px solid #000; color: #000; }
    .summary .stat, .card, .not-in-base, .genotype, .badge, .pgx-badge, .detail-box, .why-body {
      background: none !important;
      box-shadow: none !important;
    }
    .critical-alerts {
      background: #fff !important;
      color: #000 !important;
      border: 1px solid #000;
    }
    .critical-alerts li, .critical-alerts b, .critical-lead { color: #000 !important; }
    .print-btn, .manual-add-wrap, .manual-modal, .more summary { display: none !important; }
    .more-collapse, .more-inner { display: block !important; overflow: visible !important; }
    .more-inner { padding-top: 8px !important; }
    .critical-alerts, .card, .doctors-note {
      page-break-inside: avoid;
      break-inside: avoid;
    }
    thead { display: table-header-group; }
    .pgx-table th { background: none !important; }
    .pgx-table-wrap { overflow: visible; }
  }
"""




def _load_knowledge_base_embed() -> str:
    """Load KB JSON safe for embedding inside an HTML <script> tag."""
    path = Path(BASE_PATH)
    if not path.is_file():
        return "[]"
    raw = path.read_text(encoding="utf-8")
    # Validate + compact; escape '<' so "</script>" cannot break out.
    data = json.loads(raw)
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")


def _manual_gene_entry_ui(kb_json: Optional[str] = None) -> str:
    """Button + modal + client-side KB lookup for manual gene cards."""
    if kb_json is None:
        kb_json = _load_knowledge_base_embed()
    # Avoid f-string: KB JSON contains many '{' / '}' braces.
    template = r"""
  <div class="manual-add-wrap no-print">
    <button type="button" class="manual-add-btn" id="manual-add-open">
      ➕ Добавить ген вручную
    </button>
  </div>

  <div class="manual-modal no-print" id="manual-gene-modal" aria-hidden="true" role="dialog" aria-labelledby="manual-gene-title">
    <div class="manual-modal-panel" role="document">
      <h3 id="manual-gene-title">Добавить ген вручную</h3>
      <p class="manual-modal-sub">Поиск по встроенной базе знаний GenomIQ.</p>
      <form id="manual-gene-form" autocomplete="off">
        <div class="manual-field">
          <label for="manual-gene-name">Gene Name</label>
          <input id="manual-gene-name" name="gene" type="text" placeholder="VKORC1" required maxlength="64">
        </div>
        <div class="manual-field">
          <label for="manual-gene-gt">Genotype</label>
          <input id="manual-gene-gt" name="genotype" type="text" placeholder="CT или *1/*2" required maxlength="64">
        </div>
        <div class="manual-modal-actions">
          <button type="button" class="manual-cancel" id="manual-add-cancel">Отмена</button>
          <button type="submit" class="manual-analyze">Проанализировать</button>
        </div>
      </form>
    </div>
  </div>

  <script id="knowledge-base" type="application/json">__KNOWLEDGE_BASE_JSON__</script>
  <script>
  (function () {
    var modal = document.getElementById("manual-gene-modal");
    var openBtn = document.getElementById("manual-add-open");
    var cancelBtn = document.getElementById("manual-add-cancel");
    var form = document.getElementById("manual-gene-form");
    var nameInput = document.getElementById("manual-gene-name");
    var gtInput = document.getElementById("manual-gene-gt");
    var cards = document.getElementById("interpreted-gene-cards");
    var NON_GT = {
      "вариант": 1, "лекарство": 1, "эффект": 1, "уровень": 1,
      "препарат": 1, "guidance": 1, "источник": 1, "домен": 1,
      "rsid": 1, "изоформа": 1
    };

    function esc(s) {
      return String(s == null ? "" : s)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
    }

    function stripMd(s) {
      return String(s == null ? "" : s).replace(/\*\*(.+?)\*\*/g, "$1").trim();
    }

    function loadKb() {
      var el = document.getElementById("knowledge-base");
      if (!el) return [];
      try { return JSON.parse(el.textContent || "[]"); }
      catch (e) { return []; }
    }

    function geneSymbol(header) {
      var h = String(header || "").trim();
      var m = h.match(/^([A-Za-z0-9*\/\-]+)/);
      return (m ? m[1] : h).toUpperCase().replace(/\s+/g, "");
    }

    function findGene(kb, name) {
      var target = String(name || "").trim().toUpperCase().replace(/\s+/g, "");
      if (!target) return null;
      for (var i = 0; i < kb.length; i++) {
        var group = kb[i] || {};
        var genes = group.genes || [];
        for (var j = 0; j < genes.length; j++) {
          var gene = genes[j];
          var sym = geneSymbol(gene.header);
          if (sym === target || sym.indexOf(target) === 0 || target.indexOf(sym) === 0) {
            return { group: group.group || "", gene: gene };
          }
        }
      }
      return null;
    }

    function normalizeGt(gt) {
      if (!gt) return "";
      var s = String(gt).trim().replace(/\s*\(.*?\)/g, "").trim();
      if (s.charAt(0) === "*") return s.replace(/\s+/g, "").toLowerCase();
      s = s.replace(/\//g, "").replace(/\s+/g, "").replace(/\|/g, "").toLowerCase();
      if (s.length === 2 && /^[acgt]{2}$/.test(s)) {
        return s.split("").sort().join("");
      }
      return s;
    }

    function starParts(value) {
      return String(value || "").replace(/\s+/g, "").split("/").filter(function (p) {
        return p.charAt(0) === "*";
      });
    }

    function isStarOverlap(cn, rowNorm) {
      if (cn.indexOf("*") < 0 && rowNorm.indexOf("*") < 0) return false;
      var cParts = starParts(cn);
      if (!cParts.length) return cn === rowNorm;
      var cSet = {};
      cParts.forEach(function (p) { cSet[p] = 1; });
      var chunks = rowNorm.replace(/\s+/g, "").split(/[,;]/);
      for (var i = 0; i < chunks.length; i++) {
        var rChunk = starParts(chunks[i]);
        if (!rChunk.length) continue;
        var same = rChunk.length === cParts.length;
        for (var k = 0; k < rChunk.length && same; k++) {
          if (!cSet[rChunk[k]]) same = false;
        }
        if (same) {
          for (var t = 0; t < cParts.length; t++) {
            if (rChunk.indexOf(cParts[t]) < 0) { same = false; break; }
          }
        }
        if (same) return true;
      }
      var rParts = starParts(rowNorm);
      if (!rParts.length) return cn === rowNorm;
      if (cParts.length === 1 && cn.indexOf("/") < 0) return rParts.indexOf(cParts[0]) >= 0;
      if (rParts.length !== cParts.length) return false;
      for (var x = 0; x < cParts.length; x++) {
        if (rParts.indexOf(cParts[x]) < 0) return false;
      }
      return true;
    }

    function isGtCol(h) {
      var hl = String(h || "").trim().toLowerCase();
      return hl === "генотип" || hl === "аллели" || hl === "alleles" || hl === "genotype" ||
        hl.indexOf("генотип") === 0 || hl.indexOf("аллели") === 0;
    }

    function isGeneTable(headers) {
      var hasGt = false, hasDrug = false;
      for (var i = 0; i < headers.length; i++) {
        var h = String(headers[i] || "");
        if (isGtCol(h)) hasGt = true;
        if (NON_GT[h.trim().toLowerCase()]) hasDrug = true;
      }
      return hasGt && !hasDrug;
    }

    function rowGet(row, keys) {
      if (!row) return "";
      var map = {};
      Object.keys(row).forEach(function (k) { map[k.trim().toLowerCase()] = row[k]; });
      for (var i = 0; i < keys.length; i++) {
        if (map[keys[i]] != null && String(map[keys[i]]).trim()) return stripMd(String(map[keys[i]]));
      }
      for (var k in map) {
        for (var j = 0; j < keys.length; j++) {
          if (k.indexOf(keys[j]) >= 0 && map[k] != null && String(map[k]).trim()) {
            return stripMd(String(map[k]));
          }
        }
      }
      return "";
    }

    function phenotypeCodes(pheno) {
      var codes = {};
      var m;
      var re = /\b(IM|PM|NM|UM|RM|EM)\b/gi;
      while ((m = re.exec(pheno || "")) ) codes[m[1].toUpperCase()] = 1;
      var low = String(pheno || "").toLowerCase();
      if (low.indexOf("intermediate") >= 0 || low.indexOf("промежуточ") >= 0) codes.IM = 1;
      if (low.indexOf("poor metabol") >= 0 || low.indexOf("медленн") >= 0) codes.PM = 1;
      if (low.indexOf("normal metabol") >= 0 || low.indexOf("extensive") >= 0) codes.NM = 1;
      return codes;
    }

    function matchGenotype(gene, genotype) {
      var cn = normalizeGt(genotype);
      if (!cn || !gene) return null;
      var sections = gene.sections || [];
      for (var si = 0; si < sections.length; si++) {
        var tables = sections[si].tables || [];
        for (var ti = 0; ti < tables.length; ti++) {
          var tbl = tables[ti];
          var headers = tbl.headers || [];
          if (!isGeneTable(headers)) continue;
          var gtCols = headers.filter(isGtCol);
          var rows = tbl.rows || [];
          for (var ri = 0; ri < rows.length; ri++) {
            var row = rows[ri];
            for (var gi = 0; gi < gtCols.length; gi++) {
              var rowGt = String(row[gtCols[gi]] || "").trim();
              if (!rowGt) continue;
              var rowNorm = normalizeGt(rowGt);
              var starNorm = String(rowGt).replace(/\s+/g, "").toLowerCase();
              var matched = cn === rowNorm ||
                cn.replace(/\//g, "") === rowNorm.replace(/\//g, "") ||
                isStarOverlap(cn, starNorm) ||
                isStarOverlap(cn, rowNorm);
              if (matched) {
                var display = genotype;
                var parts = starParts(cn);
                if (parts.length >= 2) display = parts[0] + "/" + parts[1];
                else if (parts.length === 1) display = parts[0];
                return { row: row, displayGt: display, acmg: rowGet(row, ["acmg"]) };
              }
            }
          }
        }
      }
      return null;
    }

    function collectRecommendations(gene, phenotype, matchedRow) {
      var recs = [];
      var seen = {};
      function add(t) {
        t = stripMd(t);
        if (!t) return;
        var key = t.toLowerCase();
        if (seen[key]) return;
        seen[key] = 1;
        recs.push(t);
      }
      var fromRow = rowGet(matchedRow, ["рекомендации", "рекомендация", "recommendations"]);
      if (fromRow) add(fromRow);
      var codes = phenotypeCodes(phenotype);
      var sections = (gene && gene.sections) || [];
      for (var si = 0; si < sections.length; si++) {
        var tables = sections[si].tables || [];
        for (var ti = 0; ti < tables.length; ti++) {
          var tbl = tables[ti];
          var headers = tbl.headers || [];
          var recCol = null, gtCol = null, drugCol = null;
          for (var hi = 0; hi < headers.length; hi++) {
            var hl = String(headers[hi] || "").trim().toLowerCase();
            if (!recCol && (hl.indexOf("рекоменд") >= 0 || hl === "recommendation")) recCol = headers[hi];
            if (!gtCol && isGtCol(headers[hi])) gtCol = headers[hi];
            if (!drugCol && (hl === "препарат" || hl === "drug" || hl === "лекарство")) drugCol = headers[hi];
          }
          if (!recCol) continue;
          var rows = tbl.rows || [];
          for (var ri = 0; ri < rows.length; ri++) {
            var row = rows[ri];
            var ok = !gtCol;
            if (gtCol) {
              var cell = String(row[gtCol] || "").toUpperCase();
              ok = false;
              Object.keys(codes).forEach(function (c) {
                if (cell.indexOf(c) >= 0) ok = true;
              });
            }
            if (!ok) continue;
            var drug = drugCol ? stripMd(String(row[drugCol] || "")) : "";
            var rec = stripMd(String(row[recCol] || ""));
            if (!rec) continue;
            add(drug ? (drug + ": " + rec) : rec);
          }
        }
        var bullets = sections[si].bullets || [];
        for (var bi = 0; bi < bullets.length; bi++) {
          var b = stripMd(String(bullets[bi] || ""));
          if (/рекоменд|замен|избег|противопоказ|снизить|доз/i.test(b)) add(b);
        }
      }
      return recs;
    }

    function detailBox(label, value, critical) {
      if (!value) return "";
      var cls = "detail-box" + (/риск|рекоменд/i.test(label) ? " detail-emphasis" : "") +
        (critical ? " detail-critical" : "");
      return '<div class="' + cls + '"><div class="detail-label">' + esc(label) +
        '</div><div class="detail-value">' + esc(value) + '</div></div>';
    }

    function riskLevel(acmg, risk) {
      var blob = String(acmg || "") + " " + String(risk || "");
      blob = blob.toLowerCase();
      if (/pathogenic|противопоказ|не активируется|contraindic/.test(blob)) return "red";
      if (/risk factor|снижен|доз|миопат|промежуточ|intermediate/.test(blob)) return "orange";
      return "gray";
    }

    function levelColor(level) {
      return level === "red" ? "#ff3b30" : (level === "orange" ? "#ff9500" : "#86868b");
    }

    function buildMatchedCard(geneName, group, genotype, hit, gene) {
      var pheno = rowGet(hit.row, ["фенотип", "phenotype"]);
      var risk = rowGet(hit.row, ["клинический риск", "риск", "clinical risk"]);
      var func = rowGet(hit.row, ["функция", "function"]);
      var acmg = hit.acmg || rowGet(hit.row, ["acmg"]);
      var level = riskLevel(acmg, risk);
      var color = levelColor(level);
      var recs = collectRecommendations(gene, pheno, hit.row).filter(function (r) {
        return r && r !== "Специфических рекомендаций нет";
      });
      var recHtml = "";
      if (recs.length) {
        recHtml = '<div class="recs detail-box detail-emphasis"><div class="detail-label">Рекомендации</div>' +
          '<div class="detail-value"><ul class="recs-list">' +
          recs.map(function (r) { return "<li>" + esc(r) + "</li>"; }).join("") +
          "</ul></div></div>";
      }
      var critical = /противопоказ|высокий|тромбоз|кровотеч|pathogenic|не активируется/i.test(risk);
      var acmgBadge = acmg
        ? '<span class="badge" style="color:' + color + ';border-color:' + color + ';">' + esc(acmg) + "</span>"
        : "";
      var more = '<details class="more"><summary>Подробнее</summary><div class="more-collapse"><div class="more-inner">' +
        '<div class="note">Источник: knowledge base (ручной ввод)</div>' +
        '</div></div></details>';
      return (
        '<article class="card matched manual-entry risk-' + level + '">' +
          '<div class="card-head"><div>' +
            '<h3 class="gene-name">' + esc(geneName) + '</h3>' +
            '<div class="gene-group">' + esc(group || "Ручной ввод") + '</div>' +
          '</div><span class="status-label">Matched</span></div>' +
          '<div class="match"><div class="match-head">' +
            '<span class="genotype">' + esc(hit.displayGt || genotype) + '</span>' +
            '<span class="badge badge-matched">MATCHED</span>' +
            acmgBadge +
          '</div><div class="detail-grid">' +
            detailBox("Фенотип", pheno, false) +
            detailBox("Функция", func, false) +
            detailBox("Клинический риск", risk, critical) +
          '</div>' + recHtml + '</div>' +
          more +
        '</article>'
      );
    }

    function buildMissingCard(geneName, genotype, message) {
      return (
        '<article class="card no-match manual-entry risk-gray">' +
          '<div class="card-head"><div>' +
            '<h3 class="gene-name">' + esc(geneName) + '</h3>' +
            '<div class="gene-group">Ручной ввод</div>' +
          '</div><span class="status-label">Manual</span></div>' +
          '<div class="match-head solo"><span class="genotype">' + esc(genotype) + '</span></div>' +
          '<div class="note">' + esc(message) + '</div>' +
        '</article>'
      );
    }

    function analyze(geneName, genotype) {
      var kb = loadKb();
      var found = findGene(kb, geneName);
      if (!found) {
        return buildMissingCard(
          geneName, genotype,
          "Ген не найден в текущей базе знаний. Требуется добавление."
        );
      }
      var hit = matchGenotype(found.gene, genotype);
      if (!hit) {
        return buildMissingCard(
          geneName, genotype,
          "Ген найден в базе, но генотип «" + genotype + "» не сопоставлен с таблицами. Требуется проверка."
        );
      }
      var sym = geneSymbol(found.gene.header) || geneName;
      return buildMatchedCard(sym, found.group, genotype, hit, found.gene);
    }

    function openModal() {
      if (!modal) return;
      modal.classList.add("is-open");
      modal.setAttribute("aria-hidden", "false");
      if (nameInput) nameInput.focus();
    }

    function closeModal() {
      if (!modal) return;
      modal.classList.remove("is-open");
      modal.setAttribute("aria-hidden", "true");
      if (form) form.reset();
    }

    if (openBtn) openBtn.addEventListener("click", openModal);
    if (cancelBtn) cancelBtn.addEventListener("click", closeModal);
    if (modal) {
      modal.addEventListener("click", function (e) {
        if (e.target === modal) closeModal();
      });
    }
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && modal && modal.classList.contains("is-open")) closeModal();
    });

    if (form) {
      form.addEventListener("submit", function (e) {
        e.preventDefault();
        var gene = (nameInput && nameInput.value || "").trim();
        var genotype = (gtInput && gtInput.value || "").trim();
        if (!gene || !genotype || !cards) return;
        cards.insertAdjacentHTML("beforeend", analyze(gene, genotype));
        var added = cards.lastElementChild;
        if (added && added.scrollIntoView) {
          added.scrollIntoView({ behavior: "smooth", block: "nearest" });
        }
        closeModal();
      });
    }
  })();
  </script>
"""
    return template.replace("__KNOWLEDGE_BASE_JSON__", kb_json)


def generate_html_report(rep: dict, output_path: str):
    stats = rep.get("stats", {})
    results = rep.get("results", [])

    matched = [r for r in results if r.get("status") == "matched"]
    matched_annotation = [r for r in results if r.get("status") == "matched_annotation_only"]
    no_table = [r for r in results if r.get("status") == "no_table_in_base"]
    no_match = [r for r in results if r.get("status") == "no_genotype_match"]
    not_in_base = [r for r in results if r.get("status") == "not_in_knowledge_base"]

    matched_html = "".join(_gene_card(r, "matched") for r in matched)
    matched_annotation_html = "".join(
        _gene_card(r, "matched_annotation") for r in matched_annotation
    )
    no_match_html = "".join(_gene_card(r, "no_match") for r in no_match)
    no_table_html = "".join(_gene_card(r, "no_table") for r in no_table)

    not_in_base_html = ""
    if not_in_base:
        items = "".join(
            f"<li><b>{_esc(r['gene'])}</b> — {_esc(r.get('patient_result', ''))}</li>"
            for r in not_in_base
        )
        not_in_base_html = f"""
        <section id="missing_genes" class="missing_genes">
            <h2>Гены вне базы знаний</h2>
            <div class="not-in-base">
                <p class="hint">Эти гены есть в отчёте, но отсутствуют в текущей базе знаний.</p>
                <ul>{items}</ul>
            </div>
        </section>
        """

    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    patient_id, raw_file = _safe_header_identity(rep)
    file_name = _esc(raw_file)
    run_id = str(rep.get("run_id") or rep.get("Run_ID") or "").strip()
    meta_bits = []
    if patient_id:
        meta_bits.append(
            f'<span class="meta-item"><span class="meta-key">Patient ID</span>'
            f'<span class="meta-val">{_esc(patient_id)}</span></span>'
        )
    if run_id and not _looks_like_person_name(run_id):
        meta_bits.append(
            f'<span class="meta-item"><span class="meta-key">Run ID</span>'
            f'<span class="meta-val">{_esc(run_id)}</span></span>'
        )
    meta_bits.append(
        f'<span class="meta-item"><span class="meta-key">Source</span>'
        f'<span class="meta-val">{file_name}</span></span>'
    )
    meta_bits.append(
        f'<span class="meta-item"><span class="meta-key">Date</span>'
        f'<span class="meta-val">{_esc(now)}</span></span>'
    )
    meta_bar = "".join(meta_bits)
    alerts_html = _render_critical_alerts(results)
    doctors_html = _render_doctors_note(results)

    total_pgx = sum(len(r.get("pgx_annotations", [])) for r in results)
    found_count = stats.get("matched", 0) + stats.get("matched_annotation_only", 0)
    attention_count = len(collect_critical_alerts(results))

    manual_ui = _manual_gene_entry_ui(_load_knowledge_base_embed())
    gene_section = f"""
  <section class="gene-section">
    <h2>Интерпретированные гены</h2>
    <div class="gene-cards" id="interpreted-gene-cards">
      {matched_html}{matched_annotation_html}
    </div>
    {manual_ui}
  </section>
"""
    unmatched_section = ""
    if no_match or no_table:
        unmatched_section = f"""
  <section class="gene-section">
    <h2>Не сопоставленные генотипы</h2>
    <div class="gene-cards">
      {no_match_html}{no_table_html}
    </div>
  </section>
"""

    html_doc = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GenomIQ — {file_name}</title>
<style>
{_report_css()}
</style>
</head>
<body>
<div class="container">

  <header class="report-header">
    <h1>GenomIQ</h1>
    <div class="meta">{meta_bar}</div>
  </header>

  {alerts_html}

  <div class="summary">
    <div class="stat">
      <div class="num">{found_count}</div>
      <div class="label">Найдено генов</div>
    </div>
    <div class="stat stat-attention">
      <div class="num">{attention_count}</div>
      <div class="label">Требуют внимания</div>
    </div>
    <div class="stat">
      <div class="num">{total_pgx}</div>
      <div class="label">Фармакогенетика</div>
    </div>
  </div>

  {gene_section}
  {unmatched_section}
  {not_in_base_html}
  {doctors_html}

  <footer>
    Отчёт сформирован автоматически. Не является медицинским диагнозом.<br>
    Гены, добавленные вручную, требуют проверки врача; система не гарантирует точность интерпретации.<br>
    Для интерпретации обратитесь к врачу-генетику.
  </footer>
</div>

<button class="print-btn no-print" onclick="window.print()">Печать</button>
</body>
</html>
"""

    Path(output_path).write_text(html_doc, encoding="utf-8")
