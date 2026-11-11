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

    def test_no_fuzzy_nat_to_nat2(self):
        r = interpret_gene({"gene": "NAT", "result": "CC", "comment": ""}, self.index)
        self.assertEqual(r["status"], "not_in_knowledge_base")


if __name__ == "__main__":
    unittest.main()
