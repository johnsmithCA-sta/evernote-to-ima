#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_password.py — 快速验证印象笔记 .notes/.enex 加密密码是否正确

原理: 印象笔记 ENC0 加密在密文尾部带 HMAC-SHA256 校验值,
      密码正确时 HMAC 才会匹配 —— 因此可离线、秒级判断密码对错。

用法:
    python3 verify_password.py <文件.notes> --password <候选密码>
    # 或环境变量: export NOTES2MD_PASSWORD='密码'; python3 verify_password.py <文件>

返回:
    "密码正确" 表示该密码可解密此文件(可继续用 notes2md.py 全量转换)
    "密码不正确" 表示此密码无效, 请更换候选密码再试
"""
import argparse
import base64
import hashlib
import hmac
import os
import re
import sys
import xml.etree.ElementTree as ET


def extract_first_cipher(path: str) -> bytes:
    """提取文件中第一篇加密 content 的密文(原始字节)。"""
    with open(path, encoding="utf-8") as f:
        data = f.read()
    # 遍历所有 content, 返回第一个 base64:aes 的
    for ev, el in ET.iterparse(path, events=("end",)):
        if el.tag.rsplit("}", 1)[-1] == "content" and (el.get("encoding") or "") == "base64:aes" and el.text:
            b64 = el.text.replace("\n", "")
            cipher = base64.b64decode(b64)
            el.clear()
            return cipher
    raise ValueError("文件中未找到 base64:aes 加密内容")


def check_password(cipher: bytes, password: str) -> bool:
    if cipher[:4] != b"ENC0" or len(cipher) < 84:
        raise ValueError("不是 ENC0 加密格式")
    salt, salthmac = cipher[4:20], cipher[20:36]
    body, bodyhmac = cipher[:-32], cipher[-32:]
    keyhmac = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salthmac, 50000, 16)
    return hmac.compare_digest(
        hmac.new(keyhmac, body, hashlib.sha256).digest(), bodyhmac)


def main():
    ap = argparse.ArgumentParser(description="验证印象笔记加密密码")
    ap.add_argument("src", help=".notes/.enex 文件")
    ap.add_argument("--password", help="候选密码 (也可用环境变量 NOTES2MD_PASSWORD)")
    args = ap.parse_args()
    password = args.password or os.environ.get("NOTES2MD_PASSWORD")
    if not password:
        print("请提供密码: --password 或环境变量 NOTES2MD_PASSWORD")
        sys.exit(2)
    try:
        cipher = extract_first_cipher(args.src)
    except Exception as e:
        print(f"读取失败: {e}")
        sys.exit(1)
    if check_password(cipher, password):
        print(f"[✓] 密码正确 —— 此密码可解密 {os.path.basename(args.src)}")
        sys.exit(0)
    else:
        print(f"[×] 密码不正确 —— 请更换候选密码再试")
        sys.exit(1)


if __name__ == "__main__":
    main()
