#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""merge_notes.py — 按子笔记本合并 Markdown 为单文件, 减少 ima 导入次数(省流)

用法:
    python3 merge_notes.py <markdown目录> <输出目录> [--map '{"顶级目录":"知识库名"}'] [--exclude 目录1,目录2]

示例:
    python3 merge_notes.py ./markdown ./ima_upload \
        --map '{"02学习提升":"ai时代技能","04财务管理":"财务管理"}' \
        --exclude '03个人资料'
"""
import argparse
import glob
import json
import os
import re

DEFAULT_MAP = {"学习": "学习知识库", "工作": "工作知识库"}


def main():
    ap = argparse.ArgumentParser(description="按子笔记本合并 Markdown")
    ap.add_argument("src", help="markdown 目录（含笔记本层级）")
    ap.add_argument("out", help="合并输出目录")
    ap.add_argument("--map", help="顶级目录到知识库名的 JSON 映射")
    ap.add_argument("--exclude", help="逗号分隔的顶级目录名，跳过不合并")
    args = ap.parse_args()

    kb_map = json.loads(args.map) if args.map else DEFAULT_MAP
    exclude = set(x.strip() for x in (args.exclude or "").split(",") if x.strip())

    os.makedirs(args.out, exist_ok=True)
    total_notes = total_files = 0
    for top in sorted(os.listdir(args.src)):
        if top in exclude:
            print(f"[跳过] {top}（exclude）")
            continue
        top_dir = os.path.join(args.src, top)
        if not os.path.isdir(top_dir):
            continue
        kb_name = kb_map.get(top, top)
        kb_out = os.path.join(args.out, kb_name)
        os.makedirs(kb_out, exist_ok=True)
        for nb in sorted(os.listdir(top_dir)):
            nb_dir = os.path.join(top_dir, nb)
            if not os.path.isdir(nb_dir):
                continue
            mds = sorted(glob.glob(os.path.join(nb_dir, "*.md")))
            mds = [m for m in mds if os.path.basename(m) != "index.md"]
            if not mds:
                continue
            parts = [f"# {nb}\n"]
            for m in mds:
                text = open(m, encoding="utf-8").read()
                mm = re.match(r"^---\n(.*?)\n---\n\n", text, re.S)
                title = re.search(r"title:\s*(.+)", mm.group(1)).group(1).strip() if mm else os.path.basename(m)
                body = text[mm.end():] if mm else text
                body = re.sub(r"!\[[^\]]*\]\(_resources/[^)]*\)\n?", "", body)  # 移除本地图片引用
                body = body.strip()
                parts.append(f"## {title}\n\n{body}\n")
                total_notes += 1
            with open(os.path.join(kb_out, nb + ".md"), "w", encoding="utf-8") as f:
                f.write("\n".join(parts) + "\n")
            total_files += 1
            print(f"[OK] {kb_name}/{nb}.md ({len(mds)} 篇)")
    print(f"合并完成: {total_files} 个文件 / {total_notes} 篇 -> {args.out}")


if __name__ == "__main__":
    main()
