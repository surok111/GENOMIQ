"""
html_report.py — premium Apple-style HTML report (v16).
Critical alerts, doctor's note, PHI-safe header, print-friendly CSS.
"""

import html
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from interpreter import build_doctors_note, collect_critical_alerts

ACMG_COLORS = {
    "pathogenic": ("#ff3b30", "#ffffff"),
    "risk factor": ("#ff9500", "#ffffff"),
    "likely": ("#86868b", "#ffffff"),
    "trait": ("#86868b", "#ffffff"),
    "benign": ("#34c759", "#ffffff"),
    "normal": ("#34c759", "#ffffff"),
}


def _acmg_color(acmg_text: str):
    if not acmg_text:
        return ("#86868b", "#ffffff")
    t = acmg_text.lower()
    for key, colors in ACMG_COLORS.items():
        if key in t:
            return colors
    return ("#86868b", "#ffffff")


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


def _short_group_label(group: str) -> str:
    """'Группа 5: Фармакогенетика и …' → 'Фармакогенетика'."""
    g = (group or "").strip()
    if ":" in g:
        g = g.split(":", 1)[1].strip()
    g = re.sub(r"^Группа\s*\d+\s*", "", g, flags=re.I).strip(" —–-")
    # Prefer a short category keyword for the mini-dashboard.
    low = g.lower()
    aliases = [
        ("фармакоген", "Фармакогенетика"),
        ("липид", "Липиды"),
        ("фолат", "Фолаты"),
        ("детоксик", "Детоксикация"),
        ("антиоксид", "Антиоксиданты"),
        ("тромбо", "Тромбоз"),
        ("сердеч", "ССС"),
        ("онко", "Онкориск"),
        ("иммун", "Иммунитет"),
    ]
    for needle, label in aliases:
        if needle in low:
            return label
    # Fallback: first 2–3 words, truncated.
    words = g.split()
    short = " ".join(words[:3]).rstrip(",;")
    return (short[:28] + "…") if len(short) > 28 else (short or "Прочее")


def _is_risk_acmg(acmg: str) -> bool:
    low = (acmg or "").lower()
    return "pathogenic" in low or "risk factor" in low


def _count_risk_by_group(results: list, top_n: int = 4) -> list[dict]:
    """Top medical groups by count of Pathogenic / Risk factor genes."""
    buckets: dict[str, dict] = {}
    for r in results or []:
        if r.get("status") not in {"matched", "matched_annotation_only"}:
            continue
        if not _is_risk_acmg(_acmg_text_for_result(r)):
            continue
        raw_group = (r.get("group") or "Прочее").strip() or "Прочее"
        label = _short_group_label(raw_group)
        entry = buckets.setdefault(label, {"label": label, "count": 0, "full": raw_group})
        entry["count"] += 1
    ranked = sorted(buckets.values(), key=lambda x: (-x["count"], x["label"]))
    return ranked[:top_n]


def _render_risk_chart(group_counts: list) -> str:
    if not group_counts:
        return ""
    max_n = max(int(g["count"]) for g in group_counts) or 1
    rows = []
    for g in group_counts:
        n = int(g["count"])
        pct = max(8, int(round((n / max_n) * 100)))
        # 1 gene → amber (moderate), 2+ → red (high concentration in category)
        tone = "bar-high" if n >= 2 else "bar-mod"
        glow = " bar-glow" if n >= 2 else ""
        rows.append(
            f"""
          <div class="risk-row" title="{_esc(g.get('full') or g['label'])}: {n}">
            <div class="risk-cat">{_esc(g['label'])}</div>
            <div class="risk-track">
              <div class="risk-bar-h {tone}{glow}" style="width:{pct}%"></div>
            </div>
            <div class="risk-num">{n}</div>
          </div>
            """
        )
    return f"""
      <div class="risk-chart" aria-label="Risk profile by category">
        <div class="risk-chart-title">Risk Profile</div>
        <div class="risk-rows">
          {''.join(rows)}
        </div>
      </div>
    """


