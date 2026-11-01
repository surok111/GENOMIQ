"""
run.py — единая точка входа (v15).
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
SAMPLES_DIR = ROOT / "samples"
REPORTS_DIR = ROOT / "reports"

def _ensure_dirs():
    for d in (DATA_DIR, SAMPLES_DIR, REPORTS_DIR):
        d.mkdir(exist_ok=True)

def _load_module(name: str):
    sys.path.insert(0, str(ROOT / "src"))
    import importlib
    if name in sys.modules:
        importlib.reload(sys.modules[name])
    return importlib.import_module(name)

def cmd_build(args):
    _ensure_dirs()
    print("=" * 70)
    print("  BUILD: построение базы знаний")
    print("=" * 70)

    md_parser = _load_module("md_parser")
    cleanup = _load_module("cleanup")

    old_cwd = os.getcwd()
    os.chdir(ROOT)
    try:
        print("\n[1/2] Парсинг data/…")
        base = md_parser.parse_directory("data")
        with open("data/parsed_knowledge_base.json", "w", encoding="utf-8") as f:
            json.dump(base, f, ensure_ascii=False, indent=2)
        print(f"      Групп: {len(base)}")
        for g in base:
            print(f"        {g['group']}: {len(g['genes'])} генов")

        print("\n[2/2] Постобработка…")
        cleanup.main()
    finally:
        os.chdir(old_cwd)
    print("\n✅ База знаний готова.")

def _read_file_text(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in (".txt", ".md"):
        return path.read_text(encoding="utf-8")
    if ext == ".docx":
        try:
            from docx import Document
        except ImportError:
            print("❌ Нужен пакет python-docx. Установите: pip install python-docx")
            sys.exit(1)
        doc = Document(str(path))
        return "\n".join(p.text for p in doc.paragraphs)
    if ext == ".pdf":
        try:
            import pdfplumber
        except ImportError:
            print("❌ Для PDF нужен pdfplumber. Установите: pip install pdfplumber")
            sys.exit(1)
        with pdfplumber.open(str(path)) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    return ""

def cmd_report(args):
    _ensure_dirs()
    src_path = Path(args.file).resolve()
    if not src_path.exists():
        print(f"❌ Файл не найден: {src_path}")
        sys.exit(1)

    print("=" * 70)
    print(f"  REPORT: {src_path.name}")
    print("=" * 70)

    text = _read_file_text(src_path)
    print(f"Прочитано символов: {len(text)}")

    interpreter = _load_module("interpreter")
    html_report = _load_module("html_report")

    old_cwd = os.getcwd()
    os.chdir(ROOT)
    try:
        base = interpreter.load_base("data/parsed_knowledge_base_clean.json")
        gene_index = interpreter.build_gene_index(base)
        print(f"Генов в базе: {len(gene_index)}")

        patients = interpreter.parse_patient_report(text)
        print(f"Генов в отчёте: {len(patients)}\n")

        results = [interpreter.interpret_gene(p, gene_index) for p in patients]
        try:
            from genedb.enrich import attach_live_db
            attach_live_db(results)
        except Exception as e:
            print(f"Живая БД генов не подключена: {e}")

        rep = {
            "file": src_path.name,
            "genes_total": len(results),
            "stats": {
                "matched": sum(1 for r in results if r["status"] == "matched"),
                "matched_annotation_only": sum(1 for r in results if r["status"] == "matched_annotation_only"),
                "no_genotype_match": sum(1 for r in results if r["status"] == "no_genotype_match"),
                "no_table_in_base": sum(1 for r in results if r["status"] == "no_table_in_base"),
                "not_in_knowledge_base": sum(1 for r in results if r["status"] == "not_in_knowledge_base"),
            },
            "results": results,
        }

        total_green = rep["stats"]["matched"] + rep["stats"]["matched_annotation_only"]
        print(f"  Генов: {rep['genes_total']} | ✅ Найдено (зеленых): {total_green} | ⚠️ Не сопоставлено: {rep['stats']['no_genotype_match']} | ❌ Нет в базе: {rep['stats']['not_in_knowledge_base']}")

        out_json = REPORTS_DIR / f"{src_path.stem}_report.json"
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(rep, f, ensure_ascii=False, indent=2)
        print(f"💾 JSON: {out_json}")

        out_html = REPORTS_DIR / f"{src_path.stem}_report.html"
        html_report.generate_html_report(rep, str(out_html))
        print(f"💾 HTML: {out_html}")

    finally:
        os.chdir(old_cwd)

def cmd_sync(args):
    _ensure_dirs()
    sys.path.insert(0, str(ROOT / "src"))
    from genedb.sync import sync_genes

    symbols = [s.strip() for s in (args.genes or "").split(",") if s.strip()] or None
    sources = [s.strip() for s in (args.sources or "").split(",") if s.strip()] or None
    print("=" * 70)
    print("  SYNC: OMIM / ClinVar / ClinPGx")
    print("=" * 70)
    summary = sync_genes(
        symbols=symbols,
        sources=sources,
        backup_first=not args.no_backup,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def cmd_backup(args):
    sys.path.insert(0, str(ROOT / "src"))
    from genedb.backup import create_backup, list_backups, restore_backup

    if args.list:
        items = list_backups()
        if not items:
            print("Бэкапов пока нет.")
            return
        for item in items:
            print(f"{item['id']}  {item.get('kind')}  {item.get('created_at')}  {item.get('path')}")
        return
    if args.restore:
        result = restore_backup(args.restore, what=args.what)
        print("Восстановлено:", result)
        return
    meta = create_backup(kind="manual")
    print(f"Создан бэкап {meta['id']}")
    print(f"  путь: {meta['path']}")
    for f in meta.get("files", []):
        print(f"  {f['name']}: {f['bytes']} байт")


def cmd_db_status(args):
    sys.path.insert(0, str(ROOT / "src"))
    from genedb.store import GeneStore

    with GeneStore() as store:
        print(json.dumps(store.counts(), ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(prog="run.py", description="Parsing-Gen CLI")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("build", help="Построить базу знаний из data/")

    p_report = sub.add_parser("report", help="Обработать один файл")
    p_report.add_argument("file", help="Путь к файлу (.txt/.md/.docx/.pdf)")

    p_sync = sub.add_parser("sync", help="Обновить живую БД генов из OMIM/ClinVar/ClinPGx")
    p_sync.add_argument("--genes", help="Список символов через запятую (по умолчанию все из базы знаний)")
    p_sync.add_argument("--sources", help="omim,clinvar,clinpgx (по умолчанию все)")
    p_sync.add_argument("--no-backup", action="store_true", help="Не делать бэкап перед синхронизацией")

    p_backup = sub.add_parser("backup", help="Снимок SQLite и JSON базы знаний")
    p_backup.add_argument("--list", action="store_true", help="Показать бэкапы")
    p_backup.add_argument("--restore", metavar="ID", help="Восстановить бэкап по timestamp")
    p_backup.add_argument("--what", default="all", choices=["all", "sqlite", "knowledge"])

    sub.add_parser("db-status", help="Статистика живой БД генов")

    args = parser.parse_args()
    if args.cmd == "build":
        cmd_build(args)
    elif args.cmd == "report":
        cmd_report(args)
    elif args.cmd == "sync":
        cmd_sync(args)
    elif args.cmd == "backup":
        cmd_backup(args)
    elif args.cmd == "db-status":
        cmd_db_status(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()