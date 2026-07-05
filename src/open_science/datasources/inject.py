"""按需注入 —— 关键词/领域 trigger 选域（= operon 渐进暴露）。

问题里出现某域的触发词，就只把该域的 server 注入 context，避免 87 工具
全量撑爆。触发词表是**保守**的：命中不了就返回空（宁可不注入，让上层
决定 fallback 到 'all'），不做模糊猜测。

    from open_science.datasources.inject import select_domains, mcp_config_for_query
    select_domains("这个 5S rRNA 家族的二级结构")   # -> ['rna']
    cfg = mcp_config_for_query("查一下 P69905 的序列")  # -> genes-ontologies 域 config
"""

from __future__ import annotations

import re

from .registry import all_domains, mcp_config_for

# 域 → 触发关键词（小写子串匹配）。只放高置信词，避免误注入。
_TRIGGERS: dict[str, list[str]] = {
    "rna": ["rna", "rfam", "ncrna", "trna", "rrna", "mirna", "riboswitch",
            "covariance model", "二级结构", "核酸家族"],
    "genes-ontologies": ["uniprot", "gene ontology", "go term", "kegg",
                          "reactome", "ontology", "基因本体", "蛋白条目"],
    "pubmed": ["pubmed", "pmid", "pmc", "literature search", "文献", "论文",
               "citation"],
    "literature": ["arxiv", "openalex", "preprint", "doi", "作者"],
    "chembl": ["chembl", "bioactivity", "admet", "drug target"],
    "chemistry": ["pubchem", "chebi", "smiles", "compound", "化合物", "分子"],
    "variants": ["clinvar", "dbsnp", "variant", "rsid", "突变", "变异"],
    "genomes": ["ensembl", "ucsc", "genome browser", "vep", "基因组"],
    "structures-interactions": ["pdb", "alphafold", "emdb", "intact",
                                "蛋白结构", "复合物", "相互作用"],
    "protein-annotation": ["interpro", "pfam", "string", "protein atlas",
                           "蛋白结构域", "domain architecture"],
    "expression": ["gtex", "eqtl", "expression", "表达量"],
    "clinical-trials": ["clinical trial", "nct", "临床试验"],
    "clinical-genomics": ["civic", "clingen", "open targets"],
    "drug-regulatory": ["fda", "drug label", "drug application"],
    "human-genetics": ["gwas", "phewas", "finngen"],
    "omics-archives": ["geo", "arrayexpress", "pride", "metabolights",
                       "mgnify", "组学"],
    "regulation": ["encode", "jaspar", "unibind", "tfbs", "转录因子"],
    "cancer-models": ["cbioportal", "depmap", "cell model"],
    "cellguide": ["cell type", "marker gene", "细胞类型"],
    "biomart": ["biomart"],
    "biorxiv": ["biorxiv", "medrxiv"],
    "research-resources": ["antibody", "grant", "抗体"],
    "zinc": ["zinc", "docking library"],
}


def select_domains(query: str) -> list[str]:
    """从 query 里选出命中的域（稳定排序、去重）。命中不了返回 []。"""
    q = query.lower()
    hit = {d for d, kws in _TRIGGERS.items() if any(k in q for k in kws)}
    valid = set(all_domains())
    return sorted(hit & valid)


def mcp_config_for_query(query: str, *, fallback_all: bool = False) -> dict:
    """query → MCPConfig。未命中时：fallback_all=True 挂全域，否则挂空。"""
    domains = select_domains(query)
    if not domains:
        return mcp_config_for(["all"]) if fallback_all else {"mcpServers": {}}
    return mcp_config_for(domains)
