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
