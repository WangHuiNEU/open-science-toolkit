"""阶段 1 验证：溯源 by construction + artifact 往返 + 只读防线 + DAG + 结构渲染。

运行：
    cd open-science
    python tests/verify_stage1.py

五关（对齐 docs/ROADMAP.md 阶段 1）：
  1. 自动溯源：内核跑一段写文件的代码 → execution_log 新增一行，
     files_written 里该文件 sha256 正确。
  2. artifact 往返：save_artifact → version_id → get_artifact 字节一致。
  3. 只读防线：query("DROP TABLE execution_log") 被拒，表还在。
  4. DAG：B 依赖 A，artifact_dependencies 能走出 A→B。
  5. 结构渲染：.pdb → 渲染层判为 structure + Mol*；.png → image 内联。
"""

from __future__ import annotations

import hashlib
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from open_science.provenance.db import init_db          # noqa: E402
from open_science.provenance.host import Host, ReadOnlyViolation  # noqa: E402
from open_science.render import classify, render_directive       # noqa: E402
from open_science.runtime import KernelSession           # noqa: E402


def check_auto_provenance(db_path: str, ws: Path) -> bool:
    """关卡 1：跑代码写文件 → execution_log 自动记 + files_written sha256 正确。"""
    ks = KernelSession(db_path=db_path, workspace_dir=ws).start()
    try:
        r = ks.run("open('out.txt','w').write('hi')")
        # 从库里读回这条 execution_log
        h = Host(db_path, ws)
        rows = h.query(
            "SELECT source, files_written FROM execution_log WHERE id=?",
            params=[r.cell_id],
        )["rows"]
        ok_row = len(rows) == 1
        # cell 结果里记到的 sha256
        fw = r.files_written
        expected = hashlib.sha256(b"hi").hexdigest()
        ok_hash = any(
            f["path"].endswith("out.txt") and f["sha256"] == expected for f in fw
        )
        ok = ok_row and ok_hash and r.cell_id is not None
        print(
            f"[1] auto provenance: cell_id={r.cell_id!r} logged={ok_row} "
            f"sha_ok={ok_hash} -> {'PASS' if ok else 'FAIL'}"
        )
        return ok
    finally:
        ks.shutdown()


def check_artifact_roundtrip(db_path: str, ws: Path) -> bool:
    """关卡 2：save_artifact → get_artifact 字节一致。"""
    h = Host(db_path, ws)
    payload = b"\x89PNG fake bytes \x00\x01\x02"
    vid = h.save_artifact("fig1.png", payload)
    back = h.get_artifact(vid)
    ok = back == payload
    print(f"[2] artifact roundtrip: vid={vid[:16]}… bytes_equal={ok} -> {'PASS' if ok else 'FAIL'}")
    return ok


def check_readonly_guard(db_path: str, ws: Path) -> bool:
    """关卡 3：query 拒写；表还在。"""
    h = Host(db_path, ws)
    rejected = False
    try:
        h.query("DROP TABLE execution_log")
    except ReadOnlyViolation:
        rejected = True
    # 表还在？
    still = h.query(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='execution_log'"
    )["rows"]
    ok = rejected and len(still) == 1
    print(f"[3] readonly guard: rejected={rejected} table_intact={len(still)==1} -> {'PASS' if ok else 'FAIL'}")
    return ok


def check_dag(db_path: str, ws: Path) -> bool:
    """关卡 4：B 依赖 A → artifact_dependencies 走得出 A→B。"""
    h = Host(db_path, ws)
    a = h.save_artifact("A.csv", b"col\n1\n")
    b = h.save_artifact("B.png", b"plot-of-A", depends_on=[a])
    rows = h.query(
        "SELECT depends_on_version_id FROM artifact_dependencies "
        "WHERE artifact_version_id=?",
        params=[b],
    )["rows"]
    ok = len(rows) == 1 and rows[0][0] == a
    print(f"[4] DAG A->B: edge={rows} -> {'PASS' if ok else 'FAIL'}")
    return ok


def check_structure_render() -> bool:
    """关卡 5：.pdb 走 Mol* 结构路径；.png 走内联图片。"""
    pdb = render_directive("ver_test", "predicted.pdb")
    png = render_directive("ver_test2", "fig.png")
    ok_pdb = (
        pdb.kind == "structure"
        and pdb.viewer == "molstar"
        and pdb.structure_format == "pdb"
        and classify("x.cif") == "structure"
        and classify("y.mmcif") == "structure"
    )
    ok_png = png.kind == "image" and png.viewer is None
    ok = ok_pdb and ok_png
    print(
        f"[5] structure render: pdb.kind={pdb.kind}/{pdb.viewer} "
        f"png.kind={png.kind} -> {'PASS' if ok else 'FAIL'}"
    )
    return ok


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="openscience_s1_"))
    db_path = init_db(tmp / "provenance.sqlite")
    ws = tmp / "workspace"
    ws.mkdir(parents=True, exist_ok=True)

    results = [
        check_auto_provenance(db_path, ws),
        check_artifact_roundtrip(db_path, ws),
        check_readonly_guard(db_path, ws),
        check_dag(db_path, ws),
        check_structure_render(),
    ]
    passed = all(results)
    print("=" * 40)
    print("STAGE 1:", "ALL PASS" if passed else "FAIL")
    print(f"(tmp: {tmp})")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
