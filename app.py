"""
app.py — Streamlit веб-интерфейс для Parsing-Gen.

Запуск:
    streamlit run app.py

Открывается браузер на http://localhost:8501
Загружаешь файл (PDF/DOCX/TXT) → нажимаешь «Анализировать» → скачиваешь HTML-отчёт.
"""

import importlib.util
import json
import sys
from pathlib import Path

import streamlit as st


# ============================================================
#  Пути проекта
# ============================================================

ROOT = Path(__file__).resolve().parent
SAMPLES_DIR = ROOT / "samples"
REPORTS_DIR = ROOT / "reports"
DATA_DIR = ROOT / "data"
SRC_DIR = ROOT / "src"
BASE_JSON = DATA_DIR / "parsed_knowledge_base_clean.json"


# ============================================================
#  Динамическая загрузка модулей (как в run.py)
# ============================================================

def _load_module(name: str):
    """Загружает модуль name из src/ или из корня проекта."""
    candidates = [
        SRC_DIR / f"{name}.py",
        ROOT / f"{name}.py",
    ]
    path = None
    for c in candidates:
        if c.exists():
            path = c
            break
    if path is None:
        raise FileNotFoundError(f"Не найден модуль {name}.py ни в {SRC_DIR}, ни в {ROOT}.")

    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _ensure_dirs():
    for d in (SAMPLES_DIR, REPORTS_DIR, DATA_DIR):
        d.mkdir(exist_ok=True)


# ============================================================
#  Обработка одного файла
# ============================================================

def process_uploaded_file(file_path: Path, original_name: str) -> dict:
    """
    Обрабатывает один файл: парсит, интерпретирует, генерирует HTML.
    Возвращает словарь с результатом и путями к файлам.
    """
    interpreter = _load_module("interpreter")
    html_report = _load_module("html_report")

    # Загружаем базу
    if not BASE_JSON.exists():
        raise FileNotFoundError(
            f"Не найдена база знаний: {BASE_JSON}\n"
            f"Запустите: python run.py build"
        )

    base = interpreter.load_base(str(BASE_JSON))
    gene_index = interpreter.build_gene_index(base)

    # Читаем файл
    text = interpreter.read_any(str(file_path))
    if not text.strip():
        raise ValueError("Файл пустой или не удалось извлечь текст.")

    patients = interpreter.parse_patient_report(text)
    results = [interpreter.interpret_gene(p, gene_index) for p in patients]

    # Формируем отчёт
    rep = {
        "file": original_name,
        "genes_total": len(results),
        "stats": {
            "matched": sum(1 for r in results if r["status"] == "matched"),
            "no_genotype_match": sum(1 for r in results if r["status"] == "no_genotype_match"),
            "no_table_in_base": sum(1 for r in results if r["status"] == "no_table_in_base"),
            "not_in_knowledge_base": sum(1 for r in results if r["status"] == "not_in_knowledge_base"),
        },
        "results": results,
    }

    stem = Path(original_name).stem

    # JSON
    out_json = REPORTS_DIR / f"{stem}_report.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)

    # Markdown
    out_md = REPORTS_DIR / f"{stem}_report.md"
    interpreter.save_markdown([rep], str(out_md))

    # HTML
    out_html = REPORTS_DIR / f"{stem}_report.html"
    html_report.generate_html_report(rep, str(out_html))

    return {
        "rep": rep,
        "json": out_json,
        "md": out_md,
        "html": out_html,
    }


# ============================================================
#  Интерфейс Streamlit
# ============================================================

