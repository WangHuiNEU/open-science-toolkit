"""原样 vendor 的 operon bio-tools/lib（勿改内容——保持与上游字节级一致）。

lib/ 下 87 个包是扁平命名空间、彼此互 import。要用它们必须先把
`vendor/lib` 放到 sys.path（launcher.py / registry.py 负责），
不要写成 `from open_science.datasources.vendor.lib.mcp_rna ...`——
那样它们内部的 `from rfam_families import ...` 会找不到。
"""

from pathlib import Path

LIB_DIR = Path(__file__).resolve().parent / "lib"
