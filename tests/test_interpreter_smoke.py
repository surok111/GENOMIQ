"""Smoke tests for parser / interpreter invariants."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from genedb.catalog import extract_gene_symbols
from interpreter import (
    _is_normal,
    _is_star_overlap,
    _normalize,
    _specific_matched_genotype,
    build_gene_index,
    interpret_gene,
    load_base,
)


class InterpreterSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = load_base(str(ROOT / "data/parsed_knowledge_base_clean.json"))
        cls.index = build_gene_index(cls.base)

    def test_hla_drb1_symbol(self):
        self.assertEqual(
            extract_gene_symbols("HLA-DRB1 — Major Histocompatibility Complex")[0],
            "HLA-DRB1",
        )
        self.assertIn("HLA-DRB1", self.index)

    def test_sod2_has_supplement_genotype_table(self):
        sod2 = next(
            g
            for group in self.base
            for g in group["genes"]
            if g["header"].startswith("SOD2")
        )
        titles = [s.get("title", "") for s in sod2["sections"]]
        self.assertTrue(any("SOD2" in t and "дополнение" in t for t in titles))

    def test_normal_phrases(self):
        self.assertFalse(_is_normal("не норма"))
        self.assertTrue(_is_normal("норма"))

    def test_star_allele_no_substring(self):
        self.assertFalse(_is_star_overlap(_normalize("*1"), _normalize("*10/*10")))

    def test_specific_star_genotype_not_whole_cell(self):
        cell = "*1/*2, *1/*3, *2/*17"
        self.assertEqual(_specific_matched_genotype(cell, "*1/*2"), "*1/*2")
        r = interpret_gene(
            {"gene": "CYP2C19", "result": "*1/*2", "comment": ""}, self.index
        )
        self.assertEqual(r["status"], "matched")
        self.assertEqual(r["matched_genotype"], "*1/*2")
        self.assertEqual(r["matches"][0]["genotype"], "*1/*2")
        self.assertEqual(r["matches"][0]["full_row"].get("Генотип"), "*1/*2")
        r9 = interpret_gene(
            {"gene": "CYP2C9", "result": "*1/*2", "comment": ""}, self.index
        )
        self.assertEqual(r9["status"], "matched")
        self.assertEqual(r9["matched_genotype"], "*1/*2")
        self.assertNotIn(",", r9["matched_genotype"])

    def test_no_fuzzy_nat_to_nat2(self):
        r = interpret_gene({"gene": "NAT", "result": "CC", "comment": ""}, self.index)
        self.assertEqual(r["status"], "not_in_knowledge_base")

    def test_nqo1_dedupes_and_filters_omim_recs(self):
        r = interpret_gene(
            {"gene": "NQO1", "result": "CT", "comment": "rs1800566 C>T"},
            self.index,
        )
        self.assertEqual(r["status"], "matched")
        self.assertEqual(len(r["matches"]), 1, msg=r["matches"])
        self.assertNotIn(",", r["matched_genotype"])
        recs = r["recommendations"]
        self.assertTrue(recs)
        blob = " ".join(recs).lower()
        self.assertNotIn("jaiswal", blob)
        self.assertNotIn("мыши", blob)
        self.assertNotIn("pmid", blob)
        self.assertNotIn("in vitro", blob)
        for item in recs:
            self.assertLessEqual(len(item), 300)
        if recs == ["Специфических рекомендаций нет"]:
            self.assertEqual(recs[0], "Специфических рекомендаций нет")

    def test_why_evidence_for_cyp2c19(self):
        import tempfile
        from html_report import generate_html_report

        r = interpret_gene(
            {
                "gene": "CYP2C19",
                "result": "*1/*2",
                "comment": "rs4244285 G/A (GT=0/1)",
            },
            self.index,
        )
        self.assertEqual(r["status"], "matched")
        why = r["why"]
        self.assertIn("Intermediate Metabolizer", why["sentence"])
        self.assertIn("CPIC", why["source"])
        self.assertIn("Clopidogrel", why["source"])
        self.assertIn("rs4244285", why["evidence"])
        self.assertIn("G>A", why["evidence"])
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "why.html"
            generate_html_report(
                {
                    "file": "why.txt",
                    "stats": {"matched": 1, "not_in_knowledge_base": 0},
                    "results": [r],
                },
                str(out),
            )
            html = out.read_text(encoding="utf-8")
        self.assertIn("Why?", html)
        self.assertIn("rs4244285", html)
        self.assertIn("CPIC Guideline for Clopidogrel", html)


if __name__ == "__main__":
    unittest.main()
