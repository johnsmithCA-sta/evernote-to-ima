#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""upload_cos.py — 用 ima create_media 返回的 COS 临时凭证上传文件到腾讯云 COS

凭证获取方式（按推荐优先级，前两种不落盘）:
  1. 环境变量: export COS_CRED_JSON='<create_media 返回的完整 JSON>'
       python3 upload_cos.py --env <本地文件>
  2. 标准输入: echo '<create_media 返回的完整 JSON>' | python3 upload_cos.py - <本地文件>
  3. 兼容旧用法(凭证文件，用后请立即删除): python3 upload_cos.py <凭证json文件> <本地文件>

用法:
  python3 upload_cos.py (--env | -) <本地文件路径>
  python3 upload_cos.py <凭证json文件> <本地文件路径>   # 兼容旧用法
"""
import json
import os
import sys

from qcloud_cos import CosConfig, CosS3Client


def _load_cred_from_env():
    raw = os.environ.get("COS_CRED_JSON")
    if not raw:
        return None
    return json.loads(raw)


def _load_cred_from_stdin():
    if sys.stdin.isatty():
        return None
    raw = sys.stdin.read()
    if not raw or not raw.strip():
        return None
    return json.loads(raw)


def upload(cred_data: dict, file_path: str):
    c = cred_data["cos_credential"]
    config = CosConfig(
        Region=c["region"],
        SecretId=c["secret_id"],
        SecretKey=c["secret_key"],
        Token=c["token"],
        Scheme="https",
    )
    client = CosS3Client(config)
    with open(file_path, "rb") as f:
        resp = client.put_object(Bucket=c["bucket_name"], Body=f, Key=c["cos_key"])
    print(f"[OK] 已上传 -> {c['cos_key']} (etag={resp.get('ETag', '')})")
    return cred_data["media_id"]


def main():
    args = sys.argv[1:]
    cred_data = None
    file_path = None
    source = ""

    if args and args[0] in ("--env", "-e"):
        cred_data = _load_cred_from_env()
        file_path = args[1] if len(args) > 1 else None
        source = "环境变量 COS_CRED_JSON"
    elif args and args[0] in ("-", "--stdin"):
        cred_data = _load_cred_from_stdin()
        file_path = args[1] if len(args) > 1 else None
        source = "标准输入"
    else:
        # 兼容旧用法: <凭证json文件> <本地文件>
        if len(args) != 2:
            print(__doc__)
            sys.exit(1)
        with open(args[0], encoding="utf-8") as f:
            cred_data = json.loads(f.read())
        file_path = args[1]
        source = f"凭证文件 {args[0]}"

    if cred_data is None:
        print("[FAIL] 未获取到凭证：--env 需设置 COS_CRED_JSON，--stdin 需从标准输入传入 JSON", file=sys.stderr)
        sys.exit(1)
    if not file_path:
        print("[FAIL] 缺少本地文件路径", file=sys.stderr)
        sys.exit(1)

    if source.startswith("凭证文件"):
        print(f"[提示] 已从 {source} 读取凭证；为安全起见请用后立即删除该文件，或改用 --env / --stdin 方式避免凭证落盘。", file=sys.stderr)

    media_id = upload(cred_data, file_path)
    return media_id


if __name__ == "__main__":
    main()
