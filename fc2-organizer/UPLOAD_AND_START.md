# 上传 GitHub 后如何开始

## 1. 上传本目录全部内容到一个新的 GitHub 仓库

建议仓库名：

`fc2-organizer`

不要另外上传压缩包本身。

## 2. 第一轮给实施 Claude Code 的指令

让 Claude Code 打开本仓库，然后发送：

> 请读取根目录 `CLAUDE.md`、`docs/specifications/FC2_Organizer_v1.0_开发规格书.md` 和 `docs/prompts/ClaudeCode_00_实施总提示词.md`。
>
> 现在只执行 Phase 0。不要修改 Amane upstream，不要进入 Phase 1。完成后提交 commit，给出 Review Base、Code Review Candidate、`PHASE0_AMANE_INTEGRATION_REPORT.md` 和 `docs/review/PHASE0_HANDOFF.md`，然后停止等待独立复查。

## 3. Phase 0 完成后

新开一个独立 Claude Code session，读取：

- 规格书
- `docs/prompts/ClaudeCode_10_独立复查提示词模板.md`
- `docs/review/PHASE0_HANDOFF.md`
- 实施者给出的 Review Base / Code Review Candidate

Reviewer 不得修改代码。

## 4. 最终发布

全部 Phase 和修复轮次通过后，新开从未参与过前面工作的 Claude Code session，使用：

`docs/prompts/ClaudeCode_20_最终验收提示词.md`
