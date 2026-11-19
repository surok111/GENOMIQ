"""CPIC staging: client retries, guideline versions, and recommendation refresh."""

from __future__ import annotations

import asyncio
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cpic_ingest.client import CpicClient, retry_policy
from cpic_ingest.drugs import drugs_from_row, load_drug_names, unique_drugs
from cpic_ingest.errors import CpicApiError
from cpic_ingest.pipeline import drugs_to_refresh, ingest_cpic
from cpic_ingest.records import guideline_action, normalize_guideline, normalize_recommendation
from cpic_ingest.schema import CPIC_STAGING_SQL
from cpic_ingest.store import (
    GUIDELINE_UPSERT_SQL,
    RECOMMENDATION_UPSERT_SQL,
    ensure_cpic_schema,
    upsert_guideline,
    upsert_recommendation,
)
from migrate_to_pg import SCHEMA_SQL, _password_is_placeholder, _read_database_url

GUIDELINE_ID = 880000301
RECOMMENDATION_IDS = [880000401, 880000402]
TEST_DRUG = "cpic-test-drug"


def _guideline(version: int, year: int = 2020, name: str = "CPIC test guideline") -> dict:
    return {
        "id": GUIDELINE_ID,
        "version": version,
        "clinpgxid": "PA000TEST",
        "name": name,
        "url": "https://cpicpgx.org/guideline/test/",
        "drugs": [TEST_DRUG],
        "publication": {"title": "A paper", "pmid": "123456", "year": year},
    }


def _recommendation(recommendation_id: int, lookup: str = "Poor Metabolizer") -> dict:
    return {
        "recommendationid": recommendation_id,
        "lookupkey": {"CYP2C19": lookup},
        "drugname": TEST_DRUG,
        "guidelinename": "CPIC test guideline",
        "guidelineurl": "https://cpicpgx.org/guideline/test/",
    }


class _FakeClient:
    def __init__(self, guidelines: list[dict], recommendations: dict[str, list[dict]]):
        self.guidelines = guidelines
        self.recommendations = recommendations
        self.guideline_calls = 0
        self.recommendation_calls: list[str] = []
        self.closed = False

    async def fetch_guidelines(self) -> list[dict]:
        self.guideline_calls += 1
        return self.guidelines

    async def fetch_recommendations(self, drugname: str) -> list[dict]:
        self.recommendation_calls.append(drugname)
        return self.recommendations.get(drugname, [])

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        self.closed = True

    async def aclose(self):
        self.closed = True


class GuidelineRecordTest(unittest.TestCase):
    def test_version_decides_the_change_not_publication_year(self):
        self.assertEqual(guideline_action(None, 1), "insert")
        self.assertEqual(guideline_action(1, 2), "update")
        self.assertEqual(guideline_action(2, 2), "unchanged")
        self.assertEqual(guideline_action(3, 2), "unchanged")
        first = normalize_guideline(_guideline(1, year=2018))
        later_year = normalize_guideline(_guideline(1, year=2024))
        self.assertEqual(first["version"], later_year["version"])
        self.assertNotEqual(first["publication_year"], later_year["publication_year"])
        self.assertEqual(
            guideline_action(first["version"], later_year["version"]),
            "unchanged",
        )

    def test_normalize_recommendation_keeps_lookupkey(self):
        row = normalize_recommendation(_recommendation(7), fallback_drug="other")
        self.assertEqual(row["recommendationid"], 7)
        self.assertEqual(row["lookupkey"], {"CYP2C19": "Poor Metabolizer"})
        self.assertEqual(row["drugname"], TEST_DRUG)
        self.assertIsNone(normalize_recommendation({"lookupkey": {}}))


class DrugSourceTest(unittest.TestCase):
    def test_drugs_come_from_row_cells_not_a_fixed_list(self):
        names = drugs_from_row(
            {
                "Drug": "valproic acid; **Warfarin**",
                "Препарат": "**Celecoxib**, piroxicam",
                "Phenotype": "not a drug",
            }
        )
        self.assertEqual(
            unique_drugs(names),
            ["valproic acid", "Warfarin", "Celecoxib", "piroxicam"],
        )
        source = (ROOT / "src" / "cpic_ingest" / "drugs.py").read_text(encoding="utf-8")
        self.assertNotIn("warfarin", source.casefold())

    def test_refresh_skips_synced_drugs_until_a_guideline_changes(self):
        drugs = [TEST_DRUG, "other-drug"]
        self.assertEqual(
            drugs_to_refresh(
                drugs,
                changed_names=set(),
                changed_drug_names=set(),
                synced=set(),
                stored_by_drug={},
            ),
            drugs,
        )
        self.assertEqual(
            drugs_to_refresh(
                drugs,
                changed_names=set(),
                changed_drug_names=set(),
                synced=set(drugs),
                stored_by_drug={TEST_DRUG: {"CPIC test guideline"}},
            ),
            [],
        )
        self.assertEqual(
            drugs_to_refresh(
                drugs,
                changed_names={"CPIC test guideline"},
                changed_drug_names=set(),
                synced=set(drugs),
                stored_by_drug={TEST_DRUG: {"CPIC test guideline"}},
            ),
            [TEST_DRUG],
        )