def main():
    st.set_page_config(
        page_title="Генетический анализатор",
        page_icon="🧬",
        layout="wide",
    )

    _ensure_dirs()

    # --- Заголовок ---
    st.title("🧬 Генетический анализатор")
    st.caption(
        "Система автоматической интерпретации генетических отчётов. "
        "Загрузите файл из лаборатории — получите структурированный HTML-отчёт."
    )

    # --- Сайдбар: информация о базе ---
    with st.sidebar:
        st.header("📚 База знаний")
        if BASE_JSON.exists():
            try:
                with open(BASE_JSON, encoding="utf-8") as f:
                    base = json.load(f)
                total_genes = sum(len(g["genes"]) for g in base)
                st.success(f"✅ Загружено: {len(base)} групп, {total_genes} генов")
                for g in base:
                    st.write(f"• {g['group']} — {len(g['genes'])} генов")
            except Exception as e:
                st.error(f"Ошибка чтения базы: {e}")
        else:
            st.error("❌ База не найдена")
            st.code("python run.py build", language="bash")

        st.divider()
        st.header("ℹ️ Форматы")
        st.write("PDF, DOCX, TXT, MD")

    # --- Загрузка файла ---
    uploaded = st.file_uploader(
        "Загрузите отчёт лаборатории",
        type=["pdf", "docx", "txt", "md"],
        help="Поддерживаются PDF, DOCX, TXT, MD",
    )

    if uploaded is None:
        st.info("👆 Перетащите файл в поле выше или нажмите «Browse files».")
        return

    # Сохраняем загруженный файл во временный путь
    temp_path = SAMPLES_DIR / uploaded.name
    with open(temp_path, "wb") as f:
        f.write(uploaded.getbuffer())

    st.success(f"📄 Файл загружен: **{uploaded.name}** ({len(uploaded.getbuffer())} байт)")

    # --- Кнопка «Анализировать» ---
    col_btn, col_info = st.columns([1, 3])
    with col_btn:
        run_clicked = st.button("🔬 Анализировать", type="primary", use_container_width=True)
    with col_info:
        st.caption("Нажмите, чтобы запустить интерпретацию.")

    if not run_clicked:
        return

    # --- Обработка ---
    with st.spinner("Обработка отчёта…"):
        try:
            result = process_uploaded_file(temp_path, uploaded.name)
        except Exception as e:
            st.error(f"❌ Ошибка: {e}")
            with st.expander("Подробности (traceback)"):
                st.exception(e)
            return

    rep = result["rep"]
    stats = rep["stats"]

    st.success("✅ Анализ завершён")

    # --- Счётчики ---
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("✅ Найдено", stats["matched"])
    c2.metric("🟡 Нет таблицы", stats["no_table_in_base"])
    c3.metric("⚠️ Не сопоставлено", stats["no_genotype_match"])
    c4.metric("❌ Нет в базе", stats["not_in_knowledge_base"])

    # --- Результаты по генам ---
    with st.expander("📋 Результаты по генам", expanded=False):
        for r in rep["results"]:
            status = r["status"]
            icon = {
                "matched": "✅",
                "no_genotype_match": "⚠️",
                "no_table_in_base": "🟡",
                "not_in_knowledge_base": "❌",
            }.get(status, "·")

            gene = r["gene"]
            result_text = r.get("patient_result", "")

            if status == "matched":
                gt = r.get("matched_genotype", "")
                row = r.get("full_row") or {}
                risk = ""
                for k, v in row.items():
                    if "риск" in k.lower() or "профиль" in k.lower() or "фенотип" in k.lower():
                        risk = v
                        break
                st.markdown(f"**{icon} {gene}** — `{gt}` | {risk[:80]}")
            elif status == "no_table_in_base":
                st.markdown(f"**{icon} {gene}** — {result_text} _(нет таблицы генотипов в базе)_")
            elif status == "no_genotype_match":
                cands = r.get("extracted_candidates", [])
                st.markdown(f"**{icon} {gene}** — {result_text} _(кандидаты: {cands})_")
            else:
                st.markdown(f"**{icon} {gene}** — {result_text}")

    # --- Скачивание ---
    st.subheader("📥 Скачать отчёт")

    col1, col2, col3 = st.columns(3)

    with col1:
        with open(result["html"], "rb") as f:
            st.download_button(
                "🌐 HTML-отчёт",
                data=f,
                file_name=result["html"].name,
                mime="text/html",
                use_container_width=True,
            )

    with col2:
        with open(result["md"], "rb") as f:
            st.download_button(
                "📝 Markdown",
                data=f,
                file_name=result["md"].name,
                mime="text/markdown",
                use_container_width=True,
            )

    with col3:
        with open(result["json"], "rb") as f:
            st.download_button(
                "🗂 JSON",
                data=f,
                file_name=result["json"].name,
                mime="application/json",
                use_container_width=True,
            )

    # --- Превью HTML ---
    st.subheader("👁 Предпросмотр HTML-отчёта")
    with open(result["html"], encoding="utf-8") as f:
        html_content = f.read()

    st.components.v1.html(html_content, height=800, scrolling=True)


if __name__ == "__main__":
    main()