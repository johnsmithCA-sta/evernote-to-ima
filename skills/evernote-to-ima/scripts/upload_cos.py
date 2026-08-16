#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""upload_cos.py — 用 ima create_media 返回的 COS 临时凭证上传文件到腾讯云 COS

用法: python3 upload_cos.py <凭证json文件> <本地文件路径>
"""
import json
import sys

from qcloud_cos import CosConfig, CosS3Client


def upload(cred_json: str, file_path: str):
    data = json.loads(cred_json)
    c = data["cos_credential"]
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
    return data["media_id"]


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("用法: upload_cos.py <凭证json> <本地文件>")
        sys.exit(1)
    upload(open(sys.argv[1], encoding="utf-8").read(), sys.argv[2])
