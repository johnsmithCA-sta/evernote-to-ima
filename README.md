# evernote-to-ima

将印象笔记（evernote）数据一键迁移到 ima 知识库的端到端流水线：官方 API 同步导出明文、批量转 Markdown、去广告瘦身、按笔记本合并省流、自动导入归库。

> 让 300 篇"吃灰收藏"变成 AI 可调用的知识资产 —— 全程约 3 小时，替代手动数天搬运。

## ✨ 功能特性

- **绕开 .notes 加密**：识别新版印象笔记"系统级加密"（与账号密码无关），通过官方 API 同步导出标准明文 `.enex`，100% 完整迁移
- **批量转换 Markdown**：表格、嵌套列表、代码块、引用、待办、图片附件、YAML 元数据（title/tags/created/updated）全保留
- **网页剪藏瘦身**：自动清除广告、导航、无效配图（实测单批清理 889 行 + 2 张无效图）
- **省流合并导入**：按笔记本合并，230 篇笔记仅需 12 次上传（省 95% 请求）
- **隐私保护**：敏感笔记本（个人日记、账号备份）自动排除，不上传云端
- **离线密码验证**：秒级判定印象笔记加密密码对错（HMAC 校验）

## 🔍 差异化说明 / Why This Project

与市面上同类工具（Yarle、万能导 wandao、yinxiang-md-sync 等）相比，本项目不是又一款"enex → Markdown 转换器"，而是一条**针对 ima 场景的端到端自动化流水线**，核心差异化：

| 差异化点 | 本项目 | 同类工具 |
|---|---|---|
| **.notes 系统级加密认知与绕过** | 识别新版印象笔记"系统级加密"（与账号密码无关）机制，给出官方 API 同步绕过路径，附离线密码验证工具 | 多数只处理明文 `.enex`，遇到加密 `.notes` 即失败 |
| **ima 定向端到端** | 打通 `create_media → COS 上传 → add_knowledge` 完整导入链，转换后直接入库，而非止步于 Markdown 文件 | 大多输出 md 后需用户手动搬运 |
| **网页剪藏瘦身** | 自动清除广告、导航、无效配图（实测单批 889 行 + 2 图），提升 AI 检索质量 | 无此环节 |
| **省流合并导入** | 按子笔记本合并，230 篇仅 12 次上传（省 95% 请求与 token） | 逐篇上传，成本高 |
| **AI Skill 形态** | 标准 Agent Skills 规范（agentskills.io），Agent 可直接驱动全流程 | 传统 CLI 工具，需手动执行 |

**一句话定位**：同类工具解决"文件转换"，本项目解决"数据资产化"——让印象笔记里的收藏变成 ima 中可被 AI 问答调用的知识，且全程自动化、可被 Agent 直接执行。

## 📦 快速开始

```bash
# 1. 同步导出明文 enex（需 Python 3 + pip）
pip install evernote-backup
evernote-backup init-db --backend china -u <账号> -p <密码>   # 遇代理报错先清 HTTP_PROXY 等
evernote-backup sync
evernote-backup export <输出目录>

# 2. 批量转 Markdown（保留笔记本层级）
python3 scripts/convert_all.py <enex目录> <markdown输出目录>

# 3. 瘦身去广告
python3 scripts/slim_notes.py <markdown目录>

# 4. 按笔记本合并省流
python3 scripts/merge_notes.py <markdown目录> <输出目录> --map '{"顶级目录":"知识库名"}'

# 5. 导入 ima（需 ima-mcp 连接器，create_media → COS 上传 → add_knowledge）
python3 scripts/upload_cos.py <凭证json> <本地文件>
```

## 🗂 目录结构

```
evernote-to-ima/
├── SKILL.md              # Agent Skills 规范（agentskills.io）
└── scripts/
    ├── enex2md.py        # ENEX/明文 → Markdown 核心转换
    ├── convert_all.py    # 目录递归批量转换
    ├── slim_notes.py     # 去广告/无效图瘦身
    ├── merge_notes.py    # 按子笔记本合并省流
    ├── upload_cos.py     # COS 上传（凭证来自 ima create_media）
    ├── notes2md.py       # 加密 .notes 处理（含 ENC0 解密参考）
    └── verify_password.py# 离线验证印象笔记加密密码
```

## 🖥 安装方式

```bash
# GitHub CLI（v2.90+）
gh skill install <owner>/evernote-to-ima

# Claude Code 插件市场
/plugin marketplace add <owner>/evernote-to-ima

# Agent Skills CLI
npx skills add https://github.com/<owner>/evernote-to-ima
```

支持环境：GitHub Copilot / Claude Code / Cursor / Codex / Gemini CLI / Antigravity 及所有兼容 Agent Skills 规范的 Agent。

## ⚠️ 边界与安全

- `.notes` 系统级加密无法直接解密，必须走 evernote-backup 官方 API
- 敏感笔记本（个人日记、账号密码备份）不建议导入云端
- `.enex` 明文备份请永久保留，转换完成前勿删印象笔记原数据
- COS 临时凭证有效期 12 小时，含凭证的中间文件用后立即删除

## 📄 License

[MIT](LICENSE)
