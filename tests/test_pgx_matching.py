"""Stage 2 and 3: exact matching, scope filtering, and the group 5 pipeline."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from interpreter import build_gene_index, extract_genotype_candidates, interpret_gene  # noqa: E402
from md_parser import parse_file  # noqa: E402
from pgx_normalize import normalize_knowledge_base  # noqa: E402

SOURCE = ROOT / "data" / "group5_pharmaco.txt"


def make_index():
    parsed = parse_file(str(SOURCE))
    groups, _warnings, errors = normalize_knowledge_base([parsed])
    if errors:
        raise AssertionError(errors)
    return build_gene_index(groups)


def run(index, gene, result, comment=""):
    return interpret_gene({"gene": gene, "result": result, "comment": comment}, index)


def drug_names(result):
    names = []
    for row in result.get("drug_recommendations") or []:
        names.extend(row.get("drugs") or [])
    return names


def excluded_drugs(result):
    return [(row.get("drug_raw"), row.get("genotype_raw"), row.get("match_reason")) for row in result.get("excluded_recommendations") or [] if "drug_raw" in row]


class CopyNumberTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = make_index()

    def test_extractor_does_not_emit_plain_star_for_copy_number(self):
        candidates = extract_genotype_candidates("*1/*1xN")
        self.assertIn("*1/*1xN", candidates)
        self.assertNotIn("*1/*1", candidates)

    def test_star_one_does_not_match_copy_number_row(self):
        result = run(self.index, "CYP2D6", "*1/*1")
        self.assertEqual(result["status"], "matched")
        self.assertEqual(result["match_quality"], "exact")
        self.assertEqual(result["matched_genotype"], "*1/*1")
        self.assertIn("Normal Metabolizer", result["phenotype_label"])
        self.assertNotIn("xN", result["matched_genotype"])
        self.assertNotIn("Ultra-rapid", result["phenotype_label"])
        joined = " ".join(drug_names(result))
        self.assertNotIn("Кодеин", joined)
        self.assertNotIn("Трам", joined)
        # Source drug table has no NM row. Nothing is substituted.
        self.assertEqual(result["drug_recommendations"], [])

    def test_copy_number_does_not_match_normal_metabolizer(self):
        result = run(self.index, "CYP2D6", "*1/*1xN")
        self.assertEqual(result["status"], "matched")
        self.assertEqual(result["matched_genotype"], "*1/*1xN")
        self.assertEqual(result["match_quality"], "exact")
        self.assertIn("Ultra-rapid", result["phenotype_label"])
        self.assertNotIn("Normal Metabolizer", result["phenotype_label"])
        self.assertEqual(result["normalized_genotype"]["alleles"][1]["copy"].lower(), "xn")
        names = " ".join(drug_names(result))
        self.assertIn("Кодеин", names)
        self.assertIn("Элиглустат", names)
        reasons = {tuple(row["drugs"]): row["genotype_raw"] for row in result["drug_recommendations"]}
        self.assertEqual(reasons[("Кодеин",)], "UM")
        self.assertNotIn("Тиоридазин", names)
        # PM codeine row is a different recommendation and must stay out.
        self.assertTrue(all(row["genotype_raw"] == "UM" or row["scope"] == "all" for row in result["drug_recommendations"]))
        self.assertEqual(result["matches"][0]["provenance"]["file"], "group5_pharmaco.txt")
        self.assertEqual(result["matches"][0]["provenance"]["section_code"], "3.3")

    def test_other_copy_number_form_in_source(self):
        result = run(self.index, "CYP2D6", "*1/*2xN")
        self.assertEqual(result["matched_genotype"], "*1/*2xN")
        self.assertIn("Ultra-rapid", result["phenotype_label"])
        self.assertNotEqual(result["matched_genotype"], "*1/*2")

    def test_reversed_star_order_is_equivalent_not_a_different_genotype(self):
        result = run(self.index, "CYP2D6", "*2/*1")
        self.assertEqual(result["status"], "matched")
        self.assertEqual(result["match_quality"], "equivalent_order")
        self.assertEqual(result["matched_genotype"], "*1/*2")
        self.assertIn("Normal Metabolizer", result["phenotype_label"])


class Cyp2c9Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = make_index()

    def test_normal_excludes_intermediate_and_poor_recommendations(self):
        result = run(self.index, "CYP2C9", "*1/*1")
        self.assertEqual(result["phenotype_codes"], ["NM"])
        self.assertEqual(result["drug_recommendations"], [])
        bullets = " ".join(result["recommendations"])
        self.assertIn("*1/*1", bullets)
        self.assertNotIn("*2/*2", bullets)
        self.assertNotIn("варфарина", bullets.lower())

    def test_intermediate_uses_source_row_and_filters_drugs(self):
        result = run(self.index, "CYP2C9", "*1/*3")
        self.assertEqual(result["matched_genotype"], "*1/*3")
        self.assertEqual(result["phenotype_codes"], ["IM"])
        self.assertNotIn(",", result["matched_genotype"])
        self.assertEqual(result["matches"][0]["full_row"]["Генотип"], "*1/*3")
        names = drug_names(result)
        self.assertIn("Варфарин", names)
        self.assertIn("Фенитоин", names)
        self.assertIn("Siponimod", names)
        # *3/*3-only rows. Source: celecoxib PM (*3/*3), siponimod contraindication, erdafitinib.
        self.assertNotIn("Celecoxib", names)
        self.assertNotIn("Erdafitinib", names)
        sip = [row for row in result["drug_recommendations"] if "Siponimod" in row["drugs"]]
        self.assertEqual(len(sip), 1)
        self.assertEqual(sip[0]["genotype_raw"], "*1/*3, *2/*3")
        self.assertNotIn("ПРОТИВОПОКАЗАН", sip[0]["recommendation_raw"])
        bullets = " ".join(result["recommendations"])
        self.assertIn("*1/*3", bullets)
        self.assertNotIn("*2/*2", bullets)

    def test_poor_star3_homozygote_keeps_contraindication_on_that_genotype(self):
        result = run(self.index, "CYP2C9", "*3/*3")
        self.assertEqual(result["phenotype_codes"], ["PM"])
        names = drug_names(result)
        self.assertIn("Celecoxib", names)
        self.assertIn("Deuruxolitinib", names)
        sip = [row for row in result["drug_recommendations"] if row["drugs"] == ["Siponimod"]]
        self.assertEqual([row["genotype_raw"] for row in sip], ["*3/*3"])
        self.assertIn("ПРОТИВОПОКАЗАН", sip[0]["recommendation_raw"])
        self.assertEqual(sip[0]["provenance"]["section_code"], "1.3")

    def test_other_poor_diplotype_does_not_receive_star3_only_drug_row(self):
        result = run(self.index, "CYP2C9", "*2/*2")
        self.assertEqual(result["phenotype_codes"], ["PM"])
        sip = [row for row in result["drug_recommendations"] if "Siponimod" in row["drugs"]]
        self.assertEqual([row["genotype_raw"] for row in sip], [])
        self.assertIn("Deuruxolitinib", drug_names(result))
        self.assertNotIn("Celecoxib", drug_names(result))

    def test_star1_star5_is_the_table_row_not_the_shorter_bullet(self):
        result = run(self.index, "CYP2C9", "*1/*5")
        self.assertEqual(result["phenotype_codes"], ["IM"])
        bullets = " ".join(result["recommendations"])
        # Section 1.2 lists *1/*2 and *1/*3 only.
        self.assertNotIn("*1/*2, *1/*3", bullets)
        self.assertEqual(result["recommendations"], [])
        self.assertIn("Варфарин", drug_names(result))

    def test_rsid_without_diplotype_is_unresolved(self):
        result = run(self.index, "CYP2C9", "rs1799853 гетерозигота")
        self.assertEqual(result["status"], "no_genotype_match")
        self.assertEqual(result["match_quality"], "unresolved")
        self.assertIsNone(result["matched_genotype"])
        self.assertEqual(result["drug_recommendations"], [])
        self.assertIn("rs1799853", result["note"])
        self.assertIn("*2", result["note"])

    def test_comment_does_not_import_another_genotype(self):
        result = run(self.index, "CYP2C9", "*1/*1", comment="*3/*3 противопоказан siponimod")
        self.assertEqual(result["drug_recommendations"], [])
        self.assertEqual(result["phenotype_codes"], ["NM"])


class Cyp2c19Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = make_index()

    def test_star2_star17_uses_the_reference_row_that_lists_it(self):
        result = run(self.index, "CYP2C19", "*2/*17")
        self.assertEqual(result["status"], "matched")
        self.assertEqual(result["matched_genotype"], "*2/*17")
        self.assertEqual(result["phenotype_codes"], ["IM"])
        self.assertIn("Intermediate", result["phenotype_label"])
        self.assertEqual(result["matches"][0]["provenance"]["section_code"], "2.3")
        names = drug_names(result)
        self.assertIn("Клопидогрел", names)
        self.assertNotIn("Циталопрам", names)
        # The bullet says «медленные (*2, *3)» and does not name *2/*17.
        self.assertTrue(all("*2, *3" not in text for text in result["recommendations"]))
        unresolved = " ".join(item["text"] for item in result["unresolved_recommendations"])
        self.assertIn("Медленные метаболисты (*2, *3)", unresolved)

    def test_poor_metabolizer_drug_scope(self):
        result = run(self.index, "CYP2C19", "*2/*2")
        self.assertEqual(result["phenotype_codes"], ["PM"])
        names = drug_names(result)
        self.assertIn("Клопидогрел", names)
        self.assertIn("Циталопрам", names)
        self.assertNotIn("Бельзутифан", names)
        belzu = [
            row for row in result["excluded_recommendations"]
            if "Бельзутифан" in str(row.get("drug_raw", ""))
        ]
        self.assertTrue(belzu)
        self.assertEqual(belzu[0]["match_reason"], "second_gene_not_evaluated")

    def test_combined_rapid_label_does_not_invent_a_single_code(self):
        for genotype in ("*1/*17", "*17/*17"):
            result = run(self.index, "CYP2C19", genotype)
            self.assertEqual(result["matched_genotype"], genotype)
            self.assertEqual(result["phenotype_resolution"], "combined_label")
            self.assertEqual(result["phenotype_codes"], ["RM", "UM"])
            self.assertEqual(result["drug_recommendations"], [])
            self.assertIn("combined phenotype", result["note"])

    def test_normal_does_not_receive_intermediate_or_poor_drugs(self):
        result = run(self.index, "CYP2C19", "*1/*1")
        self.assertEqual(result["phenotype_codes"], ["NM"])
        self.assertEqual(result["drug_recommendations"], [])
        self.assertTrue(any("пролекарство" in text for text in result["recommendations"]))

    def test_unknown_diplotype_selects_nothing(self):
        result = run(self.index, "CYP2C19", "*9/*9")
        self.assertEqual(result["status"], "no_genotype_match")
        self.assertEqual(result["drug_recommendations"], [])
        self.assertEqual(result["match_quality"], "unsupported")


class Cyp1a2Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = make_index()

    def test_each_source_genotype(self):
        aa = run(self.index, "CYP1A2", "AA")
        ac = run(self.index, "CYP1A2", "AC")
        cc = run(self.index, "CYP1A2", "CC")
        self.assertIn("Быстрый", aa["phenotype_label"])
        self.assertIn("Промежуточный", ac["phenotype_label"])
        self.assertIn("Медленный", cc["phenotype_label"])
        self.assertIn("Карбамазепин", drug_names(aa))
        self.assertNotIn("Кофеин", drug_names(aa))
        self.assertNotIn("Карбамазепин", drug_names(ac))
        self.assertIn("Дексмедетомидин", drug_names(ac))
        self.assertIn("Кофеин", drug_names(cc))
        self.assertIn("Дексмедетомидин", drug_names(cc))
        self.assertNotIn("Карбамазепин", drug_names(cc))
        # The bullet explicitly names AC and CC together. The table does not
        # give them the same phenotype; both texts are preserved.
        self.assertTrue(any(text.startswith("AC / CC") for text in ac["recommendations"]))
        self.assertTrue(any("AA (" in text for text in aa["recommendations"]))
        self.assertFalse(any(text.startswith("AA") for text in cc["recommendations"]))

    def test_variant_row_and_ungrounded_drug_are_not_genotype_matches(self):
        result = run(self.index, "CYP1A2", "CC")
        self.assertNotIn("Эсциталопрам", drug_names(result))
        self.assertNotIn("Rucaparib", drug_names(result))
        reasons = {row.get("drug_raw"): row.get("match_reason") for row in result["excluded_recommendations"] if "drug_raw" in row}
        self.assertEqual(reasons["**Эсциталопрам**"], "variant_not_diplotype")
        self.assertEqual(reasons["**Rucaparib**"], "scope_drug_only")

    def test_known_variant_map_matches_only_an_explicit_nucleotide_row(self):
        result = run(self.index, "CYP1A2", "rs762551 гетерозигота")
        self.assertEqual(result["status"], "matched")
        self.assertEqual(result["match_quality"], "known_variant_map")
        self.assertEqual(result["matched_genotype"], "AC")
        self.assertIn("Промежуточный", result["phenotype_label"])
        self.assertNotIn("Кофеин", drug_names(result))


class Slco1b1Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = make_index()

    def test_nucleotide_rows_and_aliases(self):
        tt = run(self.index, "SLCO1B1", "TT")
        tc = run(self.index, "SLCO1B1", "TC")
        cc = run(self.index, "SLCO1B1", "CC")
        self.assertIn("Normal", tt["phenotype_label"])
        self.assertIn("Intermediate", tc["phenotype_label"])
        self.assertIn("Poor", cc["phenotype_label"])
        self.assertEqual(
            [row["drug_raw"] for row in tt["drug_recommendations"]],
            ["**Симвастатин**"],
        )
        self.assertEqual(tt["drug_recommendations"][0]["genotype_raw"], "Все")
        self.assertNotIn("Аторвастатин", drug_names(tc))
        self.assertIn("Симвастатин", drug_names(tc))
        tc_simva = [row for row in tc["drug_recommendations"] if row["genotype_raw"] != "Все"]
        self.assertEqual(len(tc_simva), 1)
        self.assertIn("521 TC", tc_simva[0]["genotype_raw"])
        self.assertIn("Аторвастатин", drug_names(cc))
        self.assertIn("Розувастатин", drug_names(cc))
        self.assertNotIn("Правастатин", drug_names(cc))
        self.assertNotIn("Метотрексат", drug_names(cc))

    def test_parenthetical_alias_matches_without_collapsing_star_alleles(self):
        aliased = run(self.index, "SLCO1B1", "521 CC")
        self.assertEqual(aliased["status"], "matched")
        self.assertEqual(aliased["match_quality"], "explicit_alias")
        self.assertIn("Poor", aliased["phenotype_label"])
        star = run(self.index, "SLCO1B1", "*5/*5")
        self.assertEqual(star["phenotype_resolution"], "not_in_reference_table")
        self.assertEqual(star["phenotype_label"], "")
        self.assertTrue(any("*5/*5" in row["genotype_raw"] for row in star["drug_recommendations"]))
        self.assertNotIn("Аторвастатин", drug_names(star))
        # *23 is a separate source row and is not treated as 521T>C.
        allele = run(self.index, "SLCO1B1", "*23")
        by_drug = {tuple(row["drugs"]): row["genotype_raw"] for row in allele["drug_recommendations"]}
        # §5.3 methotrexate row names *23. The simvastatin «Все» row is explicitly gene-wide.
        self.assertEqual(by_drug[("Метотрексат",)], "*23")
        self.assertEqual(by_drug[("Симвастатин",)], "Все")
        self.assertEqual(set(by_drug), {("Метотрексат",), ("Симвастатин",)})
        self.assertEqual(allele["phenotype_resolution"], "not_in_reference_table")

    def test_orphan_bullets_are_not_applied_to_every_genotype(self):
        tt = run(self.index, "SLCO1B1", "TT")
        self.assertTrue(any(text.startswith("TT ") for text in tt["recommendations"]))
        self.assertFalse(any(text.startswith("Риск:") or text.startswith("Рекомендация:") for text in tt["recommendations"]))
        cc = run(self.index, "SLCO1B1", "CC")
        self.assertFalse(any(text.startswith("TT ") for text in cc["recommendations"]))


class AmbiguousInputTest(unittest.TestCase):
    def test_two_diplotypes_in_one_result_select_nothing(self):
        index = make_index()
        result = run(index, "CYP2C9", "*1/*1, *3/*3")
        self.assertEqual(result["status"], "no_genotype_match")
        self.assertEqual(result["match_quality"], "ambiguous")
        self.assertEqual(result["drug_recommendations"], [])
        self.assertEqual(result["recommendations"], [])

    def test_conflicting_reference_rows_do_not_select_a_recommendation(self):
        gene = {
            "num": 1,
            "header": "EXAMPLE — structural fixture",
            "intro": "",
            "sections": [{
                "code": "9.1",
                "title": "fixture",
                "tables": [
                    {
                        "headers": ["Генотип", "Фенотип", "Функция", "Клинический риск", "ACMG"],
                        "rows": [
                            {"Генотип": "*1/*1", "Фенотип": "Normal Metabolizer (NM)", "Функция": "", "Клинический риск": "row-a", "ACMG": "Benign"},
                            {"Генотип": "*1/*1", "Фенотип": "Poor Metabolizer (PM)", "Функция": "", "Клинический риск": "row-b", "ACMG": "Pathogenic"},
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
        group = {"group": "fixture", "file": "fixture.txt", "intro": "", "genes": [gene], "interactions": {}}
        groups, _warnings, errors = normalize_knowledge_base([group])
        self.assertEqual(errors, [])
        index = build_gene_index(groups)
        result = run(index, "EXAMPLE", "*1/*1")
        self.assertEqual(result["match_quality"], "ambiguous")
        self.assertEqual(result["drug_recommendations"], [])
        self.assertIsNone(result["full_row"])
        self.assertNotIn("fixture-recommendation", " ".join(result["recommendations"]))


class PipelineTest(unittest.TestCase):
    def test_no_source_drug_row_disappears(self):
        parsed = parse_file(str(SOURCE))
        groups, _warnings, errors = normalize_knowledge_base([parsed])
        self.assertEqual(errors, [])
        index = build_gene_index(groups)
        source_rows = []
        for gene in groups[0]["genes"]:
            for record in gene["normalization"]["drug_recommendations"]:
                source_rows.append((gene["normalization"]["symbol"], record["drug_raw"], record["genotype_raw"], record["recommendation_raw"]))
        self.assertEqual(len(source_rows), 66)
        # Every source row is either selected or explicitly excluded for these probes.
        probes = {
            "CYP2C9": "*3/*3",
            "CYP2C19": "*2/*2",
            "CYP2D6": "*4/*4",
            "CYP1A2": "CC",
            "SLCO1B1": "CC",
        }
        for symbol, genotype in probes.items():
            result = run(index, symbol, genotype)
            seen = set()
            for row in result["drug_recommendations"]:
                seen.add((row["drug_raw"], row["genotype_raw"], row["recommendation_raw"]))
            for row in result["excluded_recommendations"]:
                if "drug_raw" not in row:
                    continue
                seen.add((row["drug_raw"], row["genotype_raw"], row["recommendation_raw"]))
            expected = {(d, g, r) for sym, d, g, r in source_rows if sym == symbol}
            self.assertEqual(seen, expected, symbol)

    def test_legacy_gene_without_drug_table_is_not_forced_onto_exact_matcher(self):
        from interpreter import load_base

        base = load_base(str(ROOT / "data" / "parsed_knowledge_base_clean.json"))
        index = build_gene_index(base)
        _group, gene = index["SOD2"]
        self.assertFalse(gene["normalization"]["use_exact_matcher"])


if __name__ == "__main__":
    unittest.main()
