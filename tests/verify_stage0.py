"""阶段 0 验证：大脑收发 + (待补) kernel 跨 cell 状态。

运行：
    cd open-science
    python tests/verify_stage0.py

需要先把 .env.example 复制为 .env 并填入真实 LLM_API_KEY。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from open_science.brain import Brain  # noqa: E402
from open_science.runtime import KernelSession  # noqa: E402


def check_brain_roundtrip() -> bool:
    """关卡 1：大脑能收发，ping 返回含 pong。"""
    brain = Brain()
    reply = brain.ping()
    ok = "pong" in reply.lower()
    print(f"[1] brain roundtrip: reply={reply!r} -> {'PASS' if ok else 'FAIL'}")
    return ok


def check_kernel_state() -> bool:
    """关卡 2：kernel 跨 cell 保留变量（operon 同款有状态内核）。

      cell A: x = 41; x += 1
      cell B: print(x)                  断言 stdout == "42"
      cell C: import math; math.sqrt(x) 断言 result ≈ 6.48
    """
    ks = KernelSession().start()
    try:
        a = ks.run("x = 41; x += 1")
        b = ks.run("print(x)")
        c = ks.run("import math; math.sqrt(x)")

        ok_a = a.ok
        ok_b = b.ok and b.stdout.strip() == "42"
        ok_c = c.ok and c.result is not None and abs(float(c.result) - 6.4807) < 1e-3
        ok = ok_a and ok_b and ok_c
        print(
            f"[2] kernel cross-cell state: A.ok={ok_a} B.stdout={b.stdout.strip()!r} "
            f"C.result={c.result!r} -> {'PASS' if ok else 'FAIL'}"
        )
        return ok
    finally:
        ks.shutdown()


def check_kernel_pip() -> bool:
    """关卡 3：内核内可装包并立即导入（operon 声明式 compute 的基础）。

    在同一内核里 pip 装一个极小、纯 python 的包（cowsay），装完当场 import。
    """
    ks = KernelSession().start()
    try:
        install = ks.run(
            "import subprocess, sys; "
            "print(subprocess.run([sys.executable,'-m','pip','install','-q','cowsay'],"
            "capture_output=True,text=True).returncode)",
            timeout=180.0,
        )
        use = ks.run("import cowsay; print('cowsay', cowsay.__name__)")
        ok = install.ok and install.stdout.strip() == "0" and use.ok and "cowsay" in use.stdout
        print(
            f"[3] kernel pip install+import: rc={install.stdout.strip()!r} "
            f"import={use.stdout.strip()!r} -> {'PASS' if ok else 'FAIL'}"
        )
        return ok
    finally:
        ks.shutdown()


def main() -> int:
    results = [
        check_brain_roundtrip(),
        check_kernel_state(),
        check_kernel_pip(),
    ]
    passed = all(results)
    print("=" * 40)
    print("STAGE 0:", "ALL PASS" if passed else "FAIL")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
