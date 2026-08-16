#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
notes2md v1.0 — 印象笔记 .notes/.enex(含 base64:aes 加密) → Markdown 批量转换

背景:
    印象笔记新版导出的 .notes 实为 ENEX 变体(<en-export>), 若笔记启用了"加密导出",
    <content encoding="base64:aes"> 的正文以 印象笔记专有格式加密:
        明文布局 = "ENC0" + IV(16字节) + AES-128-CBC密文(PKCS7填充)
        密钥     = MD5(加密密码) 的 16 字节
    附件 <resource><data> 为普通 base64, 未加密, 可直接解码。

依赖:
    - Python 3.6+ (标准库, 无需 pip 安装任何包)
    - 系统 openssl (macOS 自带 /usr/bin/openssl; Linux 一般自带)

用法:
    python3 notes2md.py <输入.notes/.enex 或 目录> <输出目录> --password <加密密码> [--flat]

    # 环境变量方式(避免密码出现在命令行历史):
    export NOTES2MD_PASSWORD='你的密码'
    python3 notes2md.py <输入> <输出>
"""
import argparse
import base64
import hashlib
import hmac
import os
import re
import subprocess
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


def aes_decrypt(cipher: bytes, password: str) -> bytes:
    """印象笔记 ENC0 加密格式解密（参考 soundly.me 解码报告 + aviaryan/Evernote-Decrypt）：
    布局 = 'ENC0'(4) + salt(16) + salthmac(16) + IV(16) + ciphertext + bodyhmac(32)
    加密密钥 = PBKDF2-HMAC-SHA256(password, salt, 50000, 16)   → AES-128-CBC
    HMAC 密钥 = PBKDF2-HMAC-SHA256(password, salthmac, 50000, 16)
    密码校验  = HMAC-SHA256(keyhmac, ENC0..ciphertext) == bodyhmac
    """
    if cipher[:4] != b"ENC0":
        raise ValueError("密文前缀不是 ENC0, 可能不是印象笔记加密导出格式")
    if len(cipher) < 84:
        raise ValueError("密文长度异常")
    salt, salthmac, iv = cipher[4:20], cipher[20:36], cipher[36:52]
    ciphertext, bodyhmac = cipher[52:-32], cipher[-32:]

    def pbkdf2(pw: str, s: bytes) -> bytes:
        return hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), s, 50000, 16)

    keyhmac = pbkdf2(password, salthmac)
    body = cipher[: len(cipher) - 32]
    if not hmac.compare_digest(hmac.new(keyhmac, body, hashlib.sha256).digest(), bodyhmac):
        raise ValueError("密码不正确 (HMAC 校验失败)")

    key = pbkdf2(password, salt)
    proc = subprocess.run(
        ["openssl", "enc", "-d", "-aes-128-cbc", "-K", key.hex(), "-iv", iv.hex()],
        input=ciphertext, capture_output=True,
    )
    if proc.returncode != 0:
        raise ValueError(f"AES 解密失败: {proc.stderr.decode(errors='replace')[:150]}")
    return proc.stdout


def decrypt_content(content_xml_enc: str, password: str) -> str:
    """content 为 base64:aes 编码的 CDATA 内容, 解密为 ENML(XHTML) 文本。
    AES 解密不校验密码正确性, 因此解密后必须严格校验(UTF-8 + XML 解析),
    否则错误密码会产出乱码被当作"成功"。"""
    try:
        raw = base64.b64decode(content_xml_enc.replace("\n", ""))
    except Exception as e:
        raise ValueError(f"base64 解码失败: {e}")
    plain = aes_decrypt(raw, password)
    try:
        text = plain.decode("utf-8")  # 严格解码, 乱码会抛 UnicodeDecodeError
    except UnicodeDecodeError:
        raise ValueError("解密失败: 密码不正确或内容已损坏 (UTF-8 校验未通过)")
    text = text.lstrip("\ufeff \t\r\n")
    if not (text.startswith("<en-note") or "<en-note" in text[:200]):
        raise ValueError("解密失败: 密码不正确或内容已损坏 (非印象笔记内容格式)")
    try:
        ET.fromstring(text)
    except ET.ParseError:
        raise ValueError("解密失败: 密码不正确或内容已损坏 (XML 解析未通过)")
    return text


def parse_enex(path: str, password: str) -> list:
    """解析 .notes/.enex, 解密 content, 返回笔记列表。单篇异常不致命。"""
    tree = ET.parse(path)
    root = tree.getroot()
    notes = []
    for note in root.findall("note"):
        title_el = note.find("title")
        title = (title_el.text or "untitled") if title_el is not None else "untitled"
        content_el = note.find("content")
        enc = (content_el.get("encoding") or "plain") if content_el is not None else "plain"
        content_text = (content_el.text or "") if content_el is not None else ""
        content_xml = ""
        decrypt_error = None
        if content_text.strip():
            try:
                if enc == "base64:aes":
                    content_xml = decrypt_content(content_text, password)
                elif enc == "base64":
                    content_xml = base64.b64decode(content_text.replace("\n", "")).decode("utf-8", errors="replace")
                else:
                    content_xml = content_text
            except Exception as e:
                decrypt_error = f"{e}"
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
                "md5": hashlib.md5(raw).hexdigest(),
            })
        notes.append({"title": title, "content_xml": content_xml, "tags": tags,
                      "created": created, "updated": updated, "resources": resources,
                      "decrypt_error": decrypt_error, "enc": enc})
    return notes


def ext_of(mime: str, fname: str) -> str:
    if fname and "." in fname:
        return fname.rsplit(".", 1)[-1].lower()
    return {"image/png": "png", "image/jpeg": "jpg", "image/gif": "gif",
            "image/webp": "webp", "application/pdf": "pdf", "text/plain": "txt"}.get(mime, "bin")


def save_resources(note: dict, out_dir: str) -> None:
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
    tag = strip_ns(el.tag)
    children = list(el)

    def inner() -> str:
        s = el.text or ""
        for c in children:
            s += convert_node(c, res_map) + (c.tail or "")
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
        code = inner().strip("\n")
        return "\n```\n" + code + "\n```\n"
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
    lines, n = [], 1
    indent = "  " * depth
    for c in list(ul_el):
        if strip_ns(c.tag) == "li":
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
    try:
        root = ET.fromstring(content_xml)
    except ET.ParseError:
        return re.sub(r"<[^>]+>", "", content_xml)
    body = convert_node(root, res_map)
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body.strip() + "\n"


def note_to_md(note: dict) -> str:
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


# ---------------------------------------------------------------- 输出
def convert_file(path: str, out_dir: str, password: str, flat: bool) -> dict:
    stats = {"notes": 0, "resources": 0, "ok": 0, "empty": 0, "failed": []}
    notes = parse_enex(path, password)
    base_dir = out_dir if flat else os.path.join(out_dir, sanitize_filename(os.path.splitext(os.path.basename(path))[0]))
    os.makedirs(base_dir, exist_ok=True)
    used, index_rows = {}, []
    for note in notes:
        stats["notes"] += 1
        if note["decrypt_error"]:
            stats["failed"].append(f"[解密失败] {note['title']}: {note['decrypt_error']}")
            continue
        try:
            save_resources(note, base_dir)
            stats["resources"] += sum(1 for r in note["resources"] if r["data"])
            base = sanitize_filename(note["title"])
            n = used.get(base, 0)
            used[base] = n + 1
            fname = f"{base}_{n}.md" if n else f"{base}.md"
            md = note_to_md(note)
            with open(os.path.join(base_dir, fname), "w", encoding="utf-8") as f:
                f.write(md)
            if len(md.strip()) <= len("---\ntitle: x\n---"):
                stats["empty"] += 1
            else:
                stats["ok"] += 1
            tags = "、".join(note["tags"]) if note["tags"] else "-"
            index_rows.append(f"- [{note['title']}]({fname}) — {tags}")
        except Exception as e:
            stats["failed"].append(f"[转换失败] {note['title']}: {e}")
    if index_rows:
        with open(os.path.join(base_dir, "index.md"), "w", encoding="utf-8") as f:
            f.write(f"# {os.path.splitext(os.path.basename(path))[0]}\n\n"
                    f"> 共 {len(index_rows)} 篇\n\n" + "\n".join(index_rows) + "\n")
    return stats


def main():
    ap = argparse.ArgumentParser(description="印象笔记 .notes/.enex(含加密) → Markdown 批量转换")
    ap.add_argument("src", help=".notes/.enex 文件或目录")
    ap.add_argument("out", nargs="?", default="markdown_out", help="输出目录 (默认 markdown_out)")
    ap.add_argument("--password", help="加密密码 (也可用环境变量 NOTES2MD_PASSWORD)")
    ap.add_argument("--flat", action="store_true", help="平面输出, 不按笔记本建子目录")
    args = ap.parse_args()

    password = args.password or os.environ.get("NOTES2MD_PASSWORD")
    if not password:
        print("错误: 必须提供加密密码 (--password 或环境变量 NOTES2MD_PASSWORD)")
        sys.exit(2)

    os.makedirs(args.out, exist_ok=True)
    files = sorted(f for f in os.listdir(args.src) if f.lower().endswith((".notes", ".enex"))) if os.path.isdir(args.src) else [args.src]
    if not files:
        print("未找到 .notes/.enex 文件")
        sys.exit(1)
    total = {"notes": 0, "ok": 0, "empty": 0, "resources": 0, "failed": 0}
    for fn in files:
        p = os.path.join(args.src, fn) if os.path.isdir(args.src) else fn
        st = convert_file(p, args.out, password, args.flat)
        print(f"[{'!!' if st['failed'] else 'OK'}] {os.path.basename(p)}: {st['notes']} 篇 "
              f"(成功{st['ok']}/空{st['empty']}), 资源{st['resources']}, 失败{len(st['failed'])}")
        for f_ in st["failed"]:
            print("      ", f_)
        total["notes"] += st["notes"]; total["ok"] += st["ok"]; total["empty"] += st["empty"]
        total["resources"] += st["resources"]; total["failed"] += len(st["failed"])
    print(f"完成: {len(files)} 文件 / {total['notes']} 篇 (成功{total['ok']}/空{total['empty']}/失败{total['failed']}) / 资源{total['resources']} -> {args.out}")
    if total["failed"]:
        print("提示: 若有解密失败, 多为密码错误——请核对导出时设置的加密密码")
        sys.exit(3)


if __name__ == "__main__":
    main()
