"""ClinVar staging: filter, canonical hash, and PostgreSQL UPSERT."""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from clinvar_ingest.download import VARIANT_SUMMARY_URL, download_variant_summary
from clinvar_ingest.errors import ClinVarDownloadError, ClinVarIngestError, ClinVarParseError, ClinVarPersistError
from clinvar_ingest.hashing import HASH_FIELDS, canonical_hash
from clinvar_ingest.panel import load_hgnc_panel
from clinvar_ingest.parser import (
    dedupe_variation,
    is_retained,
    iter_retained_records,
    iter_variant_chunks,
)
from clinvar_ingest.pipeline import ingest_clinvar
from clinvar_ingest.upsert import UPSERT_SQL, ensure_clinvar_schema, upsert_records
from migrate_to_pg import SCHEMA_SQL, _password_is_placeholder, _read_database_url

FIXTURE = ROOT / "tests" / "fixtures" / "clinvar_variant_summary_sample.tsv"
FIXTURE_IDS = [880000000201, 880000000202, 880000000203, 880000000204, 880000000205]
DIRECT_ID = 880000000301
PANEL = {"CYP2C19", "MTHFR"}


def _gzip_fixture(dest: Path) -> Path:
    with FIXTURE.open("rb") as source, gzip.open(dest, "wb") as handle:
        handle.write(source.read())
    return dest


def _record(**overrides) -> dict:
    base = {field: f"v-{field}" for field in HASH_FIELDS}
    base.update(overrides)
    return base


class CanonicalHashTest(unittest.TestCase):
    def test_hash_is_sha256_of_sorted_compact_json(self):
        record = _record(PhenotypeList="ignore-me", NumberSubmitters="4")
        payload = {field: record[field] for field in HASH_FIELDS}
        expected = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        self.assertEqual(canonical_hash(record), expected)
        self.assertEqual(len(expected), 64)

    def test_unrelated_fields_do_not_change_hash(self):
        left = _record(PhenotypeList="alpha", RCVaccession="RCV1")
        right = _record(PhenotypeList="beta", RCVaccession="RCV2", SubmitterCategories="3")
        self.assertEqual(canonical_hash(left), canonical_hash(right))

    def test_listed_field_changes_hash(self):
        left = _record(ClinicalSignificance="Pathogenic")
        right = _record(ClinicalSignificance="Likely pathogenic")
        self.assertNotEqual(canonical_hash(left), canonical_hash(right))

    def test_missing_field_is_json_null(self):
        record = {field: "x" for field in HASH_FIELDS if field != "Origin"}
        payload = {field: ("x" if field != "Origin" else None) for field in HASH_FIELDS}
        expected = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        self.assertEqual(canonical_hash(record), expected)

    def test_rs_column_alias(self):
        aliased = {field: "a" for field in HASH_FIELDS if field != "RS#"}
        aliased["RS# (dbSNP)"] = "4242"
        direct = {field: "a" for field in HASH_FIELDS}
        direct["RS#"] = "4242"
        self.assertEqual(canonical_hash(aliased), canonical_hash(direct))


