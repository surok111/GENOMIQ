import json
import pandas as pd
from pathlib import Path
from typing import List
from .models import GeneData
from . import config

def save_to_json(gene_list: List[GeneData], path: str):
    """Сериализует список генов в JSON."""
    data = []
    for gene in gene_list:
        gene_dict = {"name": gene.name, "tables": []}
        for tbl in gene.tables:
            gene_dict["tables"].append({
                "title": tbl.table_title,
                "headers": tbl.headers,
                "rows": tbl.rows
            })
        data.append(gene_dict)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def save_to_csv(gene_list: List[GeneData], prefix: str):
    """Каждую таблицу сохраняет в отдельный CSV."""
    out_dir = config.OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    for gene in gene_list:
        for i, tbl in enumerate(gene.tables):
            df = pd.DataFrame(tbl.rows)
            filename = out_dir / f"{prefix}_{gene.name}_{i+1}.csv"
            df.to_csv(filename, index=False, encoding='utf-8-sig')