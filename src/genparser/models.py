from dataclasses import dataclass, field
from typing import List, Dict

@dataclass
class GeneTable:
    gene_name: str
    table_title: str
    headers: List[str]
    rows: List[Dict[str, str]]

@dataclass
class GeneData:
    name: str
    tables: List[GeneTable] = field(default_factory=list)