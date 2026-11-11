"""Синхронизация живой БД генов с OMIM, ClinVar и ClinPGx."""

from __future__ import annotations

from typing import Callable, Iterable

from .backup import create_backup
from .catalog import load_knowledge_genes
from .clients.clinpgx import fetch_clinpgx
from .clients.clinvar import fetch_clinvar
from .clients.omim import fetch_omim
from .httputil import HttpError
from .paths import load_dotenv
from .store import GeneStore

SOURCES = ("omim", "clinvar", "clinpgx")
ProgressCb = Callable[[str], None]


def _merge_aliases(symbol: str, *lists: list[str] | None) -> list[str]:
    seen: set[str] = {symbol.strip().upper()}
    merged: list[str] = []
    for lst in lists:
        for raw in lst or []:
            alias = str(raw).strip()
            if not alias:
                continue
            key = alias.upper()
            if key in seen:
                continue
            seen.add(key)
            merged.append(alias)
    return merged


def _log(cb: ProgressCb | None, message: str) -> None:
    if cb:
        cb(message)
    else:
        print(message)


def sync_genes(
    symbols: Iterable[str] | None = None,
    sources: Iterable[str] | None = None,
    store: GeneStore | None = None,
    backup_first: bool = True,
    progress: ProgressCb | None = None,
) -> dict:
    """
    Обновляет SQLite-базу генов из внешних API.

    symbols=None — все гены из локальной базы знаний.
    sources — подмножество omim/clinvar/clinpgx.
    """
    load_dotenv()
    own_store = store is None
    store = store or GeneStore()
    selected = tuple(s.lower() for s in (sources or SOURCES))
    for src in selected:
        if src not in SOURCES:
            raise ValueError(f"Неизвестный источник: {src}. Допустимы: {SOURCES}")

    catalog = load_knowledge_genes()
    catalog_map = {g["symbol"]: g for g in catalog}
    if symbols:
        wanted = []
        for raw in symbols:
            sym = raw.strip().upper()
            wanted.append(catalog_map.get(sym, {"symbol": sym, "aliases": [], "name": sym, "kb_group": ""}))
        genes = wanted
    else:
        genes = catalog

    backup_id = None
    if backup_first:
        try:
            meta = create_backup(kind="auto-pre-sync", store=store)
            backup_id = meta["id"]
            _log(progress, f"Бэкап перед синхронизацией: {backup_id}")
        except Exception as e:
            _log(progress, f"Предупреждение: бэкап перед sync не создан ({e})")

    run_id = store.start_sync_run(selected, backup_id)
    ok = 0
    failed = 0
    errors: list[str] = []

    try:
        for gene in genes:
            symbol = gene["symbol"]
            _log(progress, f"→ {symbol}")
            store.upsert_gene(gene)
            gene_error = None
            try:
                if "omim" in selected:
                    omim_entries = fetch_omim(symbol)
                    store.replace_omim(symbol, omim_entries)
                    meta = None
                    for e in omim_entries:
                        if e.get("gene_meta"):
                            meta = e["gene_meta"]
                            break
                    if meta:
                        store.upsert_gene({
                            "symbol": symbol,
                            "aliases": _merge_aliases(
                                symbol,
                                gene.get("aliases"),
                                meta.get("aliases"),
                            ),
                            "name": gene.get("name") or meta.get("name"),
                            "chromosome": meta.get("chromosome"),
                            "summary": meta.get("summary"),
                            "kb_group": gene.get("kb_group"),
                        })
                    _log(progress, f"   OMIM: {len(omim_entries)} записей")

                if "clinvar" in selected:
                    variants, stats = fetch_clinvar(symbol)
                    store.replace_clinvar(symbol, variants, stats)
                    _log(
                        progress,
                        f"   ClinVar: всего {stats.get('total', 0)}, "
                        f"P/LP {stats.get('pathogenic', 0)}/{stats.get('likely_pathogenic', 0)}, "
                        f"сохранено {len(variants)}",
                    )

                if "clinpgx" in selected:
                    pgx = fetch_clinpgx(symbol)
                    store.replace_clinpgx(
                        symbol,
                        pgx.get("clinpgx_id"),
                        pgx.get("annotations") or [],
                        pgx.get("labels") or [],
                    )
                    _log(
                        progress,
                        f"   ClinPGx: {len(pgx.get('annotations') or [])} аннотаций, "
                        f"{len(pgx.get('labels') or [])} FDA-лейблов",
                    )
            except Exception as e:
                gene_error = str(e)
                failed += 1
                errors.append(f"{symbol}: {e}")
                _log(progress, f"   ошибка: {e}")
            else:
                ok += 1
            store.mark_synced(symbol, gene_error)

        store.finish_sync_run(run_id, ok, failed, "; ".join(errors[:8]) or None)
        summary = {
            "ok": ok,
            "failed": failed,
            "total": len(genes),
            "sources": selected,
            "backup_id": backup_id,
            "errors": errors,
        }
        _log(progress, f"Готово: {ok}/{len(genes)} генов, ошибок {failed}")
        return summary
    except Exception as e:
        store.finish_sync_run(run_id, ok, failed, str(e))
        raise
    finally:
        if own_store:
            store.close()
