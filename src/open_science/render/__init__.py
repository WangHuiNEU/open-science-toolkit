"""阶段 1：artifact 渲染层（operon 对齐项，OpenHands 不自带，必需自建）。

operon 里 artifact 不只是"存"，还按**后缀**自动渲染给用户看：
    .pdb/.cif/.mmcif → 自动挂 Mol* 3D 交互查看器（operon metadata 第 38–39 行）
    .png/.svg/.jpg…  → 内联 <img>
    .md/.tex/.html   → 可点链接 [名]({{artifact:ID}})

触发条件与 operon 一致：**后缀匹配 + 已 save_artifact**。只在内核里生成了
pdb 但没 save_artifact → 用户看不到（对齐 operon「不 save 不可见」语义）。
所以本模块的入口都要求已有 version_id（= 已落库）。

本模块只产出**渲染指令**（RenderDirective，纯数据）；真正把 Mol* web 组件挂到
前端由前端消费这个指令完成——这样后端与前端解耦，前端可以是 web / notebook / TUI。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import PurePosixPath

# 后缀 → 渲染类型
_STRUCTURE_SUFFIXES = {".pdb", ".cif", ".mmcif", ".ent", ".bcif"}
_IMAGE_SUFFIXES = {".png", ".svg", ".jpg", ".jpeg", ".gif", ".webp"}
_DOC_SUFFIXES = {".md", ".markdown", ".tex", ".html", ".htm", ".txt", ".csv"}

# Mol* 官方 CDN 组件（molstar.org，MIT）。前端据此加载 viewer。
MOLSTAR_CDN = "https://cdn.jsdelivr.net/npm/molstar/build/viewer/molstar.js"


@dataclass
class RenderDirective:
    """给前端的渲染指令（纯数据，不含实际字节）。"""

    version_id: str
    filename: str
    kind: str                      # "structure" | "image" | "document" | "download"
    marker: str                    # {{artifact:VERSION_ID}} 占位符
    # 结构专用：前端用哪个查看器、结构格式是什么
    viewer: str | None = None      # "molstar"
    structure_format: str | None = None  # "pdb"/"cif"/"mmcif"
    assets: dict = field(default_factory=dict)  # 如 {"molstar_cdn": ...}

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v not in (None, {}, [])}


def classify(filename: str) -> str:
    """按后缀判定渲染类型。"""
    suffix = PurePosixPath(filename).suffix.lower()
    if suffix in _STRUCTURE_SUFFIXES:
        return "structure"
    if suffix in _IMAGE_SUFFIXES:
        return "image"
    if suffix in _DOC_SUFFIXES:
        return "document"
    return "download"


def render_directive(version_id: str, filename: str) -> RenderDirective:
    """由 (已落库的) version_id + 文件名产出渲染指令。

    触发前提：调用方已 save_artifact 拿到 version_id——本函数不校验库，
    但语义上只应对"已保存"的 artifact 调用（对齐 operon 不 save 不可见）。
    """
    marker = f"{{{{artifact:{version_id}}}}}"
    kind = classify(filename)
    suffix = PurePosixPath(filename).suffix.lower().lstrip(".")

    if kind == "structure":
        fmt = "mmcif" if suffix == "mmcif" else suffix
        return RenderDirective(
            version_id=version_id,
            filename=filename,
            kind="structure",
            marker=marker,
            viewer="molstar",
            structure_format=fmt,
            assets={"molstar_cdn": MOLSTAR_CDN},
        )
    return RenderDirective(
        version_id=version_id,
        filename=filename,
        kind=kind,
        marker=marker,
    )