def _render_critical_alerts(results: list) -> str:
    alerts = collect_critical_alerts(results)
    if not alerts:
        return ""
    chart = _render_risk_chart(_count_risk_by_group(results))
    if len(alerts) == 1:
        a = alerts[0]
        left = f"""
      <div class="critical-copy">
        <p class="critical-lead">⚠️ ВНИМАНИЕ: {_esc(a['text'])} ({_esc(a['gene'])})</p>
      </div>
        """
    else:
        items = "".join(
            f"<li><b>{_esc(a['gene'])}</b> — {_esc(a['text'])}</li>" for a in alerts
        )
        left = f"""
      <div class="critical-copy">
        <p class="critical-lead">⚠️ ВНИМАНИЕ</p>
        <ul>{items}</ul>
      </div>
        """
    return f"""
    <section class="critical-alerts" id="critical-alerts">
      {left}
      {chart}
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
        display = _display_row_value(k, v, patient_gt)
        kl = k.strip().lower()
        emphasis = _is_emphasis_field(k)
        critical = emphasis and _is_critical_risk(str(display))
        boxes.append(
            _render_detail_box(k, str(display), emphasis=emphasis, critical=critical)
        )
    return '<div class="detail-grid">' + "".join(boxes) + "</div>"


def _render_recs_boxes(recs: list) -> str:
    if not recs:
        return ""
    items = "".join(f"<li>{_esc(r)}</li>" for r in recs)
    return f"""
        <div class="recs detail-box detail-emphasis">
            <div class="detail-label">Рекомендации</div>
            <div class="detail-value"><ul class="recs-list">{items}</ul></div>
        </div>
    """


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

    PHENO_COLORS = {
        "toxicity": ("#ff3b30", "#fff"),
        "efficacy": ("#0071e3", "#fff"),
        "metabolism/pk": ("#86868b", "#fff"),
        "dosage": ("#1d1d1f", "#fff"),
        "other": ("#86868b", "#fff"),
    }

    exact_count = sum(1 for a in pgx_annotations if a.get("match_kind") == "exact")
    allele_count = sum(1 for a in pgx_annotations if a.get("match_kind") == "allele")
    counter_parts = []
    if exact_count:
        counter_parts.append(f"точных: {exact_count}")
    if allele_count:
        counter_parts.append(f"по аллели: {allele_count}")
    counter_text = " · ".join(counter_parts)

    rows_html = []
    for a in pgx_annotations:
        pheno = (a.get("phenotype") or "Other").lower()
        fg, bg = PHENO_COLORS.get(pheno, PHENO_COLORS["other"])
        pheno_label = a.get("phenotype") or "Other"
        kind = a.get("match_kind")
        if kind == "exact":
            match_icon = "●"
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
                <td><span class="pgx-badge" style="color:{fg};border-color:{fg};">{_esc(pheno_label)}</span></td>
                <td><b>{_esc(a.get('drug', '—'))}</b></td>
                <td>{_esc(a.get('association', ''))}</td>
                <td class="pgx-pval">{_esc(a.get('pvalue', '—'))}</td>
            </tr>
        """)

    return f"""
        <div class="pgx-block">
            <h4>Фармакогенетика
                <span class="pgx-count">({len(pgx_annotations)})</span>
                <span class="pgx-counter">{counter_text}</span>
            </h4>
            <div class="pgx-table-wrap">
                <table class="pgx-table">
                    <thead>
                        <tr>
                            <th></th>
                            <th>Генотип</th>
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


def _render_why(result: dict) -> str:
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
    return f"""
        <details class="why">
            <summary>Why?</summary>
            <div class="why-body">{body}</div>
        </details>
    """


def _gene_card(result: dict, status_kind: str) -> str:
    gene = _esc(result["gene"])
    group = _esc(result.get("group", ""))
    patient_result = _esc(_redact_phi(result.get("patient_result", "")))
    comment = _esc(_redact_phi(result.get("patient_comment", "")))
    recs = result.get("recommendations", [])
    why_block = _render_why(result)

    pgx_block = _render_pgx_block(
        result.get("pgx_annotations", []),
        result.get("pgx_no_match_info"),
    )
    live_block = _render_live_db(result.get("live_db"))

    status_label = {
        "matched": "Matched",
        "matched_annotation": "Annotation",
        "no_table": "No table",
        "no_match": "Unmatched",
    }.get(status_kind, "")

    if status_kind == "matched_annotation":
        note = _esc(result.get("note", ""))
        recs_html = ""
        if recs:
            recs_html = _render_recs_boxes(recs)
        return f"""
        <article class="card matched annotation-only">
            <div class="card-head">
                <div>
                    <h3 class="gene-name">{gene}</h3>
                    <div class="gene-group">{group}</div>
                </div>
                <span class="status-label">{status_label}</span>
            </div>
            <div class="patient-line"><span class="label">Результат</span> <span class="value">{patient_result}</span></div>
            {f'<div class="patient-line comment">{comment}</div>' if comment else ''}
            {why_block}
            {f'<div class="note">{note}</div>' if note else ''}
            {pgx_block}
            {live_block}
            {recs_html}
        </article>
        """

    if status_kind == "matched":
        matches = result.get("matches", [])
        cards_inner = ""
        for m in matches:
            row = m["full_row"]
            gt = _esc(m["genotype"])
            source = _esc(m.get("source_part", ""))
            acmg = row.get("ACMG", "")
            fg, _bg = _acmg_color(acmg)
            acmg_badge = (
                f'<span class="badge" style="color:{fg};border-color:{fg};">'
                f'{_esc(acmg) or "—"}</span>'
            )
            detail_boxes = _render_row_detail_boxes(row, m.get("genotype"))
            cards_inner += f"""
                <div class="match">
                    <div class="match-head">
                        <span class="genotype">{gt}</span>
                        <span class="source">{source}</span>
                        {acmg_badge}
                    </div>
                    {detail_boxes}
                </div>
            """

        recs_html = ""
        if recs:
            recs_html = _render_recs_boxes(recs)

        return f"""
        <article class="card matched">
            <div class="card-head">
                <div>
                    <h3 class="gene-name">{gene}</h3>
                    <div class="gene-group">{group}</div>
                </div>
                <span class="status-label">{status_label}</span>
            </div>
            <div class="patient-line"><span class="label">Результат</span> <span class="value">{patient_result}</span></div>
            {f'<div class="patient-line comment">{comment}</div>' if comment else ''}
            {why_block}
            {cards_inner}
            {pgx_block}
            {live_block}
            {recs_html}
        </article>
        """

    if status_kind == "no_table":
        note = _esc(result.get("note", ""))
        recs_html = ""
        if recs:
            recs_html = _render_recs_boxes(recs)
        return f"""
        <article class="card no-table">
            <div class="card-head">
                <div>
                    <h3 class="gene-name">{gene}</h3>
                    <div class="gene-group">{group}</div>
                </div>
                <span class="status-label">{status_label}</span>
            </div>
            <div class="patient-line"><span class="label">Результат</span> <span class="value">{patient_result}</span></div>
            {f'<div class="patient-line comment">{comment}</div>' if comment else ''}
            {why_block}
            {f'<div class="note">{note}</div>' if note else ''}
            {pgx_block}
            {live_block}
            {recs_html}
        </article>
        """

    note = _esc(result.get("note", ""))
    return f"""
    <article class="card no-match">
        <div class="card-head">
            <div>
                <h3 class="gene-name">{gene}</h3>
                <div class="gene-group">{group}</div>
            </div>
            <span class="status-label">{status_label}</span>
        </div>
        <div class="patient-line"><span class="label">Результат</span> <span class="value">{patient_result}</span></div>
        {why_block}
        {f'<div class="note">{note}</div>' if note else ''}
        {pgx_block}
        {live_block}
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
    --font: "Times New Roman", Times, serif;
  }
  * { box-sizing: border-box; }
  html { scroll-behavior: smooth; }
  body, button, input, textarea, select, summary, h1, h2, h3, h4, h5, p, li, td, th, a, span, div {
    font-family: var(--font) !important;
  }
  body {
    margin: 0;
    padding: 0;
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

  @keyframes cardFadeIn {
    from { opacity: 0; transform: translateY(12px); }
    to { opacity: 1; transform: translateY(0); }
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
    background: linear-gradient(180deg, #ffffff 0%, #f4f4f7 100%);
    border: 1px solid #e5e5ea;
    border-radius: 12px;
    padding: 10px 4px;
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 1), 0 2px 10px rgba(0,0,0,0.03);
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
  }

  .summary {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: 12px;
    margin: 0 0 40px;
  }
  .summary .stat {
    background: linear-gradient(145deg, #ffffff, #f0f0f2);
    border: 1px solid #e5e5ea;
    border-radius: 16px;
    padding: 16px 12px;
    overflow: hidden;
    box-shadow: 0 4px 20px rgba(0,0,0,0.04), inset 0 1px 0 rgba(255,255,255,0.8);
    transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
    animation: cardFadeIn 0.6s ease both;
  }
  .summary .stat:hover {
    transform: scale(1.01);
    box-shadow: 0 10px 30px rgba(0,0,0,0.08);
  }
  .summary .stat .num {
    font-size: 28px;
    font-weight: 700;
    color: var(--text);
    line-height: 1.1;
  }
  .summary .stat .label {
    margin-top: 6px;
    font-size: 11px;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.03em;
    line-height: 1.3;
    word-wrap: break-word;
    overflow-wrap: break-word;
    hyphens: auto;
  }

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
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 28px;
    background: #000000;
    color: #ffffff;
    border: 1px solid #333;
    border-radius: 16px;
    padding: 24px;
    margin: 0 0 36px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.2);
    animation: cardFadeIn 0.55s ease both;
  }
  .critical-copy {
    flex: 1 1 55%;
    min-width: 0;
  }
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

  .risk-chart {
    flex: 0 0 42%;
    max-width: 340px;
    background: transparent;
    min-width: 220px;
  }
  .risk-chart-title {
    font-size: 11px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #86868b;
    margin: 0 0 12px;
  }
  .risk-rows {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .risk-row {
    display: grid;
    grid-template-columns: minmax(88px, 34%) 1fr 28px;
    align-items: center;
    gap: 10px;
  }
  .risk-cat {
    font-size: 12px;
    color: #f5f5f7;
    line-height: 1.2;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .risk-track {
    height: 10px;
    background: rgba(255,255,255,0.08);
    border-radius: 980px;
    overflow: hidden;
  }
  .risk-bar-h {
    height: 100%;
    border-radius: 980px;
    min-width: 8px;
    transition: width 0.5s ease;
    box-shadow: inset 0 0 10px rgba(255,255,255,0.2);
  }
  .risk-bar-h.bar-high {
    background: linear-gradient(90deg, #ff6961 0%, #ff3b30 100%);
  }
  .risk-bar-h.bar-high.bar-glow {
    box-shadow: inset 0 0 10px rgba(255,255,255,0.25), 0 0 12px rgba(255, 59, 48, 0.45);
  }
  .risk-bar-h.bar-mod {
    background: linear-gradient(90deg, #ffd60a 0%, #ff9500 100%);
  }
  .risk-num {
    font-size: 13px;
    font-weight: 700;
    color: #ffffff;
    text-align: right;
  }
  @media (max-width: 700px) {
    .critical-alerts {
      flex-direction: column;
      align-items: stretch;
    }
    .risk-chart {
      flex: 1 1 auto;
      max-width: none;
    }
  }

  .gene-section h2 {
    margin-bottom: 20px;
  }
  .gene-cards {
    display: grid;
    grid-template-columns: 1fr;
    gap: 24px;
    align-items: stretch;
    scroll-snap-type: y proximity;
  }
  @media (min-width: 900px) {
    .gene-cards {
      grid-template-columns: 1fr 1fr;
    }
  }

  .card {
    background: linear-gradient(135deg, #ffffff 0%, #f4f4f7 100%);
    border: 1px solid #e5e5ea;
    border-radius: 16px;
    padding: 28px 24px;
    margin: 0;
    height: 100%;
    display: flex;
    flex-direction: column;
    scroll-snap-align: start;
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 1), 0 4px 20px rgba(0,0,0,0.05);
    transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
    animation: cardFadeIn 0.7s ease both;
  }
  .card:nth-child(2) { animation-delay: 0.05s; }
  .card:nth-child(3) { animation-delay: 0.1s; }
  .card:nth-child(4) { animation-delay: 0.15s; }
  .card:nth-child(5) { animation-delay: 0.2s; }
  .card:hover {
    transform: scale(1.01);
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 1), 0 10px 30px rgba(0,0,0,0.08);
    border-color: #d2d2d7;
  }

  .card-head {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 16px;
    margin-bottom: 18px;
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
    font-size: 12px;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--muted);
    border: 1px solid var(--line);
    border-radius: 980px;
    padding: 4px 12px;
    white-space: nowrap;
    background: linear-gradient(180deg, #fbfbfd, #f5f5f7);
  }

  .patient-line {
    background: transparent;
    padding: 0;
    margin: 0 0 10px;
    font-size: 16px;
  }
  .patient-line .label {
    color: var(--muted);
    margin-right: 8px;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .patient-line .value {
    font-size: 18px;
    font-weight: 700;
    color: var(--text);
  }
  .patient-line.comment {
    font-style: italic;
    color: var(--muted);
    font-size: 14px;
  }

  .match {
    border-top: 1px solid #e5e5ea;
    padding-top: 18px;
    margin-top: 18px;
  }
  .match-head {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    align-items: center;
    margin-bottom: 14px;
  }
  .genotype {
    background: linear-gradient(180deg, #ffffff 0%, #ebebf0 100%);
    color: var(--text);
    border: 1px solid var(--line);
    padding: 6px 12px;
    border-radius: 10px;
    font-weight: 700;
    font-size: 15px;
  }
  .source { color: var(--muted); font-size: 13px; }
  .badge {
    padding: 3px 10px;
    border-radius: 980px;
    border: 1px solid var(--line);
    background: linear-gradient(180deg, #fbfbfd, #f5f5f7);
    font-size: 12px;
    font-weight: 700;
  }

  .detail-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: 8px;
  }
  .detail-box {
    background: linear-gradient(180deg, #ffffff 0%, #ebebf0 100%);
    border: 1px solid #d2d2d7;
    border-radius: 10px;
    padding: 12px 16px;
    margin-bottom: 0;
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.9);
  }
  .detail-box.detail-emphasis {
    border-left: 3px solid #1d1d1f;
  }
  .detail-box.detail-critical {
    border-left: 3px solid #ff3b30;
  }
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
  .recs-list li {
    padding: 3px 0;
    font-weight: 700;
  }
  .recs { margin-top: 16px; }

  .why {
    margin: 14px 0 8px;
    background: transparent;
    border: none;
    padding: 0;
  }
  .why summary {
    cursor: pointer;
    list-style: none;
    display: inline-block;
    margin: 0;
    padding: 6px 16px;
    background: #1d1d1f;
    color: #ffffff;
    border: none;
    border-radius: 980px;
    font-size: 14px;
    font-weight: 500;
    text-decoration: none;
    transition: background 0.2s;
    user-select: none;
  }
  .why summary::-webkit-details-marker { display: none; }
  .why summary::before { content: none; }
  .why summary:hover,
  .why[open] summary {
    background: #424245;
    color: #ffffff;
  }
  .why-body {
    margin-top: 14px;
    padding: 16px;
    background: linear-gradient(180deg, #fbfbfd, #f5f5f7);
    border: 1px solid #d2d2d7;
    border-radius: 10px;
    font-size: 14px;
    color: var(--text);
  }
  .why-sentence { margin: 0 0 10px; line-height: 1.55; font-weight: 700; }
  .why-body ul { padding-left: 18px; margin: 0; color: var(--muted); }
  .why-body li { padding: 3px 0; }

  .live-db h4, .pgx-block h4 {
    font-size: 18px;
    font-weight: 500;
    margin: 0 0 10px;
    color: var(--text);
  }
  .live-db ul {
    padding-left: 18px;
    margin: 0;
    font-size: 15px;
  }
  .live-db {
    margin-top: 18px;
    padding: 16px 0 0;
    border-top: 1px solid #e5e5ea;
    background: transparent;
  }
  .live-db h5 {
    margin: 12px 0 4px;
    font-size: 12px;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
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
    background: transparent;
    padding: 0;
    margin-top: 10px;
  }

  .not-in-base {
    background: linear-gradient(145deg, #ffffff, #f0f0f2);
    border: 1px solid #e5e5ea;
    border-radius: 16px;
    padding: 24px 28px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.04), inset 0 1px 0 rgba(255,255,255,0.8);
  }
  .not-in-base .hint { color: var(--muted); font-size: 14px; margin: 0 0 12px; }
  .not-in-base ul { padding-left: 18px; margin: 0; font-size: 15px; }

  .pgx-block {
    margin-top: 20px;
    border-top: 1px solid #e5e5ea;
    padding-top: 16px;
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
  .pgx-match-col { width: 28px; text-align: center; }
  .pgx-row-exact, .pgx-row-allele { background: transparent; border-left: none; }
  .pgx-badge {
    padding: 2px 8px;
    border-radius: 980px;
    border: 1px solid var(--line);
    font-size: 11px;
    font-weight: 700;
    background: linear-gradient(180deg, #fbfbfd, #f5f5f7);
    display: inline-block;
  }
  .pgx-gt { font-weight: 700; white-space: nowrap; }
  .pgx-pval { color: var(--muted); white-space: nowrap; }
  .pgx-no-match {
    background: linear-gradient(180deg, #fbfbfd, #f5f5f7);
    border: 1px solid #d2d2d7;
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
    animation: cardFadeIn 0.7s ease both;
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
    transition: background 0.2s;
  }
  .print-btn:hover { background: #424245; }

  @media print {
    * { box-shadow: none !important; transform: none !important; animation: none !important; }
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
      box-shadow: none !important;
    }
    .critical-alerts li, .critical-alerts b, .critical-lead { color: #000 !important; }
    .print-btn, .why summary { display: none !important; }
    .why-body { display: block !important; }
    .critical-alerts, .card, .doctors-note {
      page-break-inside: avoid;
      break-inside: avoid;
    }
    thead { display: table-header-group; }
    .pgx-table th { background: none !important; }
    .pgx-table-wrap { overflow: visible; }
  }
"""


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
    genes_with_no_data = sum(
        1
        for r in results
        if not r.get("pgx_annotations") and r.get("pgx_no_match_info")
    )

    gene_section = ""
    if matched or matched_annotation:
        gene_section = f"""
  <section class="gene-section">
    <h2>Интерпретированные гены</h2>
    <div class="gene-cards">
      {matched_html}{matched_annotation_html}
    </div>
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
      <div class="num">{stats.get('matched', 0) + stats.get('matched_annotation_only', 0)}</div>
      <div class="label">Найдено</div>
    </div>
    <div class="stat">
      <div class="num">{stats.get('no_genotype_match', 0)}</div>
      <div class="label">Не сопоставлено</div>
    </div>
    <div class="stat">
      <div class="num">{stats.get('not_in_knowledge_base', 0)}</div>
      <div class="label">Нет в базе</div>
    </div>
    <div class="stat">
      <div class="num">{total_pgx}</div>
      <div class="label">Фармакогенетика</div>
    </div>
    <div class="stat">
      <div class="num">{genes_with_no_data}</div>
      <div class="label">Без данных</div>
    </div>
  </div>

  {gene_section}
  {unmatched_section}
  {not_in_base_html}
  {doctors_html}

  <footer>
    Отчёт сформирован автоматически. Не является медицинским диагнозом.<br>
    Для интерпретации обратитесь к врачу-генетику.
  </footer>
</div>

<button class="print-btn no-print" onclick="window.print()">Печать</button>
</body>
</html>
"""

    Path(output_path).write_text(html_doc, encoding="utf-8")
