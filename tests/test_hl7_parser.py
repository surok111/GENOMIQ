"""HL7 v2 ORU^R01 → same gene dicts as parse_patient_report."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hl7_parser import looks_like_hl7, parse_hl7_report
from interpreter import parse_patient_input, parse_patient_report
from raw_parser import looks_like_raw_lab, parse_raw_lab_report

SAMPLE = ROOT / "samples" / "sample_oru_r01.hl7"
SAMPLE_VCF = ROOT / "samples" / "raw_lab_output.txt"

DUMMY_HL7 = (
    "MSH|^~\\&|LIS|CityLab|GENOMIQ|API|20261115120000||ORU^R01|MSG1|P|2.5\r"
    "PID|1||PAT-1||Test^Patient||19880312|F\r"
    "OBR|1||SPEC-1|PGX^Pharmacogenetics^L\r"
    "OBX|1|CWE|CYP2C19*2||*1/*2|||N|||F\r"
    "OBX|2|ST|MTHFR||TT|||A|||F\r"
    "OBX|3|CWE|rs6025^F5 Leiden^L||CT|||A|||F\r"
)


class Hl7ParserTest(unittest.TestCase):
    def test_detects_msh_header(self):
        self.assertTrue(looks_like_hl7(DUMMY_HL7))
        self.assertTrue(looks_like_hl7(SAMPLE.read_text(encoding="utf-8"), str(SAMPLE)))
        self.assertFalse(looks_like_hl7("Ген: MTHFR\nРезультат: TT\n"))
        self.assertFalse(looks_like_hl7("##fileformat=VCFv4.2\n#CHROM\tPOS\n"))

    def test_dummy_extracts_at_least_three_genes(self):
        genes = {p["gene"]: p["result"] for p in parse_hl7_report(DUMMY_HL7)}
        self.assertGreaterEqual(len(genes), 3)
        self.assertEqual(genes["CYP2C19"], "*1/*2")
        self.assertEqual(genes["MTHFR"], "TT")
        self.assertEqual(genes["F5"], "CT")

    def test_sample_file_and_dispatch(self):
        text = SAMPLE.read_text(encoding="utf-8")
        genes = {p["gene"]: p["result"] for p in parse_hl7_report(text)}
        self.assertEqual(genes["CYP2C19"], "*1/*2")
        self.assertEqual(genes["MTHFR"], "TT")
        self.assertEqual(genes["F5"], "CT")
        self.assertEqual(genes["NQO1"], "CT")
        self.assertEqual(genes["CYP2C9"], "*1/*2")
        self.assertNotIn("BRCA1", genes)
        dispatched = parse_patient_input(text, str(SAMPLE))
        self.assertEqual({p["gene"] for p in dispatched}, set(genes))

    def test_does_not_steal_vcf_or_classic_text(self):
        vcf = SAMPLE_VCF.read_text(encoding="utf-8")
        self.assertFalse(looks_like_hl7(vcf, str(SAMPLE_VCF)))
        self.assertTrue(looks_like_raw_lab(vcf, str(SAMPLE_VCF)))
        self.assertGreaterEqual(len(parse_raw_lab_report(vcf)), 7)
        classic = "Ген: MTHFR\nРезультат: TT\n"
        self.assertEqual(parse_patient_report(classic)[0]["gene"], "MTHFR")
        self.assertEqual(parse_patient_input(classic)[0]["gene"], "MTHFR")


if __name__ == "__main__":
    unittest.main()
