"""Stage 1: classification, genotype normalization, provenance, validation."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pgx_normalize import (  # noqa: E402
    build_normalization,
    classify_table,
    normalize_knowledge_base,
    parse_genotype_cell,
    parse_star_diplotype,
)
from md_parser import parse_file  # noqa: E402

SOURCE = ROOT / "data" / "group5_pharmaco.txt"


def load_group():
    parsed = parse_file(str(SOURCE))
    groups, warnings, errors = normalize_knowledge_base([parsed])
    return groups[0], warnings, errors


class ClassificationTest(unittest.TestCase):
    def test_table_kinds(self):
        self.assertEqual(
            classify_table(["Генотип", "Фенотип", "Функция", "Клинический риск", "ACMG"]),
            "genotype_reference",
        )
        self.assertEqual(
            classify_table(["Препарат", "Генотип", "Рекомендация", "Источник"]),
            "drug_recommendation",
        )
        self.assertEqual(
            classify_table(["Препарат", "Генотип", "Эффект", "Источник"]),
            "drug_recommendation",
        )
        self.assertEqual(classify_table(["Параметр", "Описание"]), "identity_reference")
        self.assertEqual(classify_table(["Субстраты", "Влияние генотипа"]), "substrate_reference")
        # A phenotype table that mentions a drug only inside a cell is not a drug table.
        self.assertEqual(
            classify_table(["Генотип", "Фенотип", "Клинический риск"]),
            "genotype_reference",
        )

    def test_group5_separates_every_source_table(self):
        group, warnings, errors = load_group()
        self.assertEqual(errors, [])
        self.assertEqual(group["normalization_schema"], 1)
        roles = {}
        for gene in group["genes"]:
            norm = gene["normalization"]
            self.assertEqual(norm["schema_version"], 1)
            self.assertEqual(norm["source_file"], "group5_pharmaco.txt")
            self.assertTrue(norm["use_exact_matcher"])
            roles[norm["symbol"]] = {
                "genotype_rows": sum(1 for r in norm["reference_tables"] if r["role"] == "genotype_phenotype"),
                "drugs": len(norm["drug_recommendations"]),
                "identity": sum(1 for r in norm["reference_tables"] if r["role"] == "identity"),
                "substrate": sum(1 for r in norm["reference_tables"] if r["role"] == "substrate"),
            }
        self.assertEqual(roles["CYP2C9"]["genotype_rows"], 3)
        self.assertEqual(roles["CYP2C9"]["drugs"], 12)
        self.assertGreaterEqual(roles["CYP2C9"]["identity"], 1)
        self.assertEqual(roles["CYP2C19"]["genotype_rows"], 4)
        self.assertEqual(roles["CYP2C19"]["drugs"], 12)
        self.assertEqual(roles["CYP2D6"]["genotype_rows"], 4)
        self.assertEqual(roles["CYP2D6"]["drugs"], 24)
        self.assertGreaterEqual(roles["CYP2D6"]["substrate"], 1)
        self.assertEqual(roles["CYP1A2"]["genotype_rows"], 3)
        self.assertEqual(roles["CYP1A2"]["drugs"], 8)
        self.assertEqual(roles["SLCO1B1"]["genotype_rows"], 3)
        self.assertEqual(roles["SLCO1B1"]["drugs"], 10)
        self.assertEqual(sum(v["drugs"] for v in roles.values()), 66)

    def test_original_cells_are_not_rewritten(self):
        group, _warnings, _errors = load_group()
        cyp2c9 = next(g for g in group["genes"] if g["normalization"]["symbol"] == "CYP2C9")
        phenotype = next(
            r for r in cyp2c9["normalization"]["reference_tables"]
            if r["role"] == "genotype_phenotype" and "*3/*3" in r["genotype_raw"] and "*2/*2" in r["genotype_raw"]
        )
        self.assertIn("siponimod", phenotype["risk_raw"].lower())
        self.assertIn("*3/*3", phenotype["risk_raw"])
        self.assertEqual(phenotype["row"]["Генотип"], "*2/*2, *2/*3, *3/*3")
        # The parser's tables[] copy is the same source row.
        self.assertIn(phenotype["row"], cyp2c9["sections"][2]["tables"][0]["rows"])

    def test_provenance_points_at_group5(self):
        group, _w, _e = load_group()
        slco = next(g for g in group["genes"] if g["normalization"]["symbol"] == "SLCO1B1")
        simva = [
            d for d in slco["normalization"]["drug_recommendations"]
            if "Симвастатин" in d["drug_raw"] and "*5/*5" in d["genotype_raw"]
        ]
        self.assertEqual(len(simva), 1)
        prov = simva[0]["provenance"]
        self.assertEqual(prov["file"], "group5_pharmaco.txt")
        self.assertEqual(prov["gene"], "SLCO1B1")
        self.assertEqual(prov["section_code"], "5.3")
        self.assertEqual(simva[0]["recommendation_raw"], "**Не применять 80 мг**; рассмотреть альтернативу")

    def test_identity_variants_survive(self):
        group, _w, _e = load_group()
        by_symbol = {g["normalization"]["symbol"]: g["normalization"]["variants"] for g in group["genes"]}
        cyp2c9 = {v["rsid"]: v for v in by_symbol["CYP2C9"]}
        self.assertEqual(cyp2c9["rs1799853"]["star"], "*2")
        self.assertEqual(cyp2c9["rs1057910"]["star"], "*3")
        cyp2c19 = {v["rsid"]: v["star"] for v in by_symbol["CYP2C19"]}
        self.assertEqual(cyp2c19["rs4244285"], "*2")
        self.assertEqual(cyp2c19["rs4986893"], "*3")
        self.assertEqual(cyp2c19["rs12248560"], "*17")
        self.assertTrue(any(v["rsid"] == "rs762551" for v in by_symbol["CYP1A2"]))
        self.assertTrue(any(v["rsid"] == "rs4149056" for v in by_symbol["SLCO1B1"]))
        # CYP2D6 has no rsID table in the source. Nothing is invented.
        self.assertEqual(by_symbol["CYP2D6"], [])

    def test_substrate_table_is_preserved(self):
        group, _w, _e = load_group()
        cyp2d6 = next(g for g in group["genes"] if g["normalization"]["symbol"] == "CYP2D6")
        substrate_rows = [r for r in cyp2d6["normalization"]["reference_tables"] if r["role"] == "substrate"]
        texts = " ".join(str(r["row"]) for r in substrate_rows)
        self.assertIn("Кодеин", texts)
        self.assertIn("Тамоксифен", texts)

    def test_repeated_normalization_is_deterministic(self):
        parsed = parse_file(str(SOURCE))
        first, w1, e1 = normalize_knowledge_base([json.loads(json.dumps(parsed))])
        second, w2, e2 = normalize_knowledge_base([json.loads(json.dumps(parsed))])
        self.assertEqual(e1, e2)
        self.assertEqual(
            json.dumps(first, ensure_ascii=False, sort_keys=True),
            json.dumps(second, ensure_ascii=False, sort_keys=True),
        )
        self.assertEqual(
            json.dumps(w1, ensure_ascii=False, sort_keys=True),
            json.dumps(w2, ensure_ascii=False, sort_keys=True),
        )


class GenotypeParseTest(unittest.TestCase):
    def test_copy_number_is_not_reduced(self):
        parsed = parse_star_diplotype("*1/*1xN")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["normalized"], "*1/*1xn")
        self.assertEqual(parsed["alleles"][1]["copy"].lower(), "xn")
        plain = parse_star_diplotype("*1/*1")
        self.assertNotEqual(parsed["key"], plain["key"])

    def test_allele_order_key_is_stable(self):
        self.assertEqual(parse_star_diplotype("*1/*2")["key"], parse_star_diplotype("*2/*1")["key"])
        self.assertNotEqual(parse_star_diplotype("*1/*2")["normalized"], parse_star_diplotype("*2/*1")["normalized"])

    def test_star_ten_is_not_star_one(self):
        self.assertNotEqual(parse_star_diplotype("*1/*1")["key"], parse_star_diplotype("*10/*10")["key"])

    def test_composite_and_alias_cells(self):
        im = parse_genotype_cell("*1/*2, *1/*3, *1/*5")
        self.assertEqual([t["raw"] for t in im["tokens"]], ["*1/*2", "*1/*3", "*1/*5"])
        narrowed = parse_genotype_cell("PM (*3/*3)")
        self.assertEqual(narrowed["scope"], "genotype")
        self.assertEqual(narrowed["tokens"][0]["raw"], "*3/*3")
        self.assertEqual(narrowed["phenotype_codes"], ["PM"])
        union = parse_genotype_cell("IM / PM")
        self.assertEqual(union["scope"], "phenotype")
        self.assertEqual(union["phenotype_codes"], ["IM", "PM"])
        both = parse_genotype_cell("*5/*5, *15/*15, *5/*15 (521 CC)")
        self.assertEqual([t["raw"] for t in both["tokens"]], ["*5/*5", "*15/*15", "*5/*15"])
        self.assertEqual(both["aliases"][0]["normalized"], "CC")
        only_alias = parse_genotype_cell("521 CC")
        self.assertEqual(only_alias["scope"], "genotype")
        self.assertEqual(only_alias["aliases"][0]["key"], ["NT:CC"])
        pair = parse_genotype_cell("AC + CC")
        self.assertEqual([t["normalized"] for t in pair["tokens"]], ["AC", "CC"])
        variants = parse_genotype_cell("rs2069526, rs4646425")
        self.assertEqual(variants["scope"], "variant")
        self.assertEqual(parse_genotype_cell("—")["scope"], "none")
        self.assertEqual(parse_genotype_cell("Все")["scope"], "all")
        conditional = parse_genotype_cell("PM (двойной с UGT2B17)")
        self.assertEqual(conditional["scope"], "conditional")
        self.assertIn("UGT2B17", conditional["condition"])
        labeled = parse_genotype_cell("TT (521 TT)")
        self.assertEqual(labeled["tokens"][0]["normalized"], "TT")
        self.assertEqual(labeled["aliases"][0]["normalized"], "TT")

    def test_copy_number_cell_keeps_both_diplotypes(self):
        cell = parse_genotype_cell("*1/*1xN, *1/*2xN")
        self.assertEqual([t["normalized"] for t in cell["tokens"]], ["*1/*1xn", "*1/*2xn"])
        self.assertNotIn("*1/*1", [t["normalized"] for t in cell["tokens"]])


class ValidationTest(unittest.TestCase):
    def test_known_source_warnings_are_explicit(self):
        _group, warnings, errors = load_group()
        self.assertEqual(errors, [])
        codes = {w["code"] for w in warnings}
        self.assertIn("risk_names_narrower_genotype", codes)
        self.assertIn("combined_phenotype_label", codes)
        self.assertIn("conditional_recommendation_not_evaluated", codes)
        self.assertIn("drug_genotype_not_in_reference", codes)
        self.assertIn("drug_variant_not_a_diplotype", codes)
        self.assertIn("bullet_without_genotype_association", codes)
        self.assertIn("genotype_absent_from_bullets", codes)
        # *2/*17 stays on the intermediate row the source wrote. The function
        # sentence is not used to move it, because *2 is a normal allele in
        # other genes and the file does not define a rewrite rule.
        combined = next(w for w in warnings if w["code"] == "combined_phenotype_label")
        self.assertEqual(combined["provenance"]["gene"], "CYP2C19")
        self.assertEqual(combined["provenance"]["section_code"], "2.3")

    def test_conflicting_normalized_entries_warn_and_do_not_drop_rows(self):
        gene = {
            "header": "EXAMPLE — structural fixture",
            "sections": [{
                "code": "9.1",
                "title": "fixture",
                "tables": [
                    {
                        "headers": ["Генотип", "Фенотип", "Функция", "Клинический риск", "ACMG"],
                        "rows": [
                            {"Генотип": "*1/*1", "Фенотип": "Normal Metabolizer (NM)", "Функция": "", "Клинический риск": "a", "ACMG": "Benign"},
                            {"Генотип": "*1/*1", "Фенотип": "Poor Metabolizer (PM)", "Функция": "", "Клинический риск": "b", "ACMG": "Pathogenic"},
                        ],
                    },
                    {
                        "headers": ["Препарат", "Генотип", "Рекомендация", "Источник"],
                        "rows": [{
                            "Препарат": "FixtureDrug",
                            "Генотип": "*1/*1",
                            "Рекомендация": "fixture-recommendation",
                            "Источник": "fixture",
                        }],
                    },
                ],
                "other_tables": [],
                "pharmacogenomics": [],
                "bullets": [],
                "text": "",
            }],
        }
        norm = build_normalization(gene, "fixture.txt", "fixture")
        self.assertTrue(any(w["code"] == "conflicting_genotype" for w in norm["warnings"]))
        self.assertEqual(sum(1 for r in norm["reference_tables"] if r["role"] == "genotype_phenotype"), 2)
        self.assertEqual(norm["drug_recommendations"][0]["recommendation_raw"], "fixture-recommendation")

    def test_ambiguous_table_is_kept_for_review(self):
        gene = {
            "header": "EXAMPLE — structural fixture",
            "sections": [{
                "code": "9.2",
                "title": "fixture",
                "tables": [{
                    "headers": ["Препарат", "Комментарий"],
                    "rows": [{"Препарат": "FixtureDrug", "Комментарий": "no genotype column"}],
                }],
                "other_tables": [],
                "pharmacogenomics": [],
                "bullets": [],
                "text": "",
            }],
        }
        norm = build_normalization(gene, "fixture.txt", "fixture")
        self.assertEqual(len(norm["review_tables"]), 1)
        self.assertEqual(norm["review_tables"][0]["rows"][0]["Комментарий"], "no genotype column")
        self.assertTrue(any(w["code"] == "ambiguous_table_classification" for w in norm["warnings"]))
        self.assertEqual(norm["errors"], [])


if __name__ == "__main__":
    unittest.main()
