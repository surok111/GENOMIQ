"""Raw lab dump → same gene dicts as parse_patient_report."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from interpreter import interpret_gene, load_base, build_gene_index, parse_patient_report
from raw_parser import looks_like_raw_lab, parse_raw_lab_report


SAMPLE = ROOT / "samples" / "raw_lab_output.txt"


class RawParserTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SAMPLE.read_text(encoding="utf-8")
        cls.base = load_base(str(ROOT / "data/parsed_knowledge_base_clean.json"))
        cls.index = build_gene_index(cls.base)

    def test_detects_vcf_header(self):
        self.assertTrue(looks_like_raw_lab(self.text, str(SAMPLE)))
        self.assertFalse(looks_like_raw_lab("Ген: MTHFR\nРезультат: TT\n"))

    def test_extracts_key_genes(self):
        genes = {p["gene"]: p["result"] for p in parse_raw_lab_report(self.text)}
        self.assertEqual(genes["CYP2C19"], "*1/*2")
        self.assertEqual(genes["MTHFR"], "TT")
        self.assertEqual(genes["F5"], "CT")
        self.assertEqual(genes["APOE"], "E3/E4")
        self.assertEqual(genes["SLCO1B1"], "TC")
        self.assertEqual(genes["NQO1"], "CT")
        self.assertEqual(genes["CYP2C9"], "*1/*2")
        self.assertEqual(genes["KARYOTYPE"], "46,XX,t(9;22)(q34;q11.2)")

    def test_classic_parser_still_ignores_raw_dump(self):
        self.assertEqual(parse_patient_report(self.text), [])

    def test_interpret_statuses(self):
        patients = parse_raw_lab_report(self.text)
        statuses = {p["gene"]: interpret_gene(p, self.index)["status"] for p in patients}
        self.assertEqual(statuses["KARYOTYPE"], "not_in_knowledge_base")
        for gene in ("CYP2C19", "MTHFR", "F5", "APOE", "SLCO1B1", "NQO1", "CYP2C9"):
            self.assertIn(
                statuses[gene],
                {"matched", "matched_annotation_only", "no_genotype_match"},
                msg=f"{gene} -> {statuses[gene]}",
            )


if __name__ == "__main__":
    unittest.main()
