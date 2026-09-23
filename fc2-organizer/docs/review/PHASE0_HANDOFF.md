# PHASE0_HANDOFF.md

```text
Phase: 0 — Amane v0.15.0 集成勘察（只读，无业务代码）
Review Base:   33b2bbc7e8acd8bc5e652888844b01e78830e741   (本仓库上一条提交 "Add files via upload")
Code Review Candidate: <本次 Phase 0 提交自身的 commit SHA — 由实施者在 commit 后于会话消息中给出，
                        亦可在评审时对本分支执行 `git log -1 --format=%H` 核对>
Docs Head: 同 Code Review Candidate（本 Phase 无独立代码，文档即变更全部内容）
```

## Scope

只读勘察 `upstream/amane`（本地克隆，tag `v0.15.0`，commit `45dff2159369883e028a296d775a4598836c1ddd`）。**未修改 Amane 任何文件，未修改/新增任何业务代码**（`src/`、`tests/` 目录保持规格书要求的空占位状态）。变更内容仅为：

- `fc2-organizer/.gitignore`：排除 `upstream/amane/`，防止上游源码被误提交。
- `fc2-organizer/docs/PHASE0_AMANE_INTEGRATION_REPORT.md`：勘察报告正文。
- `fc2-organizer/docs/review/PHASE0_HANDOFF.md`：本文件。

## 变更文件

```text
fc2-organizer/.gitignore                              (new)
fc2-organizer/docs/PHASE0_AMANE_INTEGRATION_REPORT.md (new)
fc2-organizer/docs/review/PHASE0_HANDOFF.md            (new)
```

`fc2-organizer/upstream/amane/` 在工作区中存在（由 `scripts/bootstrap_amane.sh` 克隆得到，供本次勘察直接阅读源码），但已被 `.gitignore` 排除，**不在本次 commit 范围内，不会进入仓库历史**。

## 已处理的要求

对照《ClaudeCode_00_实施总提示词》Phase 0 的 0.1-0.5 五项勘察问题与退出条件，五项均已在 `PHASE0_AMANE_INTEGRATION_REPORT.md` 中逐项给出源码级证据（file:line + 引用代码片段），并额外记录了两项超出提问范围但直接影响后续 Phase 判断的背景发现（Amane 已内置 FC2 三站点爬虫与字段级聚合器，但官方文档记录其当前不稳定；`MediaMetadata` 与规格书草案模型的字段形状差异）。

**用户在本轮明确强调的两项硬指标——「正确且成功读取 FC2 片源信息」与「批量处理影片刮削」——已被本次勘察验证为在 Amane v0.15.0 上可达成且无需修改主程序：**
- 「批量刮削」：REFRESH 对扫描到的每个文件各自 fan-out 一个独立 SCRAPE 任务（`handlers/refresh.py:101-119`），单片失败由 `AsyncWorker._execute()` 的任务级 try/except 与聚合层 `invoke_source()` 的站点级 try/except 双重隔离，`POST /tasks/batch` 原生支持「只重试 FAILED」，并发由 `HotSettings.worker.concurrency`（默认 10，1-64 可调）有界控制——规格书要求的批量能力已是 Amane 现成基础设施，我们要做的是把新 FC2 源以插件形式接入这条既有批量管线，而不是另起一套批量引擎。
- 「正确读取 FC2 片源信息」：Amane 现有番号归一化对规格书列出的全部 5 种脏文件名形态（含 `[广告]` 前缀、`xxx@` 前缀）均能正确提取为 `FC2-NNNNNNN`；但 Amane 内置的 3 个 FC2 爬虫源当前状态不稳定（官方文档已记录 Cloudflare 拦截 / 跳转不稳定），这正是本项目要通过插件补充「新片源/多片源」的核心价值所在，也是 Phase 2 起必须先做真实可用性探针（`docs/SOURCE_VIABILITY_<source>.md`）而不能凭代码能写就假定可用的原因。

这两项判断已写入 `PHASE0_AMANE_INTEGRATION_REPORT.md` 的「非阻塞性观察」第 1 条，将作为 Phase 1（模型设计）与 Phase 2（新源可用性验证）的首要设计输入，但具体实现留待独立复查 PASS 后的 Phase 1 才开始编码。

## 已运行的测试

无。Phase 0 不产生业务代码，规格书 0.2 节的「五种脏文件名解析」结论中有 3 种（`FC2-PPV-1234567`、`FC2PPV1234567`、`FC2-1234567` 系列）由 Amane 现有单测 `tests/parsing/test_file_info.py`（155/156/230/240/379/445/455 行）覆盖并核对一致；其余 2 种（`[广告]…`、`xxx@…`）**没有 Amane 现成测试覆盖**，是通过直接执行 Amane 未改动的源码（`python3.13 -c "from amane.parsing import parse_file_info; ..."`）人工验证得到，不构成自动化回归，已在报告「非阻塞性观察」第 2 条中记为 Phase 1 待补事项。

## 确切命令

```bash
# 克隆只读参考副本（脚本自带，未改动）
bash fc2-organizer/scripts/bootstrap_amane.sh
# => Cloning into '.../fc2-organizer/upstream/amane'...
# => HEAD is now at 45dff21 release: 0.15.0
# => 45dff2159369883e028a296d775a4598836c1ddd

# 版本关系核对
git -C fc2-organizer/upstream/amane fetch origin main
git -C fc2-organizer/upstream/amane merge-base v0.15.0 origin/main
git -C fc2-organizer/upstream/amane rev-list --left-right --count v0.15.0...origin/main
git -C fc2-organizer/upstream/amane log --oneline v0.15.0..origin/main -- src/amane/plugin src/amane/plugins
git -C fc2-organizer/upstream/amane diff v0.15.0 origin/main -- src/amane/plugin src/amane/plugins | wc -l

# 番号解析行为验证（人工执行未改动源码，非新增测试）
python3.13 -c "from amane.parsing import parse_file_info; print(parse_file_info(text='FC2-PPV-1234567'))"
# ...对 5 种输入形态逐一执行
```

## 通过 / 失败计数

不适用——Phase 0 未运行自动化测试套件，也未新增测试。上述「Amane 现有单测覆盖」的行号引用是静态阅读确认，未在本次会话中实际执行 `pytest`（Amane 完整测试套件依赖 `uv sync` 等环境搭建，超出只读勘察范围，也不属于 Phase 0 要求）。**明确写出：Amane 测试套件 NOT run in this session**；番号解析验证仅通过直接 `python3.13 -c` 调用其未改动的解析函数完成，非 pytest。

## 已知局限

1. `[广告]FC2PPV-1234567` / `xxx@FC2PPV-1234567` 两种形态无 Amane 现成自动化测试覆盖，仅人工验证。
2. 未运行 Amane 完整测试套件（`just test`），本次勘察不依赖它，也未验证 Amane v0.15.0 本身在当前环境下能否完整跑通全部测试。
3. 未实际安装一个真实插件到运行中的 Amane 实例做端到端验证（如启动服务、上传 zip、触发一次 SCRAPE）——0.1 节结论完全基于源码 + 单测阅读，不是运行时验证；Phase 5/6 需要补这一环。
4. 未评估 Amane `latest release`（非 tag，`git tag` 列表未在本次勘察中枚举）与 `main` 是否为同一提交；已确认 `origin/main` HEAD 对应 `v0.16.1` 发布提交，未来若有更新的 tag 需要 Phase 8 重新核对。

## 已知的外部来源不稳定性

- `fc2ppvdb.com`：Amane 开发文档记录「可能被 Cloudflare Access denied」（`docs/dev/content-routes.md:54`）。
- `fc2club.top`：Amane 开发文档记录「打开后跳转镜像，不稳定」，因此被排除在默认路由外（`docs/dev/content-routes.md:56`）。
- 本次勘察**未对任何外部 FC2 站点发起真实网络请求**做可用性探测（不在 Phase 0 范围内，属于 Phase 2 的 `docs/SOURCE_VIABILITY_<source>.md` 任务）；以上结论均转引自 Amane 自身文档，不是本次实测。

## 安全考量

- 插件 zip 安装路径校验：`packaging.py::_extract_zip()` 拒绝绝对路径与 `..` 路径穿越；大小限制 20MB（zip）/ 50MB（解压后）。
- 插件配置密钥字段（含 `token`/`api_key`/`secret`/`password`/`cookie`/`credential`/`dsn` 关键词）由 `observability/redact.py` 按字段名启发式自动脱敏，不进日志/任务快照明文。
- 本次勘察未在任何文件中写入真实 cookie/token/API key；`upstream/amane/` 整体被 `.gitignore` 排除，不会连带上游仓库历史或其 `.env.dev` 等文件进入本仓库提交。

## Windows 运行

Windows NOT run（本次会话运行环境为 Linux 容器，Phase 0 不要求 Windows 验证；规格书的 Windows 相关约束——不得要求用户关闭 Defender——已知悉，留待后续 Phase 实际涉及安装脚本/打包时遵守）。

## Amane 集成运行

未运行 Amane 服务本身（未 `just dev` 启动 FastAPI/前端），本 Phase 结论完全基于静态源码阅读 + 已有单测阅读 + 版本控制历史比对，不含任何运行时集成验证。

## 复查者应重点关注的内容

1. 报告中列出的 file:line 引用是否与 `upstream/amane`（`v0.15.0`，`45dff21`）源码一致（复查者应自行克隆同一 tag 核对，不接受作者转述）。
2. GO 判断依据的四项退出条件证据是否充分——尤其"无需修改 Amane 核心"这一条，是否存在报告未发现的隐藏耦合点。
3. 「非阻塞性观察」第 1 条（Amane 已有内置 FC2 聚合能力但站点不稳定）是否应该升级为需要用户/产品决策的架构选择点，而不是留给 Phase 1 实施者自行判断。
4. `[广告]`/`xxx@` 两种脏文件名形态的验证方式（人工执行未改动源码而非既有单测）是否足以支撑 GO，还是应视为需要在 Phase 1 之前先补测试的前置条件。

## 范围之外

- Amane 完整测试套件的运行结果。
- 任何真实外部 FC2 网站的可用性探测（属于 Phase 2）。
- Amane 主程序功能的通用审计（仅审插件 API / 番号解析 / 批量任务 / 资源整理 / 版本兼容五个指定切面）。
- Windows 平台验证。

## 下一阶段尚未开始

Phase 1（冻结公共数据契约：`NormalizedMetadata` / `SourceResult` / 番号标准化模块）**尚未开始编码**，`fc2-organizer/src/` 与 `fc2-organizer/tests/` 保持规格书要求的空占位状态。在独立复查给出 PASS 之前不会进入 Phase 1。

---

```text
READY FOR INDEPENDENT REVIEW
```
