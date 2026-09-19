# FC2 Organizer — Claude Code 使用顺序

建议至少使用 3 类彼此独立的 Claude Code session。

## Session A：实施者

把以下内容一起给它：
- `FC2_Organizer_v1.0_开发规格书.md`
- `ClaudeCode_00_实施总提示词.md`

第一次只允许执行 Phase 0。
Phase 0 独立审查通过以后，再让同一个实施 session 进入 Phase 1。

每一个 Phase 都：
1. 实施；
2. 测试；
3. commit；
4. 生成 HANDOFF；
5. 停止。

不要连续把多个 Phase 混在一个 review diff 里。

## Session B：独立 reviewer

新开 Claude Code session。
给它：
- 规格书；
- `ClaudeCode_10_独立复查提示词模板.md`；
- 实施者的 HANDOFF；
- repository；
- Review Base / Code Head。

Reviewer 不允许修代码。

如果 FAIL，记录 R1-01、R1-02...。

## Session A：R1 修复

把 reviewer finding 原文交回实施 session。
要求：
- 只修 finding；
- 补回归测试；
- 新 commit；
- 新 HANDOFF；
- 不提前做下一 Phase。

## Session C：R1 closure reviewer

最好再开一个新 session。
使用同一复查模板，但执行“增量闭合复查”：
- finding 是否闭合；
- 有没有打回以前机制；
- 有没有新 correctness regression。

## Phase 通过后

回到实施 Session A 进入下一 Phase。

## 最终 Session Z：Release reviewer

全部 Phase PASS 且全部 R1/R2 finding CLOSED 后：
- 新开从未参与过项目的 Claude Code session；
- 使用 `ClaudeCode_20_最终验收提示词.md`；
- 做 Release Candidate 最终验收。

---

## 建议 Git 分支

```text
main
phase/0-amane-recon
phase/1-core-contracts
phase/2-sources
phase/3-aggregator
phase/4-batch
phase/5-amane-adapter
phase/6-integration
phase/7-organize
phase/8-release
```

如果你倾向线性开发，也可以单分支逐 Phase 提交。
关键不是分支数量，而是每一轮 review 必须有冻结的：

```text
Review Base
→
Code Review Candidate
```

---

## 第一条发给实施者的话

直接粘贴：

```text
请读取《FC2 Organizer v1.0 开发规格书》和《ClaudeCode_00_实施总提示词》。

现在只执行 Phase 0。
不要编写 Phase 1 业务代码。
不要修改 Amane upstream。
完成后提交 commit，给出 Review Base、Code Review Candidate、PHASE0_AMANE_INTEGRATION_REPORT.md 和 PHASE0_HANDOFF.md，然后停止等待独立复查。
```
