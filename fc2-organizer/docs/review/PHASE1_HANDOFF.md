# PHASE1_HANDOFF.md

```text
Phase: 1 — 冻结公共数据契约（FC2 Metadata Core：模型 / SourceResult / 番号标准化）
Review Base: 5ac9d69784fafdb754c4126ec4641662fb7b626c   (Phase 0 已通过独立复查的 Code Head)
Code Review Candidate: 1e2f4d753aad9050a79589776abda74f2e063e7b
Docs Head: 待本 docs commit 完成后由最终会话消息明确报告
```

## Scope

只建立独立于 Amane 的 FC2 Metadata Core（模型契约 + 错误/状态语义 + 番号标准化），**不访问真实网站，不实现 scraper，不实现 source HTTP，不实现多源 aggregator，不实现 batch engine，不实现 Amane plugin adapter，不写 NFO，不移动文件，不操作 Amane DB**。`upstream/amane/` 未被读取/修改（本 Phase 未重新克隆或引用 Amane 源码，只依据 Phase 0 报告中已记录的字段形状差异做设计参考）。所有测试 100% 离线。

## 变更文件

Diff 范围 `5ac9d69` → `1e2f4d7`（13 个新文件，0 修改/删除）：

```text
fc2-organizer/pyproject.toml                                          (new)
fc2-organizer/docs/specifications/FC2_METADATA_CORE_CONTRACT.md       (new)
fc2-organizer/src/fc2_metadata_core/__init__.py                       (new)
fc2-organizer/src/fc2_metadata_core/errors/__init__.py                (new)
fc2-organizer/src/fc2_metadata_core/models/__init__.py                (new)
fc2-organizer/src/fc2_metadata_core/models/metadata.py                (new)
fc2-organizer/src/fc2_metadata_core/models/source_result.py           (new)
fc2-organizer/src/fc2_metadata_core/normalize/__init__.py             (new)
fc2-organizer/src/fc2_metadata_core/normalize/fc2_number.py           (new)
fc2-organizer/tests/contract/test_core_independent_of_amane.py        (new)
fc2-organizer/tests/unit/core/test_metadata.py                        (new)
fc2-organizer/tests/unit/core/test_normalize_fc2_number.py            (new)
fc2-organizer/tests/unit/core/test_source_result.py                   (new)
```

`fc2-organizer/src/README.md`、`fc2-organizer/tests/README.md`、`fc2-organizer/CLAUDE.md` 均未修改（沿用 Phase 0 状态的占位说明，不影响本 Phase 的实际实现）。

## 新增的模型 / 合同

- **`NormalizedMetadata`**（`models/metadata.py`）：独立于 Amane `MediaMetadata` 的数据类，字段包括 `number/title/studio/publisher/release/runtime/actors/tags/plot/poster_urls/thumb_urls/fanart_urls/extrafanart/source_urls/external_ids/field_sources`。刻意保留 Phase 0 报告指出的复数 `external_ids`/`source_urls`（Amane 当前是单数 `external_id`/`source_url`），字段收窄留给 Phase 5 Adapter。所有 list/dict 字段用 `field(default_factory=...)`，两实例互不共享底层容器。`meets_minimum_success()` 冻结「canonical number + 非空 title」的最低成功条件。
- **`SourceResult`**（`models/source_result.py`，frozen dataclass）：`source_id/status/metadata/elapsed_ms/error_kind/error_detail`。`SourceStatus` 7 态：`success/not_found/blocked/rate_limited/network_error/parse_error/invalid_response`。独立 `SourceErrorKind` 枚举与非 success 状态一一对应。`__post_init__` 强制以下不变式：`source_id` 非空、`elapsed_ms` 非负、success 必须有满足最低成功的 metadata 且不得带 error 信息、每个失败态必须带匹配的 `error_kind` 与非空 `error_detail`、`not_found/blocked/rate_limited/network_error` 禁止携带 metadata、`parse_error/invalid_response` 允许携带 partial（未达最低成功）metadata 但禁止携带已达最低成功的 metadata。
- **`fc2_metadata_core.errors`**：`FC2MetadataCoreError`/`MetadataContractError`/`SourceResultContractError`，替代裸 `raise Exception("failed")` 作为契约违规的统一异常协议。

## 规范化语法

`fc2_metadata_core.normalize.normalize_fc2_number()`（详见 `docs/specifications/FC2_METADATA_CORE_CONTRACT.md` §4 与 `normalize/fc2_number.py` 模块 docstring）：

```text
(?<![A-Za-z0-9]) FC2 [-_]* (?:PPV[-_]*)? (\d{5,8}) (?![A-Za-z0-9])
```

- 大小写不敏感，可出现在任意噪声字符串中间。
- `FC2`/`PPV` 之间允许 0 个或多个 `-`/`_` 分隔符，也允许没有分隔符。
- 数字位数限定 5-8 位（`MIN_FC2_DIGITS`/`MAX_FC2_DIGITS`），拒绝过短（分辨率类）与过长（日期/时间戳/哈希粘连）数字串。
- 词边界规则：`FC2` 前一个字符与数字串后一个字符若为 `[A-Za-z0-9]` 则拒绝匹配——这是防止「看到 FC2 + 任意数字就算」朴素解析器误判的关键规则（例如 `SUPERFC2-1234567`、`FC2-1234567EXTRA` 均被拒绝）。
- 结果类型 `FC2NumberResult`：`status ∈ {RECOGNIZED, NOT_FC2}`，`canonical` 当且仅当 `RECOGNIZED` 时非 `None`（由 `__post_init__` 断言保证，不是约定）。

## 正向回归用例（已关闭，自动化）

`tests/unit/core/test_normalize_fc2_number.py::test_positive_dirty_filenames_normalize_to_canonical`（14 组参数化用例）覆盖规格书全部 5 种基础形态 + 扩展噪声：

```text
FC2-PPV-1234567 / FC2PPV-1234567 / FC2PPV1234567 / FC2-1234567 / FC2_1234567
[广告]FC2PPV-1234567 / xxx@FC2PPV-1234567
FC2-PPV-1234567.mp4（扩展名后缀）
[中文字幕]FC2-PPV-1234567-CD1.mkv（前缀+CD 后缀噪声）
some.download.site_FC2PPV-1234567_1080p.mp4（下划线分隔噪声）
fc2-1234567（小写）
"  FC2-1234567  "（首尾空白）
(FC2--1234567)（重复分隔符+括号噪声）
FC2-4825061（规格书示例真实番号）
```

全部统一输出 `FC2-1234567`（或对应真实番号）。

## 复查者 F-03 的关闭证据

Phase 0 HANDOFF 明确要求：`[广告]FC2PPV-1234567` 与 `xxx@FC2PPV-1234567` 必须在 Phase 1 有真实自动化回归，不能只是文档记录的人工验证。本 Phase 新增专门测试：

```text
tests/unit/core/test_normalize_fc2_number.py::test_f03_regression_ad_prefix_noise_closed
tests/unit/core/test_normalize_fc2_number.py::test_f03_regression_xxx_at_prefix_noise_closed
```

两者均已实际运行通过（见下方 Tests run / Exact commands），且同时被包含在上方 14 组参数化正向用例中做二次覆盖。

## 反向回归用例（防误识别）

`tests/unit/core/test_normalize_fc2_number.py::test_negative_misidentification_regression`（19 组参数化用例），针对语法本身设计的攻击性用例，而非机械照抄需求文字：

```text
1234567.mp4                      纯数字文件名
SSNI-999.mp4                     其它厂牌番号
2024-01-15.mp4                   日期
1920x1080.mkv                    分辨率
Movie.Title.CD1.mp4 / CD2.mkv    CD 标记但无 FC2 token
readme.txt                       普通文本
FC2.mp4                          只有 FC2 无数字
FC2 configuration notes.txt      FC2 关键字但数字不相邻
FC2-12.mp4 / FC2-1234.mp4        数字位数不足（<5）
FC2-123456789012345.mp4          数字粘连过长
SUPERFC2-4825061.mp4             FC2 前面粘连字母（word-boundary 攻击）
PERFC2PPV1234567.mp4             FC2 前面粘连字母 + PPV 变体
FC2-1234567EXTRA.mp4             数字后面粘连字母
FC2-1234567890123.mp4            数字粘连更多数字（总长超限）
20240115_1234567890123.mp4       长无关数字串，无 FC2 token
Amane-Release-v0.15.0-build.zip  含版本号但无 FC2 token
""（空字符串）
"just a plain filename without any code.mkv"
```

全部正确返回 `FC2RecognitionStatus.NOT_FC2` / `canonical=None`。另有 `TestIsValidFc2Number` 类专门测试 canonical 格式校验器本身的正负样例。

## 复查者 F-02 的关闭证据

Phase 0 MEDIUM note：Amane `parse_file_info(path=...)` 存在强制 fallback，真正无法识别的文件也可能被伪装成 `TOTALLY-998`/`ContentType.CENSORED` 之类的假结果，不能作为「这是不是有效 FC2」的权威判据（NORM-01）。

本 Phase 闭合方式：
1. `normalize_fc2_number()` 完全由 Core 自己的正则语法判定，未 import、未调用、未引用 Amane 任何代码或数据（见下方"Core 不依赖 Amane"证据）。
2. 返回类型 `FC2NumberResult` 只有两种显式结果：`RECOGNIZED`（带合法 canonical）或 `NOT_FC2`（`canonical=None`），由 `__post_init__` 断言强制保证，不存在「猜测/兜底编号」的第三种结果。
3. `tests/unit/core/test_normalize_fc2_number.py` 的负向回归集专门验证「不会把普通数字/其它番号/长数字误判为 FC2」，其中不含任何依赖 Amane fallback 行为的假设。
4. `NormalizedMetadata.has_valid_canonical_number()` 同样只依赖 Core 自己的 `is_valid_fc2_number()`，不引用 Amane。

## 已运行的测试

```text
tests/contract/test_core_independent_of_amane.py   (9 tests)
tests/unit/core/test_metadata.py                    (16 tests)
tests/unit/core/test_normalize_fc2_number.py        (43 tests)
tests/unit/core/test_source_result.py               (32 tests)
```

覆盖：`NormalizedMetadata`（最低成功语义、mutable-default 隔离、runtime 类型校验）、`SourceResult`（7 态状态机全部合法/非法组合）、FC2 番号标准化（正向/负向回归集）、错误/状态语义、Core 不依赖 Amane（静态 AST 扫描 + 运行时阻断 amane import 后仍可正常 import 并使用全部公开 API）。

**全部测试已在本次会话中实际运行，非声称通过。**

## 确切命令

```bash
cd fc2-organizer
python3 --version
# Python 3.11.15

python3 -m pytest -v
# ...
# 100 passed in 0.13s

python3 -m pytest -q
# 100 passed in 0.09s

python3 -m pytest --collect-only -q
# 100 tests collected in 0.03s
```

## 通过 / 失败计数

```text
Python version: 3.11.15
Collected:      100
Passed:         100
Failed:         0
Skipped:        0
```

## 已知局限

1. FC2 数字位数窗口（5-8 位）是 Phase 1 的设计决策，不是从任何权威来源核实的上游事实；已在 `fc2_number.py` docstring 与 contract 文档中明确标注为「可由后续 Phase 用证据修订」。
2. `release` 字段类型选择 `str | None`（预期 ISO 日期字符串）而非 `datetime.date`，未做日期格式校验——Phase 1 判定日期解析属于具体 source 解析器（Phase 2+）的职责，不在 Core 契约层强制。
3. `NormalizedMetadata` 未设为 frozen（`SourceResult` 是 frozen），因为 Phase 3 字段级聚合大概率需要对同一 `NormalizedMetadata` 做增量合并；这是否需要在 Phase 3 改为不可变+显式 merge 函数，留给 Phase 3 实施者判断。
4. `field_sources` 的值类型选择 `dict[str, list[str]]`（每字段的贡献 source 列表）而非单一 source id，以支持规格书 Phase 3 描述的 `tags <- A + C` 式多来源贡献；Phase 3 实现聚合逻辑时需要遵循此形状，不应擅自改回单一来源。
5. 未安装/未验证真实 `amane` 包本身（`tests/contract` 里的"Amane 未安装"断言只是确认本环境确实没有 `amane`，不代表已验证过真实 Amane 包导入行为）。

## 已知的外部来源不稳定性

不适用 / Phase 1 未访问任何外部来源。

## 安全考量

- 未新增任何网络访问、文件系统写入（测试目录外）、凭据/Cookie 处理代码。
- `fc2_metadata_core` 全部代码路径为纯 CPU 计算（正则匹配、dataclass 校验），无 I/O。
- 未在任何文件中写入 secret/token/cookie。
- `git status`/`git diff --stat` 已核对本次 commit 范围仅含 13 个新文件，均在 `fc2-organizer/` 内，未触及 `upstream/amane/`（该目录本身不存在于当前工作区，本 Phase 未重新克隆）。

## Windows 运行

Windows NOT run（本次会话运行环境为 Linux 容器；本 Phase 代码为纯 Python 标准库实现，无平台相关路径/系统调用，但未做 Windows 实测，如实标注）。

## Amane 集成运行

Not run / not applicable to Phase 1（本 Phase 明确不接入 Amane，`fc2_metadata_core` 与 `amane` 完全解耦，见 §1 Core 不依赖 Amane 的自动化证据）。

## 复查者应重点关注的内容

1. `SourceResult` 的状态/错误不变式是否存在遗漏的非法组合（例如是否应该允许 `NOT_FOUND` 携带诊断性 partial metadata——本实现选择不允许，理由见 contract 文档表格）。
2. FC2 番号语法的 5-8 位数字窗口与词边界规则是否合理，是否有真实场景会被误判为负例（例如未来 FC2 编号突破 8 位数字时需要修订上限）。
3. `tests/contract/test_core_independent_of_amane.py` 的运行时 import 阻断机制（`sys.meta_path` finder）是否真正能捕获所有可能的隐式 `amane` 依赖路径（目前只在测试期间阻断，且仅覆盖本次会话已导入的 core 模块列表）。
4. `NormalizedMetadata`/`SourceResult` 的字段形状是否已经为 Phase 3（字段级聚合）与 Phase 5（Amane adapter 收窄映射）做好铺垫，是否存在会导致后续 Phase 返工的设计缺陷。

## 范围之外

```text
真实网站访问
scraper 实现
source HTTP 实现
多源 aggregator（Phase 3）
batch engine（Phase 4）
Amane plugin adapter（Phase 5）
NFO 写入
文件移动/整理
Amane DB 操作
Windows 平台实测
Amane 集成运行
```

## 下一阶段尚未开始（Next phase NOT started）

```text
Phase 2 NOT started
```

---

```text
READY FOR INDEPENDENT REVIEW
```
