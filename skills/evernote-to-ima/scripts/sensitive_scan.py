#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sensitive_scan.py — 上云前敏感信息扫描

在笔记合并、上传 ima/COS 前，扫描 Markdown 目录中可能包含的个人敏感信息，
输出「疑似含敏感信息笔记清单」供用户确认是否排除，并可作为迁移审计记录。

用法:
  python3 sensitive_scan.py <markdown目录> [--json 报告路径] [--keywords 关键词列表]
"""

import argparse
import json
import os
import re
import sys

# (标签, 正则, 说明) — 命中任一即标记
SENSITIVE_PATTERNS = [
    ("身份证号", re.compile(r"\d{17}[\dXx]"), "疑似身份证号码"),
    ("手机号", re.compile(r"1[3-9]\d{9}"), "疑似手机号码"),
    ("银行卡号", re.compile(r"\b(?:\d[ -]?){13,19}\b"), "疑似银行卡号"),
    ("邮箱地址", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "邮箱地址"),
    ("疑似密码", re.compile(r"(?i)(password|passwd|pwd|密码|口令)\s*[:：=]\s*\S{4,}"), "疑似密码/口令明文"),
    ("账号密码备份", re.compile(r"(账号|账户|登录|密码)\s*(备份|备忘|清单|记录|汇总)"), "疑似账号密码备份内容"),
    ("个人日记", re.compile(r"(日记|diary|journal|私人|隐私)"), "疑似个人隐私内容"),
]

# 默认排除关键词（用户可覆盖）——合并/上传时建议排除的笔记本目录
DEFAULT_EXCLUDE_KEYWORDS = ["个人资料", "日记", "密码", "账号备份", "私人"]


def scan_text(text):
    """返回命中的标签列表。"""
    hits = []
    for label, pattern, _desc in SENSITIVE_PATTERNS:
        if pattern.search(text):
            hits.append(label)
    return hits


def scan_dir(root):
    results = []
    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            if not fn.endswith(".md"):
                continue
            full = os.path.join(dirpath, fn)
            try:
                with open(full, encoding="utf-8") as f:
                    text = f.read()
            except (OSError, UnicodeDecodeError):
                continue
            hits = scan_text(text)
            if hits:
                results.append({
                    "file": os.path.relpath(full, root),
                    "hits": list(dict.fromkeys(hits)),  # 去重保序
                })
    return results


def main():
    ap = argparse.ArgumentParser(description="上云前敏感信息扫描")
    ap.add_argument("root", help="待扫描的 Markdown 目录")
    ap.add_argument("--json", help="将扫描结果输出为 JSON 审计报告路径")
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        print(f"[FAIL] 目录不存在: {root}")
        sys.exit(1)

    results = scan_dir(root)

    print(f"扫描完成：共检查目录 {root}")
    if not results:
        print("✓ 未发现含敏感信息的笔记")
    else:
        print(f"⚠ 发现 {len(results)} 篇笔记疑似含敏感信息：")
        for r in results:
            print(f"  - {r['file']}  ->  {', '.join(r['hits'])}")
        print("\n建议：上云前人工确认这些笔记是否应排除（个人日记、账号密码备份等敏感笔记不建议导入云端）。")

    if args.json:
        report = {
            "scanned_root": root,
            "suspect_count": len(results),
            "suspects": results,
            "suggested_exclude_keywords": DEFAULT_EXCLUDE_KEYWORDS,
        }
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"审计报告已保存: {args.json}")

    # 退出码：有疑似敏感笔记返回 2，便于脚本化门禁（有则需人工确认）
    sys.exit(2 if results else 0)


if __name__ == "__main__":
    main()
