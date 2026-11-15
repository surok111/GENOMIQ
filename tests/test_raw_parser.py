"""Raw lab dump → same gene dicts as parse_patient_report."""
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from html_report import generate_html_report
from interpreter import interpret_gene, load_base, build_gene_index, parse_patient_report
from raw_parser import looks_like_raw_lab, parse_raw_lab_report


SAMPLE = ROOT / "samples" / "raw_lab_output.txt"
SAMPLE_V2 = ROOT / "samples" / "raw_lab_output_v2.txt"
SAMPLE_HELL = ROOT / "samples" / "raw_lab_output_hell.txt"


class RawParserTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SAMPLE.read_text(encoding="utf-8")
        cls.text_v2 = SAMPLE_V2.read_text(encoding="utf-8")
        cls.text_hell = SAMPLE_HELL.read_text(encoding="utf-8")
        cls.base = load_base(str(ROOT / "data/parsed_knowledge_base_clean.json"))
        cls.index = build_gene_index(cls.base)

    def test_detects_vcf_header(self):
        self.assertTrue(looks_like_raw_lab(self.text, str(SAMPLE)))
        self.assertTrue(looks_like_raw_lab(self.text_v2, str(SAMPLE_V2)))
        self.assertTrue(looks_like_raw_lab(self.text_hell, str(SAMPLE_HELL)))
        self.assertFalse(looks_like_raw_lab("Ген: MTHFR\nРезультат: TT\n"))
        garbage_then_chrom = "asdfghjkl 12345 !@#$%\n#CHROM\tPOS\tID\tREF\tALT\n"
        self.assertTrue(looks_like_raw_lab(garbage_then_chrom))

    def test_extracts_key_genes(self):
        genes = {p["gene"]: p["result"] for p in parse_raw_lab_report(self.text)}
        self.assertEqual(len(genes), 8)
        self.assertEqual(genes["CYP2C19"], "*1/*2")
        self.assertEqual(genes["MTHFR"], "TT")
        self.assertEqual(genes["F5"], "CT")
        self.assertEqual(genes["APOE"], "E3/E4")
        self.assertEqual(genes["SLCO1B1"], "TC")
        self.assertEqual(genes["NQO1"], "CT")
        self.assertEqual(genes["CYP2C9"], "*1/*2")
        self.assertEqual(genes["KARYOTYPE"], "46,XX,t(9;22)(q34;q11.2)")

    def test_v2_logs_and_text_summary(self):
        patients = parse_raw_lab_report(self.text_v2)
        genes = {p["gene"]: p["result"] for p in patients}
        self.assertEqual(genes["CYP2C19"], "*1/*2")
        self.assertEqual(genes["CYP2C9"], "*1/*2")
        self.assertEqual(genes["MTHFR"], "TT")
        self.assertEqual(genes["F5"], "CT")
        self.assertEqual(genes["APOE"], "E3/E4")
        self.assertIn("VKORC1", genes)
        self.assertNotIn("BRCA1", genes)
        self.assertEqual(len(patients), len(genes))  # no duplicate gene rows

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

    def test_v2_interpret_key_genes(self):
        patients = parse_raw_lab_report(self.text_v2)
        statuses = {p["gene"]: interpret_gene(p, self.index)["status"] for p in patients}
        for gene in ("CYP2C19", "CYP2C9", "MTHFR", "F5", "APOE"):
            self.assertIn(
                statuses[gene],
                {"matched", "matched_annotation_only", "no_genotype_match"},
                msg=f"{gene} -> {statuses[gene]}",
            )
        if "VKORC1" in statuses:
            self.assertIn(
                statuses["VKORC1"],
                {"not_in_knowledge_base", "no_genotype_match", "matched_annotation_only", "matched"},
            )

    def test_garbage_input(self):
        garbage = "asdfghjkl 12345 !@#$%"
        result = parse_raw_lab_report(garbage)
        self.assertEqual(result, [])
        self.assertEqual(parse_raw_lab_report(""), [])
        self.assertEqual(parse_raw_lab_report(None), [])  # type: ignore[arg-type]

    def test_parse_performance_10k_vcf(self):
        known = [
            ("rs4244285", "G", "A", "0/1"),
            ("rs1801133", "C", "T", "1/1"),
            ("rs6025", "C", "T", "0/1"),
            ("rs1799853", "C", "T", "0/1"),
        ]
        lines = [
            "##fileformat=VCFv4.2",
            "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSAMPLE",
        ]
        for i in range(10000):
            if i % 20 == 0:
                rsid, ref, alt, gt = known[i % len(known)]
            else:
                rsid, ref, alt, gt = f"rs{1_000_000 + i}", "A", "G", "0/0"
            chrom = (i % 22) + 1
            lines.append(
                f"{chrom}\t{1000 + i}\t{rsid}\t{ref}\t{alt}\t99\tPASS\tDP=30\tGT\t{gt}"
            )
        text = "\n".join(lines)
        t0 = time.time()
        genes = parse_raw_lab_report(text)
        elapsed = time.time() - t0
        self.assertLess(elapsed, 2.0, f"parser took {elapsed:.3f}s for 10k VCF lines")
        names = {p["gene"] for p in genes}
        self.assertIn("CYP2C19", names)

    def test_weird_genotypes(self):
        text = """##fileformat=VCFv4.2
#CHROM	POS	ID	REF	ALT	QUAL	FILTER	INFO	FORMAT	SAMPLE
16	69720998	rs1800566	C	T	95	PASS	DP=30	GT	./.
10	96541616	rs4244285	G	A	99	PASS	DP=45	GT	0|1
1	169519049	rs6025	C	T	99	PASS	DP=55	GT	1/2
"""
        genes = {p["gene"]: p for p in parse_raw_lab_report(text)}
        self.assertNotIn("NQO1", genes)
        self.assertIn("CYP2C19", genes)
        self.assertEqual(genes["CYP2C19"]["result"], "*1/*2")
        if "F5" in genes:
            self.assertIn(genes["F5"]["result"], {"CT", "C/T", "TC"})

    def test_unknown_genes(self):
        self.assertNotIn("VKORC1", self.index)
        text = "##fileformat=VCFv4.2\nVKORC1: -1639 G>A\n"
        patients = parse_raw_lab_report(text)
        self.assertTrue(any(p["gene"] == "VKORC1" for p in patients))
        results = [interpret_gene(p, self.index) for p in patients]
        vkor = next(r for r in results if r["gene"] == "VKORC1")
        self.assertEqual(vkor["status"], "not_in_knowledge_base")
        rep = {
            "file": "unknown_genes.txt",
            "stats": {
                "matched": 0,
                "matched_annotation_only": 0,
                "no_genotype_match": 0,
                "not_in_knowledge_base": 1,
            },
            "results": results,
        }
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "report.html"
            generate_html_report(rep, str(out))
            html = out.read_text(encoding="utf-8")
        self.assertIn("missing_genes", html)
        self.assertIn("VKORC1", html)

    def test_hell_file(self):
        self.assertTrue(looks_like_raw_lab(self.text_hell, str(SAMPLE_HELL)))
        patients = parse_raw_lab_report(self.text_hell)
        genes = {p["gene"]: p["result"] for p in patients}
        self.assertEqual(len(patients), len(genes))
        for gene in ("CYP2C19", "MTHFR", "F5", "NQO1", "CYP2C9", "VKORC1"):
            self.assertIn(gene, genes, msg=f"missing {gene}: {genes}")
        self.assertNotIn("BRCA1", genes)
        self.assertFalse(any("asdfghjkl" in (p["gene"] + p["result"]).lower() for p in patients))
        glued = parse_patient_report(
            "Ген: F5\nРезультат: CT\nCYP3A5 : *1/*3\n================\n"
        )
        self.assertEqual(len(glued), 1)
        self.assertEqual(glued[0]["gene"], "F5")
        self.assertEqual(glued[0]["result"], "CT")


if __name__ == "__main__":
    unittest.main()
