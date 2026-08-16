#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""convert_all.py — 递归转换 enex 目录下所有 .enex 为 Markdown（保留笔记本层级）

用法:
    python3 convert_all.py <enex目录> <markdown输出目录>

依赖: enex2md.py（同目录）
"""
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from enex2md import convert_file  # noqa: E402


def main():
    if len(sys.argv) != 3:
        print("用法: python3 convert_all.py <enex目录> <markdown输出目录>")
        sys.exit(1)
    src, out = sys.argv[1], sys.argv[2]
    if not os.path.isdir(src):
        print(f"错误: {src} 不是目录")
        sys.exit(1)
    os.makedirs(out, exist_ok=True)
    files = sorted(glob.glob(os.path.join(src, "**", "*.enex"), recursive=True))
    if not files:
        print("未找到 .enex 文件")
        sys.exit(1)
    grand = {"notes": 0, "resources": 0, "files": 0}
    all_failed = []
    for p in files:
        rel = os.path.relpath(p, src)
        rel_dir = os.path.dirname(rel)
        notebook = os.path.splitext(os.path.basename(rel))[0]
        out_dir = os.path.join(out, rel_dir, notebook)
        st = convert_file(p, out_dir, flat=True, with_frontmatter=True, with_resources=True)
        print(f"[{'!!' if st['failed'] else 'OK'}] {rel}: {st['notes']} 篇, 资源 {st['resources']}"
              + (f", 失败 {len(st['failed'])}" if st["failed"] else ""))
        for f_ in st["failed"]:
            print("      ", f_)
        grand["notes"] += st["notes"]
        grand["resources"] += st["resources"]
        grand["files"] += 1
        all_failed += st["failed"]
    print(f"完成: {grand['files']} 个 enex / {grand['notes']} 篇 / {grand['resources']} 资源 -> {out}")
    if all_failed:
        print(f"失败 {len(all_failed)} 条, 详见上方")
        sys.exit(1)


if __name__ == "__main__":
    main()
