from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
INPUT_FILE = BASE_DIR / "data" / "input" / "analizy.docx"
OUTPUT_DIR = BASE_DIR / "data" / "output"
OUTPUT_JSON = OUTPUT_DIR / "parsed_genes.json"
OUTPUT_CSV_PREFIX = "gene_table"
