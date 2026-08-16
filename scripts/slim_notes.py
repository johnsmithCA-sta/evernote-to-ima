#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
slim_notes.py — 笔记瘦身：去除网页剪藏的非正文内容

处理内容:
  1. 文本瘦身: 空链接/纯图片链接行、广告导航关键词行、与标题重复的正文标题、纯符号垃圾行
  2. 图片瘦身: 删除 1x1 跟踪像素图及超小图(宽高均 <20px 的 icon/logo), 并从正文移除引用
  3. 空白压缩

用法: python3 slim_notes.py <markdown目录> [--dry-run]
"""
import glob
import os
import re
import struct
import sys

AD_KEYWORDS = [
    "广告", "关注公众号", "扫码", "阅读原文", "点击查看", "相关推荐",
    "猜你喜欢", "查看更多", "下载app", "app下载", "下载客户端",
    "免责声明", "本文来源", "长按识别", "点击关注", "点击购买",
    "点击这里", "阅读全文", "点击阅读", "关注我们", "商务合作",
]

LINK_LINE = re.compile(r"^(\[\]\([^)]*\)|!\[[^\]]*\]\([^)]*\)|\s*)+$")
SYMBOL_LINE = re.compile(r"^[-—=*·•]{3,}$")


def image_size(path: str):
    """读取 PNG/JPEG/GIF 尺寸, 返回 (w, h) 或 None。纯标准库实现。"""
    try:
        with open(path, "rb") as f:
            head = f.read(24)
        if head[:8] == b"\x89PNG\r\n\x1a\n":
            w, h = struct.unpack(">II", head[16:24])
            return w, h
        if head[:6] in (b"GIF87a", b"GIF89a"):
            w, h = struct.unpack("<HH", head[6:10])
            return w, h
        if head[:2] == b"\xff\xd8":  # JPEG: 扫描 SOF marker
            with open(path, "rb") as f:
                data = f.read()
            i = 2
            while i < len(data):
                if data[i] != 0xFF:
                    i += 1
                    continue
                marker = data[i + 1]
                if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                              0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                    h = struct.unpack(">H", data[i + 5:i + 7])[0]
                    w = struct.unpack(">H", data[i + 7:i + 9])[0]
                    return w, h
                length = struct.unpack(">H", data[i + 2:i + 4])[0]
                i += 2 + length
            return None
    except Exception:
        return None
    return None


def slim_file(path: str, dry: bool) -> dict:
    with open(path, encoding="utf-8") as f:
        text = f.read()
    m = re.match(r"^---\n(.*?)\n---\n\n", text, re.S)
    if not m:
        return {"file": path, "text": 0, "img": 0}
    fm = m.group(0)
    title = re.search(r"title:\s*(.+)", m.group(1))
    title = title.group(1).strip() if title else ""
    body = text[m.end():]

    lines = body.splitlines()
    out = []
    text_removed = 0
    for ln in lines:
        s = ln.strip()
        if not s:
            out.append("")
            continue
        if LINK_LINE.match(s):
            text_removed += 1
            continue
        if s.count("[](") >= 2:  # 含多个空链接的导航/页眉行
            text_removed += 1
            continue
        if any(k in s for k in AD_KEYWORDS):
            text_removed += 1
            continue
        if s in (f"# {title}", f"## {title}", f"### {title}"):
            text_removed += 1
            continue
        if SYMBOL_LINE.match(s):
            text_removed += 1
            continue
        out.append(s)

    body2 = "\n".join(out)
    body2 = re.sub(r"\n{2,}", "\n\n", body2).strip()

    # 图片瘦身: 找出本文件引用的资源图片, 删 1x1 / 超小图
    res_dir = os.path.join(os.path.dirname(path), "_resources")
    img_removed = 0
    refs = re.findall(r"!\[[^\]]*\]\((_resources/[^)]+)\)", body2)
    for ref in set(refs):
        fp = os.path.join(os.path.dirname(path), ref)
        if not os.path.exists(fp):
            continue
        sz = image_size(fp)
        if sz is None:
            continue
        w, h = sz
        if w <= 1 and h <= 1:
            tiny = True
        elif w < 20 and h < 20:
            tiny = True
        else:
            tiny = False
        if tiny:
            body2 = re.sub(r"!\[[^\]]*\]\(" + re.escape(ref) + r"\)\n?", "", body2)
            if dry:
                pass
            else:
                try:
                    os.remove(fp)
                except OSError:
                    pass
            img_removed += 1

    new = fm + body2 + "\n"
    if not dry and new != text:
        with open(path, "w", encoding="utf-8") as f:
            f.write(new)
    return {"file": path, "text": text_removed, "img": img_removed}


def main():
    root = sys.argv[1]
    dry = "--dry-run" in sys.argv
    files = sorted(glob.glob(os.path.join(root, "**", "*.md"), recursive=True))
    files = [f for f in files if os.path.basename(f) != "index.md"]
    t_total = i_total = 0
    for f in files:
        r = slim_file(f, dry)
        t_total += r["text"]
        i_total += r["img"]
    print(f"{'[DRY-RUN] ' if dry else ''}瘦身完成: {len(files)} 篇, 删除文本行 {t_total}, 删除无效图片 {i_total}")
    if dry:
        print("以上为预览, 未实际修改文件 (去掉 --dry-run 正式执行)")


if __name__ == "__main__":
    main()
