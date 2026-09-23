# CLAUDE.md — FC2 Organizer

你正在 FC2 Organizer 项目中工作。

## 必读文件

在执行任何开发前，按顺序读取：

1. `docs/specifications/FC2_Organizer_v1.0_开发规格书.md`
2. `docs/prompts/ClaudeCode_00_实施总提示词.md`
3. `docs/prompts/ClaudeCode_使用顺序.md`

## 当前正式上游

- Amane: `https://github.com/sqzw-x/amane.git`
- Baseline: `v0.15.0`

## 强约束

- 禁止修改 Amane upstream 源码。
- Amane 只能作为只读参考与兼容测试对象。
- 所有我们的业务代码必须位于本仓库。
- FC2 Metadata Core 必须与 Amane Adapter 分层。
- 必须支持当前可用的新片源 / 多片源。
- 必须支持批量操作。
- 单一 source 失败不得导致整批失败。
- 单一影片失败不得阻断其它影片。
- 不得把 secret / cookie / token 提交到 Git。
- 不得为了测试要求用户关闭 Windows Defender 或其它系统安全功能。

## 当前执行状态

首次接手本仓库时，只执行 Phase 0。

Phase 0 完成后必须：
- 提交 commit；
- 输出 Review Base；
- 输出 Code Review Candidate；
- 生成 `docs/PHASE0_AMANE_INTEGRATION_REPORT.md`；
- 生成 `docs/review/PHASE0_HANDOFF.md`；
- 停止，等待独立复查。

在独立复查 PASS 前，不得进入 Phase 1。

# 文档语言规范

本节为强制规则（状态：ACTIVE / 强制执行），详细说明见 `docs/文档语言规范.md`。

1. 本项目的系统语言、产品默认语言和项目文档默认语言均为**简体中文**。
2. 所有新增或维护的项目文档，正文必须使用简体中文，包括但不限于：开发规格书、Contract / 合同、Plan / 计划、HANDOFF / 交接、Review / 复查、Acceptance / 验收、开发提示词、治理说明、状态说明、README 类项目说明。
3. 只有以下内容允许保留英文：
   - Python / JavaScript / SQL 等代码；
   - API、function、class、enum、field 名称；
   - 文件名和目录名；
   - Git branch、SHA；
   - shell / PowerShell 命令；
   - traceback、pytest、Git 的原始输出；
   - HTTP / JSON / XML 等协议中的固定名称；
   - 外部库、项目、品牌、网站的正式名称；
   - 必须精确匹配的 error message 或字面量。
4. 标题中可以保留 Contract、Review、HANDOFF、PASS、FAIL、BLOCKED 等治理术语，但解释这些术语的正文必须使用中文。
5. 不得因为历史文档是英文，就继续默认用英文编写新文档。
6. 维护现有英文文档时，新增或重写的正文必须使用中文；如果任务明确属于“文档中文化迁移”，则应把该文档的英文说明正文完整翻译为中文。
7. 任何 AI 或开发者都不得根据仓库中的历史英文文档推断“系统语言 = 英文”“产品界面语言 = 英文”或“开发输出语言 = 英文”。本项目明确以中文为默认系统语言和项目语言。
8. 翻译文档时不得改变合同语义、requirement、finding ID、severity、SHA、测试数字、API 行为、状态或 frozen boundary，只能改变自然语言表达。