class FilterTest(unittest.TestCase):
    def test_panel_comes_from_knowledge_base(self):
        panel = load_hgnc_panel()
        self.assertIn("CYP2C19", panel)
        self.assertIn("MTHFR", panel)
        self.assertNotIn("BRCA1", panel)

    def test_exact_significance_and_panel(self):
        pathogenic = _record(GeneSymbol="CYP2C19", ClinicalSignificance="Pathogenic")
        likely = _record(GeneSymbol="mthfr", ClinicalSignificance="Likely pathogenic")
        combined = _record(GeneSymbol="CYP2C19", ClinicalSignificance="Pathogenic/Likely pathogenic")
        benign = _record(GeneSymbol="CYP2C19", ClinicalSignificance="Benign")
        other = _record(GeneSymbol="BRCA1", ClinicalSignificance="Pathogenic")
        multi = _record(GeneSymbol="BRCA1;CYP2C19", ClinicalSignificance="Pathogenic")
        self.assertTrue(is_retained(pathogenic, PANEL))
        self.assertTrue(is_retained(likely, PANEL))
        self.assertTrue(is_retained(multi, PANEL))
        self.assertFalse(is_retained(combined, PANEL))
        self.assertFalse(is_retained(benign, PANEL))
        self.assertFalse(is_retained(other, PANEL))

    def test_gzip_chunks_keep_only_panel_pathogenic_rows(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = _gzip_fixture(Path(tmp) / "variant_summary.txt.gz")
            with patch("clinvar_ingest.parser.pd.read_csv", wraps=__import__("pandas").read_csv) as mocked:
                rows = list(iter_retained_records(path, PANEL, chunksize=1))
            kwargs = mocked.call_args.kwargs
            self.assertEqual(kwargs["compression"], "gzip")
            self.assertEqual(kwargs["chunksize"], 1)
            self.assertEqual(mocked.call_args.args[0].__class__, type(path))
            ids = [row["VariationID"] for row in rows]
            self.assertEqual(ids, ["880000000201", "880000000201", "880000000201", "880000000204"])
            self.assertEqual(rows[1]["Assembly"], "GRCh38")
            self.assertEqual(rows[1]["RS# (dbSNP)"], "100")
            self.assertIn("PhenotypeList", rows[0])

    def test_plain_tsv_chunks_keep_only_panel_pathogenic_rows(self):
        with patch("clinvar_ingest.parser.pd.read_csv", wraps=__import__("pandas").read_csv) as mocked:
            rows = list(iter_retained_records(FIXTURE, PANEL, chunksize=1))
        kwargs = mocked.call_args.kwargs
        self.assertIsNone(kwargs["compression"])
        self.assertEqual(kwargs["chunksize"], 1)
        ids = [row["VariationID"] for row in rows]
        self.assertEqual(ids, ["880000000201", "880000000201", "880000000201", "880000000204"])
        self.assertEqual(rows[1]["Assembly"], "GRCh38")
        self.assertEqual(rows[1]["RS# (dbSNP)"], "100")
        self.assertIn("PhenotypeList", rows[0])

    def test_vectorized_filter_matches_row_predicate(self):
        all_rows = [
            row
            for chunk in iter_variant_chunks(FIXTURE, chunksize=2)
            for row in chunk
        ]
        expected = [row for row in all_rows if is_retained(row, PANEL)]
        actual = list(iter_retained_records(FIXTURE, PANEL, chunksize=2))
        self.assertEqual(actual, expected)
        self.assertEqual(
            [row["VariationID"] for row in actual],
            ["880000000201", "880000000201", "880000000201", "880000000204"],
        )

    def test_rejected_rows_are_not_materialized(self):
        import pandas as pd

        real = pd.DataFrame.to_dict
        sizes: list[int] = []

        def spy(self, *args, **kwargs):
            sizes.append(len(self))
            return real(self, *args, **kwargs)

        with patch.object(pd.DataFrame, "to_dict", spy):
            rows = list(iter_retained_records(FIXTURE, PANEL, chunksize=50))
        self.assertEqual(sizes, [4])
        self.assertEqual(len(rows), 4)

    def test_token_edges_match_row_predicate(self):
        import tempfile

        header = "VariationID\tGeneSymbol\tClinicalSignificance\tAssembly\n"
        body = "\n".join(
            [
                "1\t cyp2c19 \t Pathogenic \tGRCh38",
                "2\tBRCA1|CYP2C19\tPathogenic\tGRCh38",
                "3\tBRCA1, MTHFR\tLikely pathogenic\tGRCh38",
                "4\t-\tPathogenic\tGRCh38",
                "5\tCYP2C19P\tPathogenic\tGRCh38",
                "6\tCYP2C19\tPathogenic/Likely pathogenic\tGRCh38",
                "7\tCYP2C19;\tPathogenic\tGRCh37",
                "NOPE\tCYP2C19\tPathogenic\tGRCh38",
                "8\tCYP2C19\tBenign\tGRCh38",
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "edges.tsv"
            path.write_text(header + body + "\n", encoding="utf-8")
            all_rows = [row for chunk in iter_variant_chunks(path, chunksize=3) for row in chunk]
            expected = [row for row in all_rows if is_retained(row, PANEL)]
            actual = list(iter_retained_records(path, PANEL, chunksize=3))
        self.assertEqual([row["VariationID"] for row in expected], ["1", "2", "3", "7", "NOPE"])
        self.assertEqual(actual, expected)

    def test_later_grch37_does_not_replace_grch38(self):
        locked: set[int] = set()
        grch37 = _record(VariationID="880000000201", Assembly="GRCh37", Start="100")
        grch38 = _record(VariationID="880000000201", Assembly="GRCh38", Start="200")
        again = _record(VariationID="880000000201", Assembly="GRCh37", Start="300")
        self.assertEqual(dedupe_variation([grch37], locked)[0]["Start"], "100")
        self.assertEqual(dedupe_variation([grch38], locked)[0]["Start"], "200")
        self.assertEqual(dedupe_variation([again], locked), [])

    def test_bad_gzip_raises_parse_error(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "broken.txt.gz"
            path.write_bytes(b"this is not gzip")
            with self.assertRaises(ClinVarParseError):
                list(iter_variant_chunks(path, chunksize=10))

    def test_read_csv_is_not_called_for_empty_panel(self):
        with self.assertRaises(ClinVarParseError):
            list(iter_retained_records("unused.gz", set(), chunksize=10))


def _gzip_bytes(payload: bytes) -> bytes:
    import gzip as gzip_mod

    buffer = io.BytesIO()
    with gzip_mod.GzipFile(fileobj=buffer, mode="wb") as handle:
        handle.write(payload)
    return buffer.getvalue()


class _StreamResponse:
    """Minimal ``requests`` response. Body is available only through ``iter_content``."""

    def __init__(self, status: int, parts: list, headers: dict | None = None):
        self.status_code = status
        self.headers = headers or {}
        self._parts = list(parts)
        self.chunk_size = None

    def iter_content(self, chunk_size=1, decode_unicode=False):
        self.chunk_size = chunk_size
        for item in self._parts:
            if isinstance(item, BaseException):
                raise item
            if not item:
                continue
            step = chunk_size if chunk_size and chunk_size > 0 else len(item)
            for start in range(0, len(item), step):
                yield item[start:start + step]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class DownloadTest(unittest.TestCase):
    def test_streams_to_disk(self):
        import tempfile

        from clinvar_ingest.download import _CHUNK_BYTES

        payload = _gzip_bytes(b"abcdef")
        response = _StreamResponse(
            200,
            [payload[:3], payload[3:7], payload[7:]],
            {"Content-Length": str(len(payload))},
        )
        seen = {}

        def fake_get(url, **kwargs):
            seen["url"] = url
            seen["stream"] = kwargs.get("stream")
            seen["timeout"] = kwargs.get("timeout")
            return response

        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "variant_summary.txt.gz"
            with patch("clinvar_ingest.download.requests.get", side_effect=fake_get):
                download_variant_summary(dest)
            self.assertEqual(dest.read_bytes(), payload)
            self.assertFalse(dest.with_suffix(dest.suffix + ".part").exists())
            self.assertTrue(seen["stream"])
            self.assertEqual(seen["timeout"], (30.0, 60.0))
            self.assertEqual(response.chunk_size, _CHUNK_BYTES)
            self.assertEqual(VARIANT_SUMMARY_URL.endswith("variant_summary.txt.gz"), True)

    def test_progress_logs_every_interval(self):
        import tempfile

        payload = _gzip_bytes(b"abcdefghijklmnop")
        response = _StreamResponse(200, [payload], {"Content-Length": str(len(payload))})

        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "variant_summary.txt.gz"
            with patch("clinvar_ingest.download.requests.get", return_value=response):
                with self.assertLogs("clinvar_ingest.download", level="INFO") as captured:
                    download_variant_summary(dest, progress_every=10)
            self.assertEqual(len(captured.records), len(payload) // 10)
            self.assertTrue(all("ClinVar download:" in line for line in captured.output))

    def test_progress_interval_defaults_to_10_mb(self):
        import inspect

        default = inspect.signature(download_variant_summary).parameters["progress_every"].default
        self.assertEqual(default, 10 * 1024 * 1024)

    def test_http_error_removes_partial_file(self):
        import tempfile

        response = _StreamResponse(404, [])

        def fake_get(url, **kwargs):
            return response

        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "variant_summary.txt.gz"
            with patch("clinvar_ingest.download.requests.get", side_effect=fake_get):
                with self.assertRaises(ClinVarDownloadError):
                    download_variant_summary(dest)
            self.assertFalse(dest.exists())
            self.assertFalse(dest.with_suffix(dest.suffix + ".part").exists())
            self.assertIsNone(response.chunk_size)

    def test_connection_reset_resumes_with_range(self):
        import tempfile

        payload = _gzip_bytes(b"variant-summary")
        ranges: list[str | None] = []

        def fake_get(url, **kwargs):
            headers = kwargs.get("headers") or {}
            ranges.append(headers.get("Range"))
            if len(ranges) == 1:
                return _StreamResponse(
                    200,
                    [payload[:8], ConnectionResetError(10054, "forcibly closed")],
                    {"Content-Length": str(len(payload))},
                )
            return _StreamResponse(
                206,
                [payload[8:]],
                {
                    "Content-Range": f"bytes 8-{len(payload) - 1}/{len(payload)}",
                    "Content-Length": str(len(payload) - 8),
                },
            )

        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "variant_summary.txt.gz"
            with patch("clinvar_ingest.download.requests.get", side_effect=fake_get):
                download_variant_summary(dest, retries=2, backoff=0)
            self.assertEqual(ranges, [None, "bytes=8-"])
            self.assertEqual(dest.read_bytes(), payload)
            self.assertFalse(dest.with_suffix(dest.suffix + ".part").exists())

    def test_retries_use_exponential_backoff(self):
        import tempfile

        opens = {"count": 0}
        delays: list[float] = []

        def fake_get(url, **kwargs):
            opens["count"] += 1
            return _StreamResponse(200, [ConnectionResetError(10054, "forcibly closed")])

        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "variant_summary.txt.gz"
            with patch("clinvar_ingest.download.requests.get", side_effect=fake_get):
                with patch("clinvar_ingest.download.time.sleep", side_effect=delays.append):
                    with self.assertRaises(ClinVarDownloadError) as caught:
                        download_variant_summary(dest, retries=3, backoff=0.5)
            self.assertIn("ConnectionResetError", str(caught.exception))
            self.assertEqual(opens["count"], 4)
            self.assertEqual(delays, [0.5, 1.0, 2.0])
            self.assertFalse(dest.exists())
            self.assertFalse(dest.with_suffix(dest.suffix + ".part").exists())

    def test_existing_partial_is_resumed(self):
        import tempfile

        payload = _gzip_bytes(b"resume-me")
        seen: list[str | None] = []
        streamed = {"chunk": None}

        def fake_get(url, **kwargs):
            headers = kwargs.get("headers") or {}
            seen.append(headers.get("Range"))
            self.assertTrue(kwargs.get("stream"))
            self.assertEqual(kwargs.get("timeout"), (30.0, 60.0))
            offset = 10
            response = _StreamResponse(
                206,
                [payload[offset:]],
                {"Content-Range": f"bytes {offset}-{len(payload) - 1}/{len(payload)}"},
            )
            streamed["response"] = response
            return response

        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "variant_summary.txt.gz"
            part = dest.with_suffix(dest.suffix + ".part")
            part.write_bytes(payload[:10])
            with patch("clinvar_ingest.download.requests.get", side_effect=fake_get):
                download_variant_summary(dest, retries=0, backoff=0)
            self.assertEqual(seen, ["bytes=10-"])
            self.assertEqual(dest.read_bytes(), payload)
            self.assertGreater(streamed["response"].chunk_size, 0)

    def test_invalid_gzip_is_not_published(self):
        import tempfile

        body = b"this is not gzip"
        ranges: list[str | None] = []

        def fake_get(url, **kwargs):
            headers = kwargs.get("headers") or {}
            ranges.append(headers.get("Range"))
            return _StreamResponse(200, [body], {"Content-Length": str(len(body))})

        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "variant_summary.txt.gz"
            with patch("clinvar_ingest.download.requests.get", side_effect=fake_get):
                with self.assertRaises(ClinVarDownloadError) as caught:
                    download_variant_summary(dest, retries=1, backoff=0)
            self.assertIn("gzip", str(caught.exception))
            self.assertEqual(ranges, [None, None])
            self.assertFalse(dest.exists())
            self.assertFalse(dest.with_suffix(dest.suffix + ".part").exists())

    def test_short_download_is_not_published(self):
        import tempfile

        payload = _gzip_bytes(b"short")

        def fake_get(url, **kwargs):
            return _StreamResponse(
                200,
                [payload],
                {"Content-Length": str(len(payload) + 25)},
            )

        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "variant_summary.txt.gz"
            part = dest.with_suffix(dest.suffix + ".part")
            with patch("clinvar_ingest.download.requests.get", side_effect=fake_get):
                with self.assertRaises(ClinVarDownloadError) as caught:
                    download_variant_summary(dest, retries=0, backoff=0)
            self.assertIn("complete", str(caught.exception))
            self.assertFalse(dest.exists())
            self.assertEqual(part.read_bytes(), payload)


class UpsertContractTest(unittest.TestCase):
    def test_sql_updates_only_when_hash_changes(self):
        compact = " ".join(UPSERT_SQL.split())
        self.assertIn("ON CONFLICT (clinvar_variation_id) DO UPDATE SET", compact)
        self.assertIn(
            "WHERE clinvar_staging.content_sha256 IS DISTINCT FROM EXCLUDED.content_sha256",
            compact,
        )
        self.assertNotIn("DO NOTHING", compact)

    def test_migration_creates_staging_without_dropping_it(self):
        self.assertIn("CREATE TABLE IF NOT EXISTS clinvar_staging", SCHEMA_SQL)
        self.assertIn("clinvar_variation_id BIGINT PRIMARY KEY", SCHEMA_SQL)
        self.assertIn("raw_payload JSONB", SCHEMA_SQL)
        self.assertNotIn("DROP TABLE", SCHEMA_SQL.split("clinvar_staging")[0][-80:])
        self.assertNotIn("DROP TABLE IF EXISTS clinvar_staging", SCHEMA_SQL)


class StagingDatabaseTest(unittest.TestCase):
    conn = None

    @classmethod
    def setUpClass(cls):
        url = _read_database_url()
        if _password_is_placeholder(url):
            raise unittest.SkipTest("DATABASE_URL is not configured")
        import psycopg

        try:
            cls.conn = psycopg.connect(url)
        except Exception as exc:
            raise unittest.SkipTest(f"PostgreSQL unavailable ({exc.__class__.__name__})") from exc
        ensure_clinvar_schema(cls.conn)
        cls.conn.commit()
        cls.url = url

    @classmethod
    def tearDownClass(cls):
        if cls.conn is not None:
            cls.conn.close()

    def setUp(self):
        self._kb_before = self._kb_count()
        self._delete([DIRECT_ID, *FIXTURE_IDS])

    def tearDown(self):
        self._delete([DIRECT_ID, *FIXTURE_IDS])
        self.assertEqual(self._kb_count(), self._kb_before)

    def _kb_count(self) -> int:
        with self.conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM kb_genotypes")
            return int(cur.fetchone()[0])

    def _delete(self, ids: list[int]) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                "DELETE FROM clinvar_staging WHERE clinvar_variation_id = ANY(%s)",
                (ids,),
            )
        self.conn.commit()

    def _fetch(self, variation_id: int):
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT rcv_accession, gene_symbol, gene_id, clinical_significance,
                       content_sha256, raw_payload, source_retrieved_at
                FROM clinvar_staging
                WHERE clinvar_variation_id = %s
                """,
                (variation_id,),
            )
            return cur.fetchone()

    def test_schema_columns(self):
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'clinvar_staging'
                ORDER BY ordinal_position
                """
            )
            found = {name: dtype for name, dtype in cur.fetchall()}
        self.assertEqual(found["clinvar_variation_id"], "bigint")
        self.assertEqual(found["rcv_accession"], "text")
        self.assertEqual(found["gene_symbol"], "text")
        self.assertEqual(found["gene_id"], "integer")
        self.assertEqual(found["clinical_significance"], "text")
        self.assertEqual(found["content_sha256"], "character")
        self.assertEqual(found["raw_payload"], "jsonb")
        self.assertEqual(found["source_retrieved_at"], "timestamp with time zone")

    def test_insert_update_and_unchanged(self):
        first_at = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
        same_at = datetime(2026, 6, 7, 8, 9, 10, tzinfo=timezone.utc)
        changed_at = datetime(2026, 8, 9, 10, 11, 12, tzinfo=timezone.utc)
        original = _record(
            VariationID=str(DIRECT_ID),
            GeneSymbol="CYP2C19",
            GeneID="1557",
            ClinicalSignificance="Pathogenic",
            RCVaccession="RCV-OLD",
            PhenotypeList="kept-in-payload",
        )
        inserted = upsert_records(self.conn, [original], first_at)
        self.conn.commit()
        self.assertEqual((inserted.inserted, inserted.updated, inserted.unchanged), (1, 0, 0))

        stored = self._fetch(DIRECT_ID)
        self.assertEqual(stored[0], "RCV-OLD")
        self.assertEqual(stored[1], "CYP2C19")
        self.assertEqual(stored[2], 1557)
        self.assertEqual(stored[3], "Pathogenic")
        self.assertEqual(stored[4].strip(), canonical_hash(original))
        self.assertEqual(stored[5]["PhenotypeList"], "kept-in-payload")
        self.assertEqual(stored[5]["VariationID"], str(DIRECT_ID))
        self.assertEqual(stored[6], first_at)

        untouched = dict(original)
        untouched["RCVaccession"] = "RCV-NEW"
        untouched["PhenotypeList"] = "should-not-land"
        unchanged = upsert_records(self.conn, [untouched], same_at)
        self.conn.commit()
        self.assertEqual((unchanged.inserted, unchanged.updated, unchanged.unchanged), (0, 0, 1))
        stored = self._fetch(DIRECT_ID)
        self.assertEqual(stored[0], "RCV-OLD")
        self.assertEqual(stored[5]["PhenotypeList"], "kept-in-payload")
        self.assertEqual(stored[6], first_at)

        revised = dict(original)
        revised["ClinicalSignificance"] = "Likely pathogenic"
        revised["RCVaccession"] = "RCV-UPDATED"
        updated = upsert_records(self.conn, [revised], changed_at)
        self.conn.commit()
        self.assertEqual((updated.inserted, updated.updated, updated.unchanged), (0, 1, 0))
        stored = self._fetch(DIRECT_ID)
        self.assertEqual(stored[0], "RCV-UPDATED")
        self.assertEqual(stored[3], "Likely pathogenic")
        self.assertEqual(stored[4].strip(), canonical_hash(revised))
        self.assertEqual(stored[6], changed_at)

    def test_ingest_fixture_prefers_grch38_and_filters(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = _gzip_fixture(Path(tmp) / "variant_summary.txt.gz")
            summary = ingest_clinvar(
                self.url,
                source=path,
                panel=PANEL,
                chunksize=1,
            )
        self.assertFalse(summary["downloaded"])
        self.assertEqual(summary["matched"], 4)
        self.assertEqual(summary["inserted"], 2)
        self.assertEqual(summary["updated"], 1)
        self.assertEqual(summary["unchanged"], 0)

        chosen = self._fetch(880000000201)
        self.assertEqual(chosen[5]["Assembly"], "GRCh38")
        self.assertEqual(chosen[5]["Start"], "200")
        self.assertEqual(chosen[5]["RCVaccession"], "RCV0001")
        self.assertIsNotNone(self._fetch(880000000204))
        self.assertIsNone(self._fetch(880000000202))
        self.assertIsNone(self._fetch(880000000203))
        self.assertIsNone(self._fetch(880000000205))

    def test_database_error_rolls_back(self):
        import psycopg

        class Cursor:
            def execute(self, sql, params=None):
                if "INSERT INTO clinvar_staging" in sql:
                    raise psycopg.OperationalError("database unavailable")

            def fetchall(self):
                return []

            def fetchone(self):
                return None

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        class Conn:
            def __init__(self):
                self.rolled_back = False

            def cursor(self):
                return Cursor()

            def rollback(self):
                self.rolled_back = True

        conn = Conn()
        with self.assertRaises(ClinVarPersistError):
            upsert_records(conn, [_record(VariationID=str(DIRECT_ID))], datetime.now(timezone.utc))
        self.assertTrue(conn.rolled_back)

    def test_placeholder_url_is_rejected(self):
        with self.assertRaises(ClinVarPersistError):
            ingest_clinvar(
                "postgresql://postgres:YOUR_PASSWORD@localhost:5432/postgres",
                source="unused.gz",
                panel=PANEL,
            )
