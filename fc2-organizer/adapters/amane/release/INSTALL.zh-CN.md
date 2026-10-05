# FC2 Metadata（ffcc）Amane 来源插件 —— 安装说明

> **桌面版请使用 sidecar 目录提供 Core，不要使用 pip。** 本发布包同时包含插件 zip 与独立的 Core wheel；
> Core 必须以**发布包里的那一个 wheel 文件**的形式放入 Amane 数据目录，插件才会加载它。

## 1. 支持范围（坐标级声明）

version compatibility target = Amane v0.15.0 与 v0.18.0；**support claim is coordinate-scoped, not version-global**。
本发布包只在下列坐标上经验证兼容（`(Amane 版本, 宿主形态, 平台)`）：

| 坐标 | Amane 版本 | 宿主形态 | 平台 |
|---|---|---|---|
| SC-01 | v0.15.0 | 官方 Windows x64 冻结桌面版 | Windows x64 |
| SC-02 | v0.18.0 | 官方 Windows x64 冻结桌面版 | Windows x64 |
| SC-03 | v0.15.0 | 源码宿主（Python 3.14.x） | Windows x64 |
| SC-04 | v0.18.0 | 源码宿主（Python 3.14.x） | Windows x64 |

macOS、Linux、Docker：**UNVERIFIED**（没有对应的验证环境），不属于本发布包的兼容声明。
若你仍在这些环境中尝试，下文的 Docker 说明仅为 **UNVERIFIED / informational — 不在本发布验收覆盖范围内**。

## 2. 发布包内容

| 文件 | 作用 |
|---|---|
| `ffcc.fc2-metadata-0.1.0.zip` | Amane 插件（上传到「管理 → 插件」） |
| `fc2_metadata_core-0.1.0-py3-none-any.whl` | Core（独立 wheel；**放入数据目录**，不要解压、不要用 pip 安装） |
| `SHA256SUMS` | 文件校验清单（可选：用 `sha256sum -c SHA256SUMS` 核对） |
| `COMPATIBILITY.json` | 机器可读的兼容清单 |
| `VERSION` | 发布包版本 |
| `INSTALL.zh-CN.md` | 本文 |

## 3. 安装（从零开始）

1. 打开 Amane 的数据目录（桌面版：托盘菜单「打开数据目录」）。
2. 在其下创建文件夹 `plugins/_ffcc_core/`（若 `plugins/` 不存在则一并创建），把 `fc2_metadata_core-0.1.0-py3-none-any.whl`
   **原样复制**进去。（核对 `SHA256SUMS` 是可选建议；插件加载时会强制校验。）
3. 在 Amane「管理 → 插件」上传 `ffcc.fc2-metadata-0.1.0.zip`。成功后插件会出现在列表中，**无需重启**。
   **运行期间不要替换或删除 sidecar wheel。**
4. 在「设置 → 影片刮削 → 内容路由」中，把 `ffcc.fc2-metadata` 加入 FC2 内容类型的来源列表。
5. 在「管理 → 插件」中按需修改配置（见第 6 节）。

顺序很重要：**先放 Core，再装插件**。否则第 3 步会以可读的错误（HTTP 422）失败，不会留下半装状态。

Docker（**UNVERIFIED / informational — 不在本发布验收覆盖范围内**）：`/data` 卷中的目录结构相同，步骤 2 的目录对应 `/data/plugins/_ffcc_core/`。

## 4. 不要这样做

* **不要**用 `pip install`、解压、editable、源码目录或 `PYTHONPATH` 提供 Core：这些形态一律不被接受，插件会拒绝加载（即使其中的字节完全正确）。
  源码方式运行的 Amane 同样使用 sidecar wheel；`pip` 只可用于准备 Amane 自己的依赖环境。
* **不要**在 Amane 运行期间替换或删除 `plugins/_ffcc_core/` 里的 wheel（见第 7 节）。
* **不要**把 `fc2_metadata_core` 的文件复制进插件目录或插件 zip。

## 5. 升级

| 变更 | 做法 | 是否需要重启 |
|---|---|---|
| 只升级插件（配对的 Core 不变） | 在「管理 → 插件」覆盖上传新的 zip | 否 |
| 升级 Core（配对记录变化） | **卸载旧插件 → 重启 Amane → 把新 wheel 放入 `plugins/_ffcc_core/` → 上传新的插件 zip** | 是 |

Core 升级必须严格按 `uninstall → restart → replace artifact → install` 顺序；插件不会在运行中热切换 Core。
旧 wheel 可以保留或删除，插件只认与自己配对的那个文件名。

## 6. 配置

在「管理 → 插件」中，`config` 对象支持：

| 字段 | 缺省 | 含义 |
|---|---|---|
| `sources` | 未设置 | 未设置 = 使用内置的来源集合与顺序；列表 = 权威列表（顺序即字段优先级）。每项：`id`（必须是已注册来源）、`enabled`（缺省 `true`）、`base_url`（可选镜像，必须是安全的绝对 http(s) 基址，不得含凭据 / query / fragment） |
| `source_deadline_seconds` | `20` | 每个来源的总耗时预算（秒），范围 `(0, 600]` |

注意：Amane 对 `config` 做**顶层浅合并**，无法通过省略某个键来恢复默认值；需要恢复默认时请显式写回默认值。
重试次数与网络行为由 Amane 自身的网络设置决定。

## 7. 完整性与已知限制（如实说明）

* 插件在加载时会校验 `plugins/_ffcc_core/` 中的 wheel：文件名、普通文件类型、大小上限和整个文件的 SHA-256 都必须与插件内置的配对记录一致。
  这是**准入时刻**的完整性与版本配对校验，**不是**运行期间的不可变保证，也不证明发布渠道本身。
  因此**运行期间不要替换或删除 sidecar wheel**。
* 已加载的 Core 只能证明「当前来源与当前文件字节」符合配对记录，不能证明此前已执行过的全部字节。
* 若忘记放置 Core，Amane 会显示 P5-C1 冻结的提示：`FC2 Metadata Core 未安装或版本不兼容：请在 Amane 所在的 Python 环境中安装 fc2-metadata-core（缺失模块：fc2_metadata_core）`。
  对桌面版请改为按第 3 节把 wheel 放入 sidecar 目录（**不要 pip**）。
* 只支持「上传 zip」的安装方式；用「选择服务器路径」安装到数据目录之外的插件目录时，插件无法定位 sidecar。
* 真实站点联网冒烟与批量任务不在本发布验收范围内。

## 8. 卸载

在「管理 → 插件」卸载 `ffcc.fc2-metadata`。`plugins/_ffcc_core/` 不会被卸载动作触碰；不再使用时可手动删除（请在 Amane 已停止运行后删除）。