class CpicClientTest(unittest.TestCase):
    def test_retry_policy_matches_the_milestone(self):
        policy = retry_policy()
        self.assertEqual(policy["stop"].max_attempt_number, 5)
        self.assertEqual(policy["wait"].max, 60)
        self.assertEqual(type(policy["wait"]).__name__, "wait_exponential_jitter")

    def test_client_closes_its_http_resources(self):
        async def scenario():
            transport = httpx.MockTransport(lambda request: httpx.Response(200, json=[]))
            client = CpicClient(transport=transport, timeout=12.5)
            async with client as opened:
                inner = opened._client
                self.assertFalse(inner.is_closed)
                self.assertEqual(inner.timeout.connect, 12.5)
            self.assertTrue(inner.is_closed)

        asyncio.run(scenario())

    def test_guidelines_and_recommendations_use_the_cpic_paths(self):
        seen = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            if request.url.path.endswith("/guideline"):
                return httpx.Response(200, json=[_guideline(1)])
            return httpx.Response(200, json=[_recommendation(RECOMMENDATION_IDS[0])])

        async def scenario():
            async with CpicClient(transport=httpx.MockTransport(handler)) as client:
                guidelines = await client.fetch_guidelines()
                recommendations = await client.fetch_recommendations(TEST_DRUG)
            return guidelines, recommendations

        guidelines, recommendations = asyncio.run(scenario())
        self.assertEqual(guidelines[0]["id"], GUIDELINE_ID)
        self.assertEqual(recommendations[0]["recommendationid"], RECOMMENDATION_IDS[0])
        guideline_url = str(seen[0].url)
        self.assertIn("guideline", guideline_url)
        self.assertIn("publication", guideline_url)
        self.assertEqual(seen[0].url.params["order"], "name")
        self.assertEqual(seen[1].url.params["drugname"], f"eq.{TEST_DRUG}")

    def test_transient_http_and_transport_errors_are_retried(self):
        attempts = {"status": 0, "transport": 0}

        def status_handler(request: httpx.Request) -> httpx.Response:
            attempts["status"] += 1
            if attempts["status"] < 3:
                return httpx.Response(503, json={"message": "unavailable"})
            return httpx.Response(200, json=[])

        def transport_handler(request: httpx.Request) -> httpx.Response:
            attempts["transport"] += 1
            raise httpx.ConnectError("connection failed")

        async def no_sleep(*args, **kwargs):
            return None

        async def scenario():
            with patch("asyncio.sleep", new=no_sleep):
                async with CpicClient(transport=httpx.MockTransport(status_handler)) as client:
                    self.assertEqual(await client.fetch_guidelines(), [])
                with self.assertRaises(CpicApiError):
                    async with CpicClient(transport=httpx.MockTransport(transport_handler)) as client:
                        await client.fetch_guidelines()

        asyncio.run(scenario())
        self.assertEqual(attempts["status"], 3)
        self.assertEqual(attempts["transport"], 5)

    def test_client_errors_are_not_retried(self):
        for status in (400, 401, 403, 404):
            with self.subTest(status=status):
                attempts = {"count": 0}

                def handler(request: httpx.Request, status=status) -> httpx.Response:
                    attempts["count"] += 1
                    return httpx.Response(status, json={"message": "no"})

                async def scenario():
                    async with CpicClient(transport=httpx.MockTransport(handler)) as client:
                        await client.fetch_recommendations(TEST_DRUG)

                with self.assertRaises(CpicApiError) as caught:
                    asyncio.run(scenario())
                self.assertIn(str(status), str(caught.exception))
                self.assertEqual(attempts["count"], 1)


