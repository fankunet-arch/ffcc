# FC2 Metadata（ffcc）Amane 来源插件 —— 安装骨架说明

> **状态：P5-C1 实现候选（等待独立 Level 1 Review）。** 本文档只描述 **P5-C1 的安装骨架**。
> **最终分发包、Core 的最终供给方式、安装 / 重载 / 配置往返验收、当前发布线兼容矩阵均属 P5-C2，本包不声称完成。**

## 它是什么

一个 Amane 来源插件（`id = ffcc.fc2-metadata`，能力 `film_metadata`，内容类型 `fc2`）。它是一层很薄的 adapter：

```text
Amane host（Python >= 3.14，v0.15.0）
   -> SearchQuery -> 本插件 -> canonical FC2 号 -> fc2_metadata_core（不修改）-> AggregationResult
   -> MediaMetadata | None | SourceError -> Amane host
```

规范合同：`docs/specifications/PHASE5_C1_AMANE_ADAPTER_CONTRACT.md`；施工计划：`docs/P5_C1_CONSTRUCTION_PLAN.md`。

## 目录

```text
adapters/amane/
  api_manifest/amane_v0.15.0_api_manifest.json   从 exact v0.15.0（45dff21…）源码 AST 生成的公共 API 清单
  fc2_amane_adapter/                              插件树（没有 __init__.py；plugin.py 在树根）
    plugin.py        宿主侧入口（唯一 import amane.plugin / pydantic 的模块）
    _core_gate.py    Core 缺失 / 不兼容时的固定 ImportError 翻译
    _settings.py     配置校验（不回显配置值）与 Core 配置构造
    _number.py       SearchQuery -> canonical（规范化完全委托 Core）
    _bridge.py       Amane web client -> Core SourceHttpClient 传输桥
    _runtime.py      一次构造、多次复用的 Core 调用封装
    _outcome.py      AggregationResult -> 中立结果（状态 / 错误 / 字段映射与窄化）
```

## 前置条件（P5-C1 冻结的最小要求）

1. 宿主：Amane **v0.15.0**，Python **>= 3.14**。
2. **`fc2_metadata_core` 必须能在 Amane 所在的同一个 Python 解释器中被 import**（安装到该环境，或位于其 `sys.path` 上）。
   - 缺失 / 版本不兼容时，插件导入失败，Amane 在 `discover()` 的 `failures` 中记录固定消息，**不会部分注册**，也**不会**回退到 Amane 内置的 FC2 爬虫：

     ```text
     FC2 Metadata Core 未安装或版本不兼容：请在 Amane 所在的 Python 环境中安装 fc2-metadata-core（缺失模块：<模块名>）
     ```

   - 注意：Amane 的开发文档写明插件“不能声明自己的 pip 依赖”。把 Core 预装到宿主解释器超出了宿主文档承诺的支持范围
     （合同 L-08）；Core 的最终供给方式由 **P5-C2** 决定，本包**不**复制 / vendor / 打包 Core 源码。

## 构建确定性的插件 zip（骨架）

```powershell
python tools\build_amane_plugin_zip.py --tree adapters\amane\fc2_amane_adapter --out <输出.zip>
```

zip 的唯一顶层文件夹是 `ffcc.fc2-metadata/`，其下是插件树的全部 `*.py`；条目排序、固定时间戳 / 权限、LF 换行，
相同输入得到字节相同的产物。**这不是最终可分发包。** 也可以手动把插件树复制到
`{data_dir}/plugins/sources/ffcc.fc2-metadata/`（目录名必须等于插件 id）。

## 配置（Amane 插件配置的 `config` 对象）

| 字段 | 缺省 | 含义 |
|---|---|---|
| `sources` | `null` | `null` = Core 默认来源集合与顺序；列表 = 权威列表（顺序即字段优先级）。每项：`id`（必须是已注册来源）、`enabled`（缺省 `true`）、`base_url`（可选镜像，必须是安全的绝对 http(s) 基址，不得含凭据 / query / fragment） |
| `source_deadline_seconds` | `20` | 每个来源的总墙钟预算（含宿主重试与退避），范围 `(0, 600]` |

重试 / 并发 / 熔断 / 字段优先级不暴露：传输重试归宿主（`network.max_retries`，宿主缺陷：v0.15.0 中 `0` 会使一次请求都不发），
Core 层重试被关闭。请求数口径见合同 §15.2：L1 = S，L2 ≤ S×H，L3 ≤ S×H×21。

## 证据

* 真实宿主见证：`docs/acceptance/evidence/P5_C1_HOST_WITNESS.json`（H-01..H-15）。重跑：

  ```powershell
  <py314> tools\run_amane_host_witness.py --amane-src <amane-checkout@v0.15.0> --core-src src --adapter-tree adapters\amane\fc2_amane_adapter --out <输出.json>
  ```

* HANDOFF：`docs/review/P5_C1_HANDOFF.md`。
