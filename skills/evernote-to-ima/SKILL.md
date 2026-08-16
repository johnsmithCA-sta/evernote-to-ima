---
name: evernote-to-ima
description: >-
  印象笔记/evernote 数据一键迁移到 ima 知识库的端到端流水线。自动完成官方 API
  同步导出明文 enex、批量转换 Markdown、网页剪藏去广告瘦身、按笔记本合并省流、
  上传 ima 知识库。当用户需要把印象笔记迁移到 ima / Obsidian 等 Markdown 知识库、
  或处理 .notes/.enex 导出文件时使用。
version: "1.0.0"
license: MIT
tags: [印象笔记, evernote, 迁移, ima, 知识库, markdown]
---

# 印象笔记 → ima 迁移工具

将印象笔记（evernote）数据批量迁移到 ima 知识库的端到端流水线，覆盖：数据获取 → 格式转换 → 内容瘦身 → 智能导入。

## 触发词

- "把印象笔记迁移到 ima" / "迁移印象笔记数据"
- "处理 .notes / .enex 导出文件"
- "印象笔记转 Markdown / 转 ima 知识库"

## 执行流程

### 第 1 步：获取明文数据（绕开 .notes 加密）

新版印象笔记导出的 `.notes` 为系统级加密（与账号密码无关，无法直接解密）。
正确路径：使用 `evernote-backup`（需 Python 3 + pip 安装）通过官方 API 同步导出**明文 .enex**：

```bash
pip install evernote-backup
evernote-backup init-db --backend china -u <账号> -p <密码>   # 注意清除代理环境变量
evernote-backup sync
evernote-backup export <输出目录>     # 每个笔记本一个明文 .enex
```

> ⚠️ 若遇 `Evernote returned None for a required field` 报错：执行前先 `env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy` 清除本地代理。

### 第 2 步：转换 Markdown

```bash
python3 scripts/enex2md.py <enex目录> <markdown输出目录> --flat   # 或整个目录
# 保留笔记本层级批量转换:
python3 scripts/convert_all.py <enex目录> <markdown输出目录>
```

转换特性：表格、嵌套列表、代码块、引用、待办、图片附件解码、YAML 元数据（title/tags/created/updated）、每个笔记本自动生成 index.md。

### 第 3 步：瘦身（去广告与无效图）

```bash
python3 scripts/slim_notes.py <markdown目录>           # 正式执行
python3 scripts/slim_notes.py <markdown目录> --dry-run # 先预览
```

自动删除：网页剪藏的导航/空链接行、广告关键词行（关注公众号/扫码/阅读原文等）、与标题重复的正文标题、1x1 及 <20px 的跟踪图/图标。

### 第 4 步：按笔记本合并（省流，可选）

```bash
python3 scripts/merge_notes.py <markdown目录> <输出目录> \
    --map '{"顶级目录":"目标知识库名"}' --exclude '个人资料'
```

将数百篇笔记合并为少量文件，大幅减少 ima 导入次数。

### 第 5 步：导入 ima（需 ima-mcp 连接器）

流程：`create_media`（获取 COS 临时凭证 + media_id）→ 用 `upload_cos.py` 上传 COS → `add_knowledge` 入库：

```bash
python3 scripts/upload_cos.py <凭证json> <本地文件>   # 凭证来自 create_media 返回
```

## 依赖

- Python 3.6+（脚本为纯标准库，零第三方依赖）
- 可选：evernote-backup（第 1 步）、cos-python-sdk-v5（第 5 步 COS 上传）
- 系统 openssl（AES 解密）

## 边界与安全

- `.notes` 系统级加密无法解密，必须走 evernote-backup 官方 API
- 敏感笔记本（个人日记、账号密码备份）不建议导入云端
- `.enex` 明文备份请永久保留，转换完成前勿删印象笔记原数据
- COS 临时凭证有效期 12 小时，含凭证的中间文件用后立即删除
- 支持格式：印象笔记导出的 .enex/.notes（XML），输出 GitHub 风格 Markdown

## 使用示例

用户说"帮我把印象笔记迁移到 ima"时：
1. 引导用户安装 evernote-backup 并登录同步（账号密码仅本机用于 API 登录）
2. 导出明文 enex 后，运行 convert_all.py 批量转 Markdown
3. 运行 slim_notes.py 瘦身去广告
4. 按笔记本 merge_notes.py 合并省流
5. 通过 ima-mcp 连接器逐批 create_media → 上传 → add_knowledge 入库
6. 输出迁移报告：篇数、归库映射、失败清单、待办事项