class CpicDatabaseTest(unittest.TestCase):
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
        ensure_cpic_schema(cls.conn)
        cls.conn.commit()
        cls.url = url

    @classmethod
    def tearDownClass(cls):
        if cls.conn is not None:
            cls.conn.close()

    def setUp(self):
        self._kb_before = self._kb_count()
        self._delete_test_rows()

    def tearDown(self):
        self._delete_test_rows()
        self.assertEqual(self._kb_count(), self._kb_before)

    def _kb_count(self) -> int:
        with self.conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM kb_genotypes")
            return int(cur.fetchone()[0])

    def _delete_test_rows(self) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                "DELETE FROM cpic_recommendation WHERE recommendationid = ANY(%s)",
                (RECOMMENDATION_IDS,),
            )
            cur.execute("DELETE FROM cpic_guideline WHERE id = %s", (GUIDELINE_ID,))
            cur.execute("DELETE FROM cpic_drug_sync WHERE drugname = %s", (TEST_DRUG,))
        self.conn.commit()

    def test_schema_is_part_of_the_existing_migration(self):
        self.assertIn("CREATE TABLE IF NOT EXISTS cpic_guideline", SCHEMA_SQL)
        self.assertIn("CREATE TABLE IF NOT EXISTS cpic_recommendation", CPIC_STAGING_SQL)
        self.assertNotIn("DROP TABLE IF EXISTS cpic_guideline", SCHEMA_SQL)
        self.assertIn("WHERE cpic_guideline.version < EXCLUDED.version", GUIDELINE_UPSERT_SQL)
        self.assertNotIn("publication_year", GUIDELINE_UPSERT_SQL.split("WHERE", 1)[1])
        self.assertNotIn("DO NOTHING", RECOMMENDATION_UPSERT_SQL)

    def test_same_version_keeps_the_stored_year(self):
        when = datetime(2026, 1, 1, tzinfo=timezone.utc)
        later = datetime(2026, 6, 1, tzinfo=timezone.utc)
        original = normalize_guideline(_guideline(1, year=2018))
        self.assertEqual(upsert_guideline(self.conn, original, when), "inserted")
        self.conn.commit()
        changed_year = normalize_guideline(_guideline(1, year=2024))
        self.assertEqual(upsert_guideline(self.conn, changed_year, later), "unchanged")
        self.conn.commit()
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT version, publication_year, source_retrieved_at FROM cpic_guideline WHERE id = %s",
                (GUIDELINE_ID,),
            )
            version, year, retrieved = cur.fetchone()
        self.assertEqual(version, 1)
        self.assertEqual(year, 2018)
        self.assertEqual(retrieved, when)

    def test_higher_version_updates_and_refreshes_recommendations(self):
        async def run(guidelines, recommendations):
            client = _FakeClient(guidelines, recommendations)
            summary = await ingest_cpic(self.url, drugs=[TEST_DRUG], client=client)
            return client, summary

        client, first = asyncio.run(
            run([_guideline(1, year=2018)], {TEST_DRUG: [_recommendation(RECOMMENDATION_IDS[0])]})
        )
        self.assertEqual(first["guidelines_inserted"], 1)
        self.assertEqual(first["recommendations_inserted"], 1)
        self.assertEqual(client.recommendation_calls, [TEST_DRUG])

        client, second = asyncio.run(
            run(
                [_guideline(1, year=2024)],
                {TEST_DRUG: [_recommendation(RECOMMENDATION_IDS[0], lookup="should-not-land")]},
            )
        )
        self.assertEqual(second["guidelines_unchanged"], 1)
        self.assertEqual(second["drugs_refreshed"], 0)
        self.assertEqual(client.recommendation_calls, [])
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT publication_year FROM cpic_guideline WHERE id = %s",
                (GUIDELINE_ID,),
            )
            self.assertEqual(cur.fetchone()[0], 2018)
            cur.execute(
                "SELECT lookupkey FROM cpic_recommendation WHERE recommendationid = %s",
                (RECOMMENDATION_IDS[0],),
            )
            self.assertEqual(cur.fetchone()[0], {"CYP2C19": "Poor Metabolizer"})

        client, third = asyncio.run(
            run([_guideline(2, year=2025)], {TEST_DRUG: [_recommendation(RECOMMENDATION_IDS[1])]})
        )
        self.assertEqual(third["guidelines_updated"], 1)
        self.assertEqual(third["recommendations_inserted"], 1)
        self.assertEqual(third["recommendations_removed"], 1)
        self.assertEqual(client.recommendation_calls, [TEST_DRUG])
        with self.conn.cursor() as cur:
            cur.execute("SELECT version, publication_year FROM cpic_guideline WHERE id = %s", (GUIDELINE_ID,))
            self.assertEqual(cur.fetchone(), (2, 2025))
            cur.execute(
                "SELECT recommendationid FROM cpic_recommendation WHERE drugname = %s ORDER BY recommendationid",
                (TEST_DRUG,),
            )
            self.assertEqual([row[0] for row in cur.fetchall()], [RECOMMENDATION_IDS[1]])

    def test_identical_recommendation_is_not_rewritten(self):
        row = normalize_recommendation(_recommendation(RECOMMENDATION_IDS[0]))
        first_at = datetime(2026, 2, 2, tzinfo=timezone.utc)
        second_at = datetime(2026, 3, 3, tzinfo=timezone.utc)
        self.assertEqual(upsert_recommendation(self.conn, row, first_at), "inserted")
        self.assertEqual(upsert_recommendation(self.conn, row, second_at), "unchanged")
        self.conn.commit()
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT source_retrieved_at FROM cpic_recommendation WHERE recommendationid = %s",
                (RECOMMENDATION_IDS[0],),
            )
            self.assertEqual(cur.fetchone()[0], first_at)

    def test_loader_reads_kb_pgx_without_changing_it(self):
        names = load_drug_names(self.conn)
        self.assertGreater(len(names), 0)
        self.assertEqual(self._kb_count(), self._kb_before)
