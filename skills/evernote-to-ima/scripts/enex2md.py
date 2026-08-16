#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
enex2md v2.0 — 印象笔记 .enex → Markdown 批量转换工具（纯 Python 标准库，零依赖）

用法:
    python3 enex2md.py <输入.enex 或 目录> [输出目录] [--flat] [--no-frontmatter] [--no-resources]

示例:
    python3 enex2md.py ~/Desktop/evernote_export/ ~/Desktop/markdown_notes
    python3 enex2md.py 01_行业报告.enex ./out --flat

特性:
    - ENML 富文本 → Markdown: 标题/加粗/斜体/下划线/链接/列表(含嵌套)/表格/代码块/引用/待办
    - 图片附件 base64 解码存盘, Markdown 相对路径引用 (优先保留原文件名)
    - 每个 .enex 默认输出到同名子目录 (保留笔记本层级), --flat 可平面输出
    - 每篇笔记一个 .md, 头部 YAML frontmatter (title/tags/created/updated)
    - 每个笔记本目录自动生成 index.md 索引
    - 容错: 单篇失败自动跳过并统计, 不中断批量
"""
import argparse
import base64
import hashlib
import os
import re
import sys
import xml.etree.ElementTree as ET

RESOURCE_DIR = "_resources"


# ---------------------------------------------------------------- 基础工具
def strip_ns(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def sanitize_filename(name: str) -> str:
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", name)
    name = re.sub(r"\s+", " ", name).strip(" .")
    return name[:120] or "untitled"


def parse_enex(path: str) -> list:
    """解析 .enex, 返回笔记列表 dict。单篇异常不致命, 由上层捕获。"""
    tree = ET.parse(path)
    root = tree.getroot()
    notes = []
    for note in root.findall("note"):
        title_el = note.find("title")
        title = (title_el.text or "untitled") if title_el is not None else "untitled"
        content_el = note.find("content")
        content_xml = (content_el.text or "") if content_el is not None else ""
        tags = [t.text for t in note.findall("tag") if t.text]
        created = (note.findtext("created") or "").strip()
        updated = (note.findtext("updated") or "").strip()
        resources = []
        for res in note.findall("resource"):
            data_el = res.find("data")
            raw = b""
            if data_el is not None and data_el.text:
                try:
                    raw = base64.b64decode(data_el.text)
                except Exception:
                    raw = b""
            resources.append({
                "data": raw,
                "mime": (res.findtext("mime") or "application/octet-stream").strip(),
                "file_name": (res.findtext("file-name") or "").strip(),
                "width": (res.findtext("width") or "").strip(),
                "height": (res.findtext("height") or "").strip(),
                "md5": hashlib.md5(raw).hexdigest(),
            })
        notes.append({"title": title, "content_xml": content_xml, "tags": tags,
                      "created": created, "updated": updated, "resources": resources})
    return notes


def ext_of(mime: str, fname: str) -> str:
    if fname and "." in fname:
        return fname.rsplit(".", 1)[-1].lower()
    return {"image/png": "png", "image/jpeg": "jpg", "image/gif": "gif",
            "image/webp": "webp", "image/svg+xml": "svg", "application/pdf": "pdf",
            "text/plain": "txt", "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
            }.get(mime, "bin")


def save_resources(note: dict, out_dir: str) -> None:
    """把笔记资源写入 <out>/_resources/, 返回 hash->文件名 映射 (写回 note['res_map'])。"""
    res_dir = os.path.join(out_dir, RESOURCE_DIR)
    os.makedirs(res_dir, exist_ok=True)
    note["res_map"] = {}
    used = set()
    for r in note["resources"]:
        if not r["data"]:
            continue
        base = sanitize_filename(r["file_name"]) or r["md5"][:12] + "." + ext_of(r["mime"], r["file_name"])
        if "." not in base:
            base += "." + ext_of(r["mime"], r["file_name"])
        name, n = base, 1
        while name in used or os.path.exists(os.path.join(res_dir, name)):
            stem, dot, ext = base.rpartition(".")
            name = f"{stem}_{n}{dot}{ext}"
            n += 1
        used.add(name)
        with open(os.path.join(res_dir, name), "wb") as f:
            f.write(r["data"])
        note["res_map"][r["md5"]] = name
        if r["file_name"]:
            note["res_map"][r["file_name"]] = name


# ---------------------------------------------------------------- ENML → MD
def convert_node(el, res_map: dict) -> str:
    """递归转换。inner() 拼接 el.text + 子节点转换 + 子节点 tail, 保证直接文本不丢失。"""
    tag = strip_ns(el.tag)
    children = list(el)

    def inner() -> str:
        s = ""
        t0 = el.text or ""
        if t0.strip():  # 丢弃 HTML 标签间无意义的换行/缩进空白
            s += t0
        for c in children:
            s += convert_node(c, res_map)
            t = c.tail or ""
            if t.strip():  # 仅保留实际文本 tail
                s += t
        return s

    def li_text(li_el) -> str:
        s = li_el.text or ""
        for g in list(li_el):
            s += convert_node(g, res_map) + (g.tail or "")
        return s.strip()

    if tag == "en-note":
        return inner()
    if tag in ("div", "p", "section"):
        return inner().strip() + "\n"
    if tag == "br":
        return "\n"
    if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
        return "#" * int(tag[1]) + " " + inner().strip() + "\n"
    if tag in ("b", "strong"):
        return "**" + inner() + "**"
    if tag in ("i", "em"):
        return "*" + inner() + "*"
    if tag == "u":
        return "<u>" + inner() + "</u>"
    if tag == "a":
        return f"[{inner().strip()}]({el.get('href', '')})"
    if tag == "blockquote":
        body = inner().strip()
        return "".join("> " + line + "\n" for line in body.splitlines()) + "\n"
    if tag == "pre":
        code = "".join((c.text or "") for c in children)
        if not code:
            code = inner()
        return "\n```\n" + code.strip("\n") + "\n```\n"
    if tag == "code":
        return "`" + inner() + "`"
    if tag == "ul":
        return list_block(el, 0, res_map, ordered=False)
    if tag == "ol":
        return list_block(el, 0, res_map, ordered=True)
    if tag == "li":
        return inner()
    if tag == "table":
        return table_block(el, res_map)
    if tag in ("tr", "td", "th", "thead", "tbody"):
        return inner()
    if tag == "en-todo":
        checked = "x" if (el.get("checked") or "").lower() == "true" else " "
        return f"- [{checked}] {inner()}"
    if tag == "en-media":
        fname = res_map.get(el.get("hash", ""))
        if fname:
            return f"\n![{fname}]({RESOURCE_DIR}/{fname})\n"
        return ""
    if tag in ("span", "font", "center", "strike", "del"):
        return inner()
    return inner()


def list_block(ul_el, depth: int, res_map: dict, ordered: bool) -> str:
    """支持嵌套列表的块级转换。"""
    lines = []
    n = 1
    indent = "  " * depth
    for c in list(ul_el):
        tag = strip_ns(c.tag)
        if tag == "li":
            text = (c.text or "")
            for g in list(c):
                if strip_ns(g.tag) in ("ul", "ol"):
                    continue
                text += convert_node(g, res_map) + (g.tail or "")
            marker = f"{n}. " if ordered else "- "
            lines.append(indent + marker + text.strip())
            for sub in list(c):
                if strip_ns(sub.tag) in ("ul", "ol"):
                    lines.append(list_block(sub, depth + 1, res_map,
                                           ordered=strip_ns(sub.tag) == "ol").rstrip("\n"))
            n += 1
    return "\n".join(lines) + "\n"


def table_block(tbl_el, res_map: dict) -> str:
    rows = []
    for tr in tbl_el.iter():
        if strip_ns(tr.tag) == "tr":
            cells = []
            for cell in list(tr):
                if strip_ns(cell.tag) in ("td", "th"):
                    cells.append(convert_node(cell, res_map).strip().replace("\n", " "))
            rows.append(cells)
    if not rows:
        return ""
    out = []
    for i, row in enumerate(rows):
        out.append("| " + " | ".join(row) + " |")
        if i == 0:
            out.append("|" + "|".join("---" for _ in row) + "|")
    return "\n".join(out) + "\n"


def enml_to_md(content_xml: str, res_map: dict) -> str:
    if not content_xml.strip():
        return ""
    # 印象笔记 content 常带 XML 声明 + 引用外部 DTD 的 DOCTYPE, ElementTree 无法解析, 需先剥离
    cleaned = re.sub(r"<\?xml[^>]*\?>", "", content_xml)
    cleaned = re.sub(r"<!DOCTYPE[^>]*>", "", cleaned)
    try:
        root = ET.fromstring(cleaned)
    except ET.ParseError:
        return re.sub(r"<[^>]+>", "", content_xml)
    body = convert_node(root, res_map)
    lines = [ln.strip() for ln in body.splitlines()]  # 逐行去首尾空白, 消除网页剪藏的缩进噪音
    body = "\n".join(lines)
    body = re.sub(r"\n{2,}", "\n\n", body)  # 压缩连续空行
    return body.strip() + "\n"


def note_to_md(note: dict, with_frontmatter: bool = True) -> str:
    head = ""
    if with_frontmatter:
        head = "---\n"
        head += f"title: {note['title']}\n"
        if note["tags"]:
            head += "tags: [" + ", ".join(note["tags"]) + "]\n"
        if note["created"]:
            head += f"created: {note['created']}\n"
        if note["updated"]:
            head += f"updated: {note['updated']}\n"
        head += "---\n\n"
    body = enml_to_md(note["content_xml"], note.get("res_map", {}))
    return head + body


# ---------------------------------------------------------------- 文件输出
def convert_file(enex_path: str, out_dir: str, flat: bool, with_frontmatter: bool,
                 with_resources: bool) -> dict:
    stats = {"notes": 0, "resources": 0, "failed": []}
    try:
        notes = parse_enex(enex_path)
    except Exception as e:
        stats["failed"].append(f"{os.path.basename(enex_path)}: 解析失败 {e}")
        return stats

    base_dir = out_dir if flat else os.path.join(out_dir, sanitize_filename(os.path.splitext(os.path.basename(enex_path))[0]))
    os.makedirs(base_dir, exist_ok=True)

    used = {}
    index_rows = []
    for note in notes:
        try:
            if with_resources:
                save_resources(note, base_dir)
                stats["resources"] += sum(1 for r in note["resources"] if r["data"])
            else:
                note["res_map"] = {}
            base = sanitize_filename(note["title"])
            n = used.get(base, 0)
            used[base] = n + 1
            fname = f"{base}_{n}.md" if n else f"{base}.md"
            with open(os.path.join(base_dir, fname), "w", encoding="utf-8") as f:
                f.write(note_to_md(note, with_frontmatter))
            tags = "、".join(note["tags"]) if note["tags"] else "-"
            index_rows.append(f"- [{note['title']}]({fname}) — {tags}")
            stats["notes"] += 1
        except Exception as e:
            stats["failed"].append(f"{note.get('title', '?')}: {e}")

    if index_rows:
        with open(os.path.join(base_dir, "index.md"), "w", encoding="utf-8") as f:
            f.write(f"# {os.path.splitext(os.path.basename(enex_path))[0]}\n\n"
                    f"> 共 {len(index_rows)} 篇\n\n" + "\n".join(index_rows) + "\n")
    return stats


def main():
    ap = argparse.ArgumentParser(description="印象笔记 .enex → Markdown 批量转换")
    ap.add_argument("src", help=".enex 文件或包含 .enex 的目录")
    ap.add_argument("out", nargs="?", default="markdown_out", help="输出目录 (默认 markdown_out)")
    ap.add_argument("--flat", action="store_true", help="平面输出, 不为每个笔记本建子目录")
    ap.add_argument("--no-frontmatter", action="store_true", help="不生成 YAML frontmatter")
    ap.add_argument("--no-resources", action="store_true", help="不导出附件资源")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    grand = {"notes": 0, "resources": 0, "files": 0}
    all_failed = []
    if os.path.isdir(args.src):
        files = sorted(f for f in os.listdir(args.src) if f.lower().endswith(".enex"))
    else:
        files = [args.src]
    if not files:
        print("未找到 .enex 文件")
        sys.exit(1)
    for fn in files:
        p = fn if os.path.isabs(fn) else os.path.join(args.src, fn) if os.path.isdir(args.src) else fn
        st = convert_file(p, args.out, args.flat, not args.no_frontmatter, not args.no_resources)
        print(f"[OK] {os.path.basename(p)} -> {st['notes']} 篇, {st['resources']} 资源"
              + (f", 失败 {len(st['failed'])}" if st["failed"] else ""))
        grand["notes"] += st["notes"]
        grand["resources"] += st["resources"]
        grand["files"] += 1
        all_failed += st["failed"]
    print(f"全部完成: {grand['files']} 个文件 / {grand['notes']} 篇笔记 / {grand['resources']} 个资源 -> {args.out}")
    if all_failed:
        print("以下条目转换失败(已跳过):")
        for item in all_failed:
            print("  -", item)


if __name__ == "__main__":
    main()
