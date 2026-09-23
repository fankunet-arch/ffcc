# FC2 Organizer -- Phase 4 / P4-C5 图片获取合同（Image Acquisition Contract）

状态：**冻结候选，P4-C5 substeps 1-5 已完成**（基础层 + 二进制 transport + JPEG 校验 + 获取编排 + 合成门槛；独立复查 REQUIRED）。
Package：`fc2_organizer.images`（`__init__.py`、`errors.py`、`models.py`、`policy.py`、`urls.py`、`transport.py`、`jpeg.py`、`acquisition.py`）。
Frozen Base: `97f6aeba8d11d9bc8a29d5397b9a1e1711d36cd6`
Substep 1 Head: `a961dda486bc8377bd2cec8ae9dd107f5379eba4`
Substep 2 Head: `d7c1bd9173cb88be399368a4a7a9083f52f73e72`
Substep 3 Head: `4c780a88dd97613e97fe6a0f139deddcbfb40066`
Substep 4 Head: `9fff05ec1e8dbec3fce65dd9453fa41b8a4b786e`
Branch: `claude/phase4-c5-image-acquisition`

标注为 **IMPLEMENTED IN SUBSTEP 2** 的章节描述二进制 HTTP transport（第 12 节）；
**IMPLEMENTED IN SUBSTEP 3** 标注仅限 JPEG 的内容策略、结构校验和尺寸上限（第 13 节）；**IMPLEMENTED IN
SUBSTEP 4** 标注 `acquire_images` 编排（第 14 节）；
**IMPLEMENTED IN SUBSTEP 5** 标注合成图片门槛（第 15 节）。
没有 substep 标注的章节在 substep 1 中冻结。本合同中没有任何待定内容；明确的范围外清单见第 16 节。

## 1. 范围

P4-C5 整体：在内存中，根据一部影片 metadata 中的候选图片 URL，获取其 poster / fanart / thumb / extrafanart
图片，时间、重定向和内存都有上限，并以结构化、不含 secret 的形式报告每一个候选的失败。

**Substep 1 只交付：**

1. `fc2_organizer.images` package 骨架；
2. 不可变的值模型（第 3-6 节）；
3. 失败词汇（第 5 节）；
4. 不可变的获取策略（第 7 节）；
5. 纯函数的候选 URL 安全门（第 8 节）；
6. 错误层级（第 9 节）以及架构边界及其合同测试（第 10 节）。

**Substep 2 只交付**（第 12 节，IMPLEMENTED IN SUBSTEP 2）：二进制 HTTP transport -- `ImageHttpClient`
protocol、生产用的 `HttpxImageClient`、`ImageHttpResponse`、带逐跳 URL 重新校验的手动重定向处理、
流式读取时对单个响应的 `max_bytes` 上限、单次请求的总 deadline、transport 错误映射以及 client 生命周期。

**Substep 3 只交付**（第 13 节，IMPLEMENTED IN SUBSTEP 3）：仅限 JPEG 的规则、Content-Type 策略、
有界的 JPEG 结构校验、从 SOF header 提取尺寸、尺寸上限、严格 bytes / 严格 str 边界和恶意输入语义，
以及纯函数 helper `validate_acquired_image`。

**Substep 4 只交付**（第 14 节，IMPLEMENTED IN SUBSTEP 4）：
`acquire_images` -- 角色映射、候选排序与回退、失败映射、候选数量上限、extrafanart 上限、结果总量上限、
artifact 构造、失败排序、取消语义以及敏感数据排除。

**Substep 5 只交付**（第 15 节，IMPLEMENTED IN SUBSTEP 5）：400-record 合成图片门槛、全 package 回归以及
这份冻结合同；复查 handoff 是 `docs/review/P4_C5_HANDOFF.md`（纯文档提交）。
substep 5 没有新增任何功能。

完全不属于 P4-C5 的范围（第 16 节）：文件系统写入 / 落盘、覆盖 / 冲突、缩放 / 裁剪 / 转码、修改 NFO、
CLI / UI、持久化、Amane。

## 2. 角色

```python
class ImageRole(Enum):
    POSTER = "poster"
    FANART = "fanart"
    THUMB = "thumb"
    EXTRAFANART = "extrafanart"
```

恰好是冻结的 v1.0 整理布局中的四个图片角色
（`poster.jpg` / `fanart.jpg` / `thumb.jpg` / `extrafanart/`，
PHASE4_ORGANIZE_PLAN_CONTRACT）。从角色到 metadata URL 列表
（`poster_urls` / `fanart_urls` / `thumb_urls` / `extrafanart`）的映射
**IMPLEMENTED IN SUBSTEP 4**（第 14.2 节）。把角色映射到计划路径 / 文件不属于 P4-C5（这里不做任何文件系统工作）。

## 3. 模型规则（适用于所有模型）

* `@dataclass(frozen=True, slots=True)`；没有 `__dict__`。
* 每个字段都在 `__post_init__` 中用**严格**类型检查（`type(x) is T`）校验：`bool` 永远不能当作 `int`
  通过；`bytes` / `str` / `tuple` / 模型的子类永远不能当作基类型通过。
* 违规时抛出 `ImageModelError`。消息只包含字段名、Python 类型名和固定措辞。
* 没有任何模型带有 `url`、`headers`、`cookies`、`body`、`exception`、
  `traceback` 或自由文本 `error_detail` 字段。

## 4. `AcquiredImage`

| 字段 | 规则 |
|---|---|
| `role` | 严格 `ImageRole` |
| `candidate_index` | 严格 `int`，`>= 0`（在该角色候选列表中的位置） |
| `content` | 严格 `bytes`；不出现在 `repr` 中 |
| `width`、`height` | 严格 `int`，`> 0`（在 substep 1 中只是携带，**并不测量**） |
| `size_bytes` | 严格 `int`，`== len(content)` |
| `sha256` | 严格 `str`，64 个小写十六进制字符，**等于** `hashlib.sha256(content).hexdigest()` |

模型只检查形态。JPEG 校验器和尺寸上限已经存在（第 13 节，IMPLEMENTED IN SUBSTEP 3）；
每个 `AcquiredImage` 都由 `validate_acquired_image` 的结果构建（因此 `width` / `height` 总是来自 SOF header），
这由 `acquire_images` 完成 -- **IMPLEMENTED IN SUBSTEP 4**（14.6）。

## 5. 失败词汇：`ImageFailureKind` 与 `ImageCandidateFailure`

```text
INVALID_URL  UNSAFE_URL  CANDIDATE_LIMIT
TIMEOUT  CONNECTION_ERROR  REDIRECT_LIMIT  TRANSPORT_ERROR
HTTP_STATUS  TOO_LARGE  TOTAL_BYTES_LIMIT
CONTENT_TYPE_MISMATCH  INVALID_JPEG  INVALID_DIMENSIONS
```

这些词已冻结。自 substep 4 起，每一种 kind 都由 `acquire_images` 产生（映射：第 14.5 节）。

`ImageCandidateFailure(role, candidate_index, kind, http_status=None)`：

| 字段 | 规则 |
|---|---|
| `role` | 严格 `ImageRole` |
| `candidate_index` | 严格 `int`，`>= 0` |
| `kind` | 严格 `ImageFailureKind` |
| `http_status` | 严格 `int`，范围 `100..599`，**当且仅当** `kind is HTTP_STATUS`；否则为 `None` |

除此之外不保存任何内容：没有 URL、query、header、cookie、`Authorization`、响应体、异常或 traceback。

## 6. `ImageAcquisitionResult`

| 字段 | 规则 |
|---|---|
| `poster` | `None` 或 `role is POSTER` 的严格 `AcquiredImage` |
| `fanart` | `None` 或 `role is FANART` 的严格 `AcquiredImage` |
| `thumb` | `None` 或 `role is THUMB` 的严格 `AcquiredImage` |
| `extrafanart` | 由严格 `AcquiredImage` 组成的严格 `tuple`，每个都是 `role is EXTRAFANART` |
| `failures` | 由严格 `ImageCandidateFailure` 组成的严格 `tuple` |

全部为空（`ImageAcquisitionResult()`）是合法的。`total_bytes` 是一个纯属性：所有已获取图片的 `size_bytes`
之和。保证它不超过 `max_total_bytes`，以及 `len(extrafanart) <= max_extrafanart`，
由 `acquire_images` 强制执行 -- **IMPLEMENTED IN SUBSTEP 4**（14.7、14.9）。
模型本身并不知道策略。

## 7. `ImageAcquisitionPolicy`

| 字段 | 默认值 | 规则 |
|---|---|---|
| `request_deadline_seconds` | `15.0` | 严格 `int` 或 `float`（不能是 `bool`），有限，`> 0` |
| `max_redirects` | `5` | 严格 `int`（不能是 `bool`），`> 0` |
| `max_image_bytes` | `16 * 1024 * 1024` | 严格 `int`，`> 0` |
| `max_total_bytes` | `64 * 1024 * 1024` | 严格 `int`，`> 0` |
| `max_candidates_per_role` | `16` | 严格 `int`，`> 0` |
| `max_extrafanart` | `12` | 严格 `int`，`> 0` |

跨字段规则：`max_image_bytes <= max_total_bytes`。违规时抛出
`ImagePolicyError`。`frozen=True, slots=True`。

运行时强制执行：`request_deadline_seconds`、`max_redirects` 和
`max_image_bytes` 由 transport 强制执行（第 12 节，IMPLEMENTED IN SUBSTEP 2）；
`max_total_bytes`、`max_candidates_per_role` 和 `max_extrafanart` 由
`acquire_images` 强制执行（第 14 节，IMPLEMENTED IN SUBSTEP 4）。

## 8. URL 安全门：`validate_image_url(url) -> str`

纯函数；不访问 DNS、socket、文件系统、时钟或环境。

### 8.1 严格类型边界

第一个操作是 `type(url) is str`。其他任何值 -- 包括任何 `str` 子类 -- 都会在该值的任何方法
（`strip`、`encode`、`__eq__`、`__hash__`、`__repr__`、`__format__`、
`__iter__`、`__len__`、`__bool__`、...）能够运行**之前**抛出 `ImageUrlError(NOT_EXACT_STR)`。由一个恶意子类测试
强制执行，该子类的每个钩子都会记录并抛出异常；记录到的钩子调用次数必须为 0。

### 8.2 输出：安全判断不等于规范化（冻结）

* 安全的 URL 以**同一个 `str` 对象**返回（`result is url`）。
* 校验器从不对 URL 或其 query 做 strip、大小写折叠、重新加引号、重新编码、去除 userinfo、重排或其他任何改写。
* 从不返回或保留任何 `urllib` 的 `SplitResult` / `ParseResult`。
* 需要改写才能变得安全的 URL 会被拒绝，而不是被修复。

### 8.3 规则（按此顺序检查）

| # | 规则 | reason | kind |
|---|---|---|---|
| 1 | 严格 `str` | `NOT_EXACT_STR` | `INVALID_URL` |
| 2 | 非空 | `EMPTY` | `INVALID_URL` |
| 3 | `len <= 4096`（`MAX_IMAGE_URL_LENGTH`） | `TOO_LONG` | `INVALID_URL` |
| 4 | 任何位置都不含 Unicode 空白、C0 控制字符或 DEL（因此 `urlsplit` 的静默剥除永远不会生效） | `WHITESPACE_OR_CONTROL` | `INVALID_URL` |
| 5 | 任何位置都不含 `\`（WHATWG 把它当作 `/`，`urlsplit` 则不会） | `BACKSLASH` | `UNSAFE_URL` |
| 6 | `urlsplit` 成功 | `MALFORMED` | `INVALID_URL` |
| 7 | 有 scheme（否则为相对 URL，包括 `//host/x`） | `RELATIVE` | `INVALID_URL` |
| 8 | scheme 为 `http` 或 `https`（不区分大小写）；拒绝 `file:` `data:` `ftp:` `javascript:` 等 | `UNSUPPORTED_SCHEME` | `UNSAFE_URL` |
| 9 | authority 非空 | `MISSING_HOST` | `INVALID_URL` |
| 10 | 没有 userinfo（authority 中出现 `@`） | `USERINFO` | `UNSAFE_URL` |
| 11 | 没有端口，或端口在 `1..65535` 内 | `INVALID_PORT` | `INVALID_URL` |
| 12 | hostname 非空 | `MISSING_HOST` | `INVALID_URL` |
| 13 | 方括号 host：合法的 IPv6，没有 zone id，全局地址（8.4） | `INVALID_HOST` / `NON_GLOBAL_IP` | `INVALID_URL` / `UNSAFE_URL` |
| 14 | reg-name host：ASCII `[a-z0-9_-]` 的 label，没有空 label，可选的单个结尾点；不含 `%`，不含非 ASCII 字符（IDNA / NFKC 可能把例如全角数字映射成 IP） | `INVALID_HOST` | `INVALID_URL` |
| 15 | host（忽略结尾点）不是 `localhost`，也不以 `.localhost` 结尾 | `LOCALHOST` | `UNSAFE_URL` |
| 16 | 如果最后一个 label 是数字（`[0-9]+` 或 `0x[0-9a-f]*`），host 必须是严格的点分四段 IPv4（拒绝 `2130706433`、`0x7f.1`、`127.1`、`0177.0.0.1`） | `NUMERIC_HOST` | `UNSAFE_URL` |
| 17 | IPv4 字面量是全局地址（8.4） | `NON_GLOBAL_IP` | `UNSAFE_URL` |

### 8.4 全局地址规则

使用标准库 `ipaddress`，只有当 IP 字面量满足 `is_global`，**并且**不是私有、回环、链路本地、组播、保留或
未指定地址时才接受（组播会被显式检查：在 Python 3.12 上组播地址的 `is_global` 为 `True`），也不能是 IPv6
站点本地地址，并且其中嵌入的每个 IPv4 地址（IPv4-mapped、6to4、Teredo）本身也必须是全局地址。被拒绝的示例：
`127.0.0.1`、`::1`、`10.0.0.1`、
`192.168.1.1`、`169.254.169.254`、`224.0.0.1`、`240.0.0.1`、`0.0.0.0`、
`100.64.0.1`、`::ffff:127.0.0.1`、`64:ff9b::7f00:1`。诸如
`8.8.8.8` 和 `2606:4700:4700::1111` 这样的公网字面量会被接受。

### 8.5 明确不作的声明（冻结）

* **不做 DNS 解析。** 一个看起来是公网、却解析到私有或回环地址的 hostname，**不会**被这道门拦住。
* **这道门不解决 DNS rebinding。** substep-2 的 transport 也没有增加连接时（已解析地址）的检查；见第 12.11 节。
  到目前为止，DNS rebinding 以及“公网名称解析到私有地址”在 P4-C5 中仍然**明确未处理**。
* 重定向目标在每一次后续跳转之前，都会由 transport 用这个相同的函数重新校验 -- **IMPLEMENTED IN SUBSTEP 2**
  （第 12.4 节）。

### 8.6 错误形态

`ImageUrlError(reason)` 只携带 `.reason: UrlRejectionReason` 和
`.failure_kind`（派生）。消息：`image URL rejected: <reason.value>`。URL（整体或任何部分：host、path、query、
token、userinfo）永远不会保存在异常上，也不会出现在消息中，并且该错误永远不做异常链接
（`__cause__ is None`；任何 context 都被抑制）。

## 9. 错误

```text
ImageError(Exception)
 +-- ImageInputError(ImageError, TypeError)   illegal argument (e.g. HttpxImageClient.get(max_bytes=True))
 +-- ImagePolicyError(ImageError, ValueError)
 +-- ImageModelError(ImageError, ValueError)
 +-- ImageUrlError(ImageError, ValueError)    .reason, .failure_kind
 +-- ImageTransportError(ImageError)          substep 2; failure_kind TRANSPORT_ERROR
      +-- ImageTimeoutError                   TIMEOUT
      +-- ImageConnectionError                CONNECTION_ERROR
      +-- ImageRedirectLimitError             REDIRECT_LIMIT
      +-- ImageRedirectError                  .reason (None | UrlRejectionReason);
      |                                       TRANSPORT_ERROR if None, else INVALID_URL / UNSAFE_URL
      +-- ImageResponseTooLargeError          TOO_LARGE
      +-- ImageClientClosedError              TRANSPORT_ERROR
 +-- ImageContentTypeError(ImageError, ValueError)   substep 3; CONTENT_TYPE_MISMATCH
 +-- ImageJpegError(ImageError, ValueError)          INVALID_JPEG, .reason: JpegRejectionReason
 +-- ImageDimensionError(ImageError, ValueError)     INVALID_DIMENSIONS, .reason: DimensionRejectionReason
```

transport 错误**不接受任何构造参数**（`ImageRedirectError` 可选的 reason 枚举除外）：每条消息都是固定字符串，
因此无法传入任何 URL、header、响应体、库消息或异常 `repr`。`ImageUrlError.failure_kind` 的语义与 substep 1
相同（只是把映射移到了一个共享 helper 中，以便 `ImageRedirectError` 复用）。

本 package 从不抛出裸 `ValueError`。

## 10. 架构边界

```text
fc2_organizer.images    foundation: __init__, errors, models, policy, urls, jpeg (substep 3)
    '-- standard library only:
        __future__, dataclasses, enum, hashlib, math, re, ipaddress, urllib.parse
    '-- jpeg.py specifically: __future__, dataclasses, enum, fc2_organizer.images.errors
        (never transport.py, httpx, an image library, struct, or any I/O module)

fc2_organizer.images.transport    (substep 2 -- the single httpx exception)
    '-- httpx
    '-- fc2_organizer.images.errors, fc2_organizer.images.urls
    '-- __future__, asyncio, dataclasses, math, re, types, typing, urllib.parse
```

* 基础层模块：不 import `fc2_metadata_core`（任何模块，包括 `sources`、聚合、批处理、资源控制）、`amane`、
  `httpx`、`requests`、`socket`、`ssl`、
  `http`、`urllib.request`、`asyncio`、`os`、`pathlib`、`io`、`shutil`、`time`、
  `random`，也不 import 任何其他 `fc2_organizer` package。`errors.py` 只 import
  `__future__` 和 `enum`。
* 没有反向依赖：`fc2_metadata_core`、`discovery`、`planning`、
  `publication` 和 `nfo` 从不 import `images`。
* `transport.py` 是**唯一** import `httpx` 的 images 模块。它从不 import `fc2_metadata_core`
  （它不复用面向文本的 `SourceHttpClient` / `HttpResponse.text`）、`amane`、任何文件系统模块或任何其他
  `fc2_organizer` package，也不做任何文件系统调用。
* `fc2_organizer/images/__init__.py` **不** import `transport`；裸
  `import fc2_organizer.images` 永远不会加载 `httpx`。请显式 import transport：
  `from fc2_organizer.images.transport import HttpxImageClient`。
* `fc2_organizer/__init__.py` 没有改动，也**不会**急切地 import
  `images`；请显式 import：`from fc2_organizer.images import ...`。
* `fc2_organizer` 的顶层子 package 现在恰好是
  `{"discovery", "planning", "publication", "nfo", "images"}`。现有的四个作用域守卫断言
  （P4-C1..P4-C4 的架构测试）各更新了一行（只是 package 集合的增长）；它们的禁止 import 守卫、运行时阻断器、
  允许列表和反向依赖守卫都没有改动。
由 `tests/contract/test_images_architecture.py` 强制执行（模块集合恰好是五个基础层模块加上 `transport.py`；
只有 `transport.py` import `httpx`；transport 的允许列表；没有文件系统调用；没有 `.aread` / `.text` /
`decode` / 非 `self` 的 `.content`；`AsyncClient` 只在 `__init__` 中创建一次，带
`follow_redirects=False` 和 `trust_env=False`，没有 auth / cookies / headers /
proxies；基础层 import 允许列表；禁止调用；反向依赖；在 meta-path 层阻断 `amane` / `httpx` / `requests` / `socket` /
`ssl` / `fc2_metadata_core` / `urllib.request` / `http.client` 的情况下做运行时 import；公开 API 中不含任何
延后才提供的入口）。

## 11. 实现状态

| 领域 | 状态 |
|---|---|
| HTTP client 抽象 / httpx transport | IMPLEMENTED IN SUBSTEP 2 (12.1-12.2) |
| 重定向处理与逐跳 URL 重新校验 | IMPLEMENTED IN SUBSTEP 2 (12.4) |
| 流式响应体与单个响应的 `max_bytes` 上限 | IMPLEMENTED IN SUBSTEP 2 (12.5-12.6) |
| 单次请求的总 deadline | IMPLEMENTED IN SUBSTEP 2 (12.7) |
| Content-Type 提取（不含策略） | IMPLEMENTED IN SUBSTEP 2 (12.8) |
| transport 错误映射、取消、生命周期 | IMPLEMENTED IN SUBSTEP 2 (12.9-12.10) |
| 在获取结果中把 HTTP 状态映射为 `HTTP_STATUS` 失败 | IMPLEMENTED IN SUBSTEP 4 (14.5) |
| 仅限 JPEG 规则、Content-Type 接受 / 拒绝策略 | IMPLEMENTED IN SUBSTEP 3 (13.1-13.2) |
| JPEG 结构校验、尺寸提取、尺寸上限 | IMPLEMENTED IN SUBSTEP 3 (13.3-13.4) |
| 严格 bytes / 严格 str 边界、恶意输入语义 | IMPLEMENTED IN SUBSTEP 3 (13.6) |
| 结果总量 64 MiB 上限、候选数量与 extrafanart 的运行时强制执行 | IMPLEMENTED IN SUBSTEP 4 (14.7-14.9) |
| 连接时的已解析地址检查 / DNS rebinding | NOT ADDRESSED（见 8.5、12.11） |
| `acquire_images` API、角色映射、候选排序 / 回退、角色隔离 | IMPLEMENTED IN SUBSTEP 4 (14.1-14.4, 14.10) |
| 失败映射与排序、artifact 构造、取消、敏感数据排除 | IMPLEMENTED IN SUBSTEP 4 (14.5-14.6, 14.10-14.12) |
| 合成获取门槛、全 package 回归 | IMPLEMENTED IN SUBSTEP 5 (15) |
| 最终的 P4-C5 handoff | COMPLETED IN SUBSTEP 5 -- `docs/review/P4_C5_HANDOFF.md`（纯文档提交） |
| P4-C5 关闭 | NOT CLOSED -- 独立复查 REQUIRED |

## 12. 二进制 HTTP transport -- IMPLEMENTED IN SUBSTEP 2

模块：`fc2_organizer.images.transport`。测试：
`tests/unit/images/test_image_transport.py`（完全离线，第 12.12 节）。

### 12.1 `ImageHttpClient`（protocol）与 `ImageHttpResponse`

```python
class ImageHttpClient(Protocol):
    async def get(self, url: str, *, deadline_seconds: float, max_redirects: int,
                  max_bytes: int) -> ImageHttpResponse: ...
    async def aclose(self) -> None: ...

@dataclass(frozen=True, slots=True)
class ImageHttpResponse:
    status_code: int          # exact int, 100..599, never a redirect status
    content_type: str | None  # exact str media type or None (12.8)
    content: bytes            # exact bytes; b"" unless status_code == 200
```

`ImageHttpResponse` 的违规会抛出 `ImageModelError`（`bytearray`、
`memoryview`、`str`、`bytes` / `str` 子类、`bool` 类型的状态、带响应体的non-200）。响应体被快照为内置 `bytes`。
响应中**不**保存 URL、重定向历史、header mapping、cookie、`httpx.Request` / `httpx.Response` 或异常
（它的 `gc` referent 只有 `int` / `str` / `bytes` / `None`）。

`get` 的参数规则（否则在任何请求之前抛出 `ImageInputError`）：
`deadline_seconds` 为严格 `int` / `float`，有限，`> 0`；`max_redirects` 为严格
`int >= 0`；`max_bytes` 为严格 `int > 0`。没有 `headers`、`cookies`、
`auth` 或凭据参数。

### 12.2 `HttpxImageClient`

* 每个实例一个 `httpx.AsyncClient`，在 `__init__` 中创建（绝不按请求创建，也绝不在 import 时创建）。
  构造时不发送任何请求。
* `follow_redirects=False`、`trust_env=False`（不使用 `HTTP_PROXY` / `HTTPS_PROXY`
  / `ALL_PROXY` / `.netrc`），没有 auth，没有 client cookie，没有 client header。
* `transport=` 接受 `httpx.AsyncBaseTransport`（测试注入
  `httpx.MockTransport`）；其他任何值 -> `ImageInputError`。
* 每一跳的 `httpx.Request` 都直接构建，只带固定 header：
  `Accept: image/jpeg, image/*;q=0.8`、`Accept-Encoding: identity`、
  `User-Agent: fc2-organizer-image-fetch/0.1 (...)`（外加 httpx 的 `Host`）。
  服务器下发的 cookie 在每一跳之后都会从 client 的 cookie jar 中清除，永远不会被发送。
* 解析差异守卫：构建出的请求的 scheme 和 host 必须等于校验器判断时 `urlsplit` 得到的 scheme / hostname；
  否则什么都不发送（`ImageTransportError`）。
* 每一跳只发送一次 -- **没有重试，没有退避，没有 `Retry-After`**。重定向不算重试。

### 12.3 初始 URL

`validate_image_url(url)`（substep 1 的函数本身，而不是副本）在构建任何请求之前运行。不安全 / 非法的初始 URL
会抛出 `ImageUrlError`，并且什么都不发送。

### 12.4 手动重定向

* 重定向状态码：`301 302 303 307 308`。每一跳都是 `GET`。
* httpx 0.27 的 `AsyncClient.send` 即使在 `follow_redirects=False` 时也会自己解析 `Location`（用来构建
  `next_request`）。为了让每个重定向目标都受*我们自己的*校验器约束，一个响应事件钩子会在 header 到达后立即运行，
  对于重定向状态码，它用一个只携带原始 `Location` 字符串的私有信号中止 `send`；httpx 会**不读取**地关闭该响应。
* 解析方式：`urllib.parse.urljoin(current_url, location)`（允许相对 `Location`），然后在发送下一跳**之前**执行
  `validate_image_url(target)`。经过校验的字符串就是下一次请求的确切目标。
* 缺失 / 空白的 `Location` -> `ImageRedirectError(reason=None)`
  （`TRANSPORT_ERROR`）。未通过校验的目标（localhost、`*.localhost`、私有 / 链路本地 / 回环 / 非规范数字 IP、
  `file:` / `data:` / `ftp:`、userinfo、空白、格式错误 ...）-> `ImageRedirectError(reason)`，其
  `failure_kind` 为 `INVALID_URL` / `UNSAFE_URL`，与 `ImageUrlError` 完全相同。**被拒绝的目标永远不会被请求**
  （测试断言了记录下来的请求列表）。
* 重定向的响应体永远不会被读取，也永远不会被当作图片。

**重定向上限（冻结）：** `max_redirects` 是允许*跟随*的重定向次数。当 `max_redirects = N` 时，N 次重定向的链
会成功（N+1 个请求）；当第 (N+1) 个重定向响应到达时，会抛出 `ImageRedirectLimitError`，**并且不会**请求它的目标
（因此最多发送 N+1 个请求）。`max_redirects = 0` 表示第一个重定向响应就失败。边界测试在两侧覆盖了
N = 0, 1, 5, 6。

### 12.5 状态处理

只有最终为 `200` 的响应才会进入响应体流式读取。其他每一种最终状态（`204`、
`206`、`304`、`403`、`404`、`429`、`500`、`503`、...）都**在不读取响应体的情况下**返回
`ImageHttpResponse(status_code, content_type, b"")`。把non-200 状态映射为 `HTTP_STATUS` 是获取层的工作
（第 14.5 节，IMPLEMENTED IN SUBSTEP 4）。`100..599` 之外的状态 -> `ImageTransportError`。

### 12.6 流式 `max_bytes` 上限与 `Content-Length`

* `Content-Encoding` 必须缺失或为 `identity`（请求本身要求的就是 `identity`）；其他任何值 -> 在读取之前
  抛出 `ImageTransportError`，因此永远不会发生解压（也就不会有解压炸弹），字节计数器等于内存中持有的字节数。
* 响应体逐块读取（identity 编码下的 `aiter_bytes`）到一个 `bytearray` 中；在追加一个块之前，
  若 `len(buffer) + len(chunk) > max_bytes` -> 立即抛出 `ImageResponseTooLargeError`；**不再拉取任何后续块**，
  并且在不排空的情况下关闭响应。恰好 `max_bytes` 会被接受；`max_bytes + 1` 会被拒绝。绝不先调用
  `aread()` / `.content`。
* `Content-Length` 提前拒绝：如果该 header 是格式正确的 ASCII 十进制数（去除首尾空白后为 `[0-9]+`），并且其值
  `> max_bytes`，则在读取任何响应体字节之前抛出 `TOO_LARGE`。非常长的数字串按长度比较，绝不传给 `int()`。
  格式错误 / 带符号 / 重复的值会被忽略。
  `Content-Length` 只是一个提示：流式计数器无论如何都会生效（谎报的小值仍然受上限约束；缺失值也没有问题）。

### 12.7 总 deadline

`deadline_seconds` 是一次 `get()` 的全部墙钟预算：第一跳、每一次重定向、header 以及响应体流式读取。
一个 `asyncio.timeout(deadline)` 包住整个请求 / 重定向 / 流式读取的生命周期；它**不会**在每一跳时重置。
每一跳的 httpx 超时扩展都被设为*剩余*预算，任何 httpx 超时（`ConnectTimeout`、`ReadTimeout`、`WriteTimeout`、
`PoolTimeout`）或内置 `TimeoutError` 都映射为同一个 `ImageTimeoutError`。

**无法表示的 deadline（R1，关闭 P4-C5-R-02）。** 可接受的输入域没有改变：策略和 `get()` 仍然接受任何严格的正
`int`（以及任何有限的正 `float`）。在构建任何请求之前，`get()` 会把 deadline 转换成事件循环时钟所需的 float。
这一判断依据异常类型（转换时的 `OverflowError`）做出，绝不依据消息。当一个 `int` 大到无法表示为 float 时
（例如 `10**400`、`10**309`、`2**1024`），不发送任何内容，`get()` 抛出一个新的、消息固定的 `ImageTransportError`
（`TRANSPORT_ERROR`），其 `__cause__` / `__context__` 为 `None`。不会有任何 `OverflowError`、
`ValueError` 或库异常泄漏出来。每一个可以表示的 deadline
（`15.0`、`1`、`10**308`、`1e300`、`sys.float_info.max`）的行为都与之前完全相同。

### 12.8 Content-Type 提取（不含策略）

`content_type` 是 `Content-Type` 中的媒体类型：第一个 `;` 之前的文本，去除首尾空白，保留大小写。当 header
缺失、为空、长于 127 个字符或含有可打印 ASCII 以外的任何字符时为 `None`。transport 中不做任何
`image/jpeg` / `image/png` / `application/octet-stream` 的判断；策略见第 13.2 节（IMPLEMENTED IN SUBSTEP 3），
由获取层应用（第 14.4 节，IMPLEMENTED IN SUBSTEP 4）。header mapping 永远不会被返回。

### 12.9 错误映射与取消

| 原因 | 抛出 |
|---|---|
| httpx `TimeoutException` 系列、内置 `TimeoutError`、deadline 到期 | `ImageTimeoutError` |
| httpx `NetworkError`（`ConnectError`，包括 DNS / TLS、`ReadError`、`WriteError`、`CloseError`）、`ProtocolError`（`RemoteProtocolError`、`LocalProtocolError`）、`ProxyError` | `ImageConnectionError` |
| 其他任何普通 `Exception`（例如 `UnsupportedProtocol`、`RuntimeError`） | `ImageTransportError` |
| `aclose()` 之后的失败 | `ImageClientClosedError` |

库异常在 worker coroutine 内部被转换为一个**新的**错误值，并且只从 `get()` 本身、在任何 `except` 块之外抛出，
因此 `__cause__` 和 `__context__` 为 `None`，从该错误出发无法触及任何 httpx 异常、请求、响应、header mapping
或重定向 URL。消息中从不包含 URL、query、响应体、库消息或异常 `repr`。

**取消（冻结）：** 调用方的 `asyncio.CancelledError` 原样传播（永远不会被映射）。`KeyboardInterrupt`、`SystemExit`、
`GeneratorExit` 以及其他所有非 `Exception` 的 `BaseException` 都原封不动地传播。只有普通的 `Exception` 会被映射。

### 12.9a 清理边界（R1，关闭 P4-C5-R-01）

关闭响应（`response.aclose()`）和关闭它的字节迭代器都是清理步骤。它们都通过同一个 helper（`_cleanup`）执行，
绝不通过裸的 `finally`：

| 情况 | 结果 |
|---|---|
| 清理时抛出 httpx `NetworkError`（包括 `CloseError`）/ `ProtocolError` / `ProxyError` | 新的 `ImageConnectionError` 值 |
| 清理时抛出 httpx `TimeoutException` / 内置 `TimeoutError` | 新的 `ImageTimeoutError` 值 |
| 清理时抛出其他任何普通 `Exception` | 新的 `ImageTransportError` 值 |
| 主结果已经是一个错误值（例如 `TOO_LARGE`、流式读取中途的读取 / 连接错误），并且清理失败 | 保留**主**错误；丢弃清理错误 |
| 主结果是一个 `ImageHttpResponse`（带响应体的 200，或任何non-200 状态），并且清理失败 | 清理错误值（fail closed） |
| 主路径正在传播 `asyncio.CancelledError`、`KeyboardInterrupt`、`SystemExit`、`GeneratorExit` 或任何其他非 `Exception` 的 `BaseException` | 执行清理；丢弃清理产生的普通错误；原样重新抛出**原始对象**（因此 deadline 到期仍然会变成 `ImageTimeoutError`） |
| 清理本身抛出取消 / 致命 `BaseException` | 原样传播：绝不吞掉，绝不映射 |

分类使用与第 12.9 节相同的基于类型的映射，从不查看消息。映射后的值在 worker 内部被创建，而不是被抛出。
它们只会通过 `get()` 在任何 `except` 块之外的唯一一次 raise 到达调用方。因此 `__cause__` / `__context__` 为 `None`，
从该错误出发无法触及任何原始异常、`httpx.Request`、`httpx.Response`、URL、query token、库消息或清理时的 traceback。

### 12.10 生命周期

`async with HttpxImageClient() as client:` 或 `await client.aclose()`
（幂等）。关闭之后，`get()` 和 `__aenter__` 会抛出
`ImageClientClosedError`，并且什么都不发送。

### 12.11 明确不作的声明

* 没有已解析地址（连接时）检查：DNS 应答为私有 / 回环地址的公网 hostname 仍然会被连接。DNS rebinding **没有**
  被处理。
* 没有重试 / 退避 / `Retry-After`，没有 HTTP/2，没有缓存。
* transport 本身不做任何 Content-Type 或 JPEG 判断（那是第 13 节，由获取层应用）；transport 中也没有角色 /
  候选编排，没有结果级的总字节上限（那些属于第 14 节）。

### 12.12 离线测试

所有 transport 测试都使用 `httpx.MockTransport` 加上一个会记录的
`httpx.AsyncByteStream` -- 没有 DNS、socket、监听器或公网。证明强度：记录流会统计实际被拉取的块数
（超过上限的响应体恰好在第一个越过上限的块处停止；non-200 / 重定向响应体拉取零个块），记录器会列出实际发送的
每一个请求（不安全的重定向目标从不出现）。开发期间做过变异检查：去掉重定向重新校验、在大小检查之前读取整个
响应体，或者每一跳都重新设定 deadline，都会让相应的测试失败。

## 13. 仅限 JPEG 的内容校验 -- IMPLEMENTED IN SUBSTEP 3

模块：`fc2_organizer.images.jpeg`（只使用标准库；由 `fc2_organizer.images` 导出）。测试：
`tests/unit/images/test_image_jpeg.py`。

### 13.1 仅限 JPEG 规则（冻结）

P4-C5 的输出格式**只有 JPEG**。PNG、WEBP、GIF、AVIF、HTML、JSON 或其他任何不具备 JPEG 结构的内容都会被拒绝
（`INVALID_JPEG`）。不做任何转码；没有新增或 import 任何图片库（Pillow 或其他）。

### 13.2 Content-Type 策略：`validate_image_content_type(content_type) -> ContentTypeVerdict`

`content_type` 必须是 `None` 或严格的 `str`（否则在该值的任何方法运行之前抛出 `ImageInputError`）。
媒体类型是第一个 `;` 之前的文本，去除首尾空白后不区分大小写地比较；参数被忽略。

| 声明的媒体类型 | 结果 |
|---|---|
| `image/jpeg`、`image/jpg`、`image/pjpeg` | `JPEG_DECLARED` |
| `None`、空、`application/octet-stream` | `UNDECLARED` -- 只由字节内容决定 |
| 其他任何值（`image/png`、`image/webp`、`image/gif`、`image/avif`、`text/html`、`application/json`、`text/plain`、`image/*`、`binary/octet-stream`、...） | `ImageContentTypeError` -> `CONTENT_TYPE_MISMATCH` |

显式声明的非 JPEG 媒体类型会被拒绝，**即使响应体是合法的 JPEG**。`JPEG_DECLARED` 和 `UNDECLARED` 都仍然需要
13.3 的字节校验；声明永远不能替代校验。错误消息是固定的（`image content type is not JPEG`），从不回显声明的值。

### 13.3 结构校验：`inspect_jpeg(content) -> JpegInfo`

`content` 必须是严格的 `bytes`（`bytearray`、`memoryview`、`str` 以及任何 `bytes` 子类 -> 在该值的任何钩子
运行之前抛出 `ImageInputError`）。
只做一次前向遍历，O(len(content))，每个下标在使用前都做边界检查：

1. 偏移 0 处为 `FF D8`（SOI），否则为 `NOT_JPEG`（PNG / WEBP / GIF / AVIF / HTML / JSON 就在这里失败）。
2. 在第一个 SOS 之前（含），精确解析 marker 和段：
   * marker 是 `0xFF`，可以作为填充字节重复出现（T.81 B.1.1.2），然后是一个代码；在应当开始 marker 的位置出现
     非 `FF` 字节 -> `INVALID_MARKER`。填充字节永远不会被当作段数据；
   * 独立 marker `TEM`（`01`）和 `RST0..7`（`D0..D7`）不带长度，会被跳过；
   * `FF 00`、重复的 SOI 以及保留代码 `02..BF` -> `INVALID_MARKER`；
   * 在任何 SOS 之前出现 EOI -> `MISSING_SOF` / `MISSING_SOS`；
   * 其他每个 marker 都有一个 2-byte 的大端长度：长度字段被截断 -> `TRUNCATED`，长度 `< 2` ->
     `INVALID_SEGMENT_LENGTH`，段越过末尾 -> `SEGMENT_OUT_OF_BOUNDS`。这类段（APPn、DQT、DHT、DAC、
     DRI、COM、JPG、JPGn、DNL、DHP、EXP ...）按其声明的长度跳过。
3. SOF：恰好是 13 个帧 marker `C0 C1 C2 C3 C5 C6 C7 C9 CA CB CD CE CF`。
   `C4`（DHT）、`C8`（JPG）和 `CC`（DAC）**永远**不是帧。帧 header：精度、高度、宽度、分量数 `Nf >= 1`，
   并且段长度必须恰好是 `8 + 3*Nf`。精度为 `8` 或 `12`（DCT）或 `2..16`
   （无损 `C3 C7 CB CF`）；否则为 `INVALID_SOF`。第二个 SOF -> `MULTIPLE_SOF`。
4. SOS：要求之前出现过 SOF（`MISSING_SOF`）；header 中 `Ns` 在 `1..4` 内，且长度恰好为 `6 + 2*Ns`（`INVALID_SOS`）。
5. SOS header 之后的熵编码数据**不做扫描**。载荷必须以 `FF D9`（EOI）结尾，且 EOI 位于 SOS header 之后；
   否则为 `MISSING_EOI`（这包括 EOI 之后还有尾随字节的情况）。在任何 SOS 之前就结束的数据 -> `TRUNCATED`。

没有真实段的裸 `FF D8 ... FF D9` 会被拒绝；这项检查绝不只是 `startswith(FFD8)` / `endswith(FFD9)`。

**承诺的范围（冻结）：** 有界的*结构*校验。通过校验**不**保证每一个 JPEG 解码器都能解码该图片（熵数据、
Huffman / 量化表的内容以及分量采样都没有校验）。不解码任何像素。

所有失败都是 `ImageJpegError(reason: JpegRejectionReason)`
（`INVALID_JPEG`）。任何 `IndexError`、`struct.error`、`UnicodeError`、
`OverflowError` 或其他内部异常都无法泄漏出来（测试覆盖了一个合法 fixture 的每一个前缀，以及一个确定性的
3000-case 变异 fuzz）。

### 13.4 尺寸与上限

宽度和高度来自 SOF 帧 header（不做解码）。它们在结构被接受**之后**才被判断。`JpegInfo(width, height, sof_marker)`
是 `frozen=True, slots=True`，并在构造时强制执行上限：

| 规则 | reason（`INVALID_DIMENSIONS`） |
|---|---|
| width / height 为严格 `int`（不能是 `bool`） | `NOT_EXACT_INT` |
| `width == 0` | `ZERO_WIDTH` |
| `height == 0`（不支持由 DNL 定义高度） | `ZERO_HEIGHT` |
| `width <= 20000` | `WIDTH_TOO_LARGE` |
| `height <= 20000` | `HEIGHT_TOO_LARGE` |
| `width * height <= 100_000_000` | `TOO_MANY_PIXELS` |

`20000 x 5000`（恰好 `1e8`）会被接受；`20000 x 5001` 不会。违规时抛出 `ImageDimensionError(reason)`，
绝不是裸 `ValueError`。`sof_marker` 必须是 13 个帧 marker 之一。

### 13.5 集成 helper：`validate_acquired_image(content, content_type) -> JpegInfo`

冻结的顺序：(0) 两个参数的严格类型，(1) Content-Type 策略，
(2) JPEG 结构，(3) 尺寸上限。纯函数：没有 HTTP、角色、候选迭代或 I/O。由第 14.4 节接入获取流程
（IMPLEMENTED IN SUBSTEP 4）。

### 13.6 恶意输入语义

`type(content) is bytes` 和 `content_type is None or type(content_type) is str`
是最先执行的操作。恶意的 `bytes` 子类（覆盖 `__bytes__`、
`__repr__`、`__str__`、`__getitem__`、`__len__`、`__iter__`、`__eq__`、
`__hash__`、`__buffer__`、`startswith`、`find`、`decode`、...）或 `str`
子类（`strip`、`lower`、`split`、`__eq__`、`__hash__`、...）会以 `ImageInputError` 被拒绝，
其钩子的运行次数为**零**（用会记录并抛出异常的钩子测试）。

### 13.7 错误与副作用

`ImageContentTypeError`（`CONTENT_TYPE_MISMATCH`）、`ImageJpegError`
（`INVALID_JPEG`、`.reason`）、`ImageDimensionError`（`INVALID_DIMENSIONS`、
`.reason`）都是 `ImageError` + `ValueError`。消息是固定文本加上 reason 值：从不包含载荷字节、声明的
Content-Type、URL 或内部异常文本；从不做异常链接。该模块不做任何文件系统、网络、时钟或随机数操作，
只 import `__future__`、`dataclasses`、`enum` 和 `fc2_organizer.images.errors`。

开发期间做过变异检查：把 `C4`/`C8`/`CC` 当作 SOF 接受、去掉 EOI 检查、去掉段长度下限、去掉边界检查、
去掉像素上限，或用 `isinstance` 代替严格类型检查，都会让 `test_image_jpeg.py` 失败。

## 14. 获取编排 -- IMPLEMENTED IN SUBSTEP 4

模块：`fc2_organizer.images.acquisition`（需要显式 import；不从 `fc2_organizer.images` 重新导出，
后者的 import 保持不涉及 `httpx` /
`fc2_metadata_core`）。测试：`tests/unit/images/test_image_acquisition.py`。

### 14.1 API

```python
async def acquire_images(
    record: PublicationRecord,
    client: ImageHttpClient,
    *,
    policy: ImageAcquisitionPolicy | None = None,
) -> ImageAcquisitionResult
```

* `type(record) is PublicationRecord`，否则抛出 `ImageInputError`。
* `policy=None` -> `ImageAcquisitionPolicy()`；否则它必须是严格的
  `ImageAcquisitionPolicy`（`ImageInputError`）。
* `client` 总是由外部注入（任何带有可调用 `get` 的对象，否则抛出 `ImageInputError`）；`acquire_images`
  从不构造 `HttpxImageClient` 或任何其他 client，也从不关闭被注入的 client。
* 输入错误在**任何请求之前**抛出。每一个针对单个候选的问题都会变成一个 `ImageCandidateFailure`；
  任何候选失败都不会抛出异常。

### 14.2 角色映射与候选形态

| 角色 | metadata 字段 | 胜出者 |
|---|---|---|
| `POSTER` | `metadata.poster_urls` | 第一个合法的 JPEG |
| `FANART` | `metadata.fanart_urls` | 第一个合法的 JPEG |
| `THUMB` | `metadata.thumb_urls` | 第一个合法的 JPEG |
| `EXTRAFANART` | `metadata.extrafanart` | 每一个合法的 JPEG，最多 `max_extrafanart` 个 |

没有跨角色回退：每个角色只读取自己的字段，一个角色中的成功永远不会被提升到另一个角色。

四个集合都在任何请求之前检查：每个都必须是严格的 `tuple`，每个条目都必须是严格的 `str`。`list` / `set` /
`frozenset` / 生成器 / 裸 `str` / `None` / `tuple` 子类，或非 `str` / `str` 子类的条目（只可能通过伪造的
metadata 出现），会抛出 `ImageInputError`，消息只写出字段名 -- 绝不写出值。`record.metadata` 的可信程度以
`PublicationRecord` 所保证的为限（`isinstance` `NormalizedMetadata`）；恶意的 metadata *子类*属于延续下来的
P4-C4-R-01 那一类 finding，这里不做处理。

### 14.3 候选排序（冻结）

角色按 `POSTER -> FANART -> THUMB -> EXTRAFANART` 的顺序处理；在一个角色内部，候选按 tuple 顺序处理。
严格串行：一次只有一个 `await client.get(...)`（没有 `gather`、任务组或后台任务），因此每次 `acquire_images`
调用最多只有一个请求在进行中。每个候选**最多只请求一次**（不对同一 URL 重试）；同一个 URL 列出两次就是两个候选。

### 14.4 单个候选的处理流程（冻结顺序）

1. `validate_image_url(url)` -- 未通过的 URL 永远不会被请求。
2. `client.get(url, deadline_seconds=policy.request_deadline_seconds,
   max_redirects=policy.max_redirects, max_bytes=policy.max_image_bytes)`。
3. 响应必须是严格的 `ImageHttpResponse`；`status_code == 200`。
4. Content-Type 策略（13.2）。5. JPEG 结构（13.3）。6. 尺寸（13.4）
   -- 第 4-6 步通过 `validate_acquired_image` 完成。
7. 结果总量上限（14.7）。
8. 构造 `AcquiredImage`（14.6）。

任何一步失败，都只为该候选记录恰好一个失败，然后转到同一角色的下一个候选。

### 14.5 失败映射（按异常类型 / 结构化 kind，绝不按消息文本）

| 原因 | `kind` |
|---|---|
| `ImageUrlError`（第 1 步，或由 client 抛出） | 它的 `failure_kind`：`INVALID_URL` / `UNSAFE_URL` |
| `ImageRedirectError` | 它的 `failure_kind`：`INVALID_URL` / `UNSAFE_URL`，或没有可用 `Location` 时的 `TRANSPORT_ERROR` |
| `ImageTimeoutError` | `TIMEOUT` |
| `ImageConnectionError` | `CONNECTION_ERROR` |
| `ImageRedirectLimitError` | `REDIRECT_LIMIT` |
| `ImageResponseTooLargeError` | `TOO_LARGE` |
| 其他任何 `ImageTransportError`（包括 `ImageClientClosedError`）、违反 protocol 的 client 抛出的其他任何普通 `Exception`，或者不是严格 `ImageHttpResponse` 的响应 | `TRANSPORT_ERROR` |
| 最终状态 `!= 200` | `HTTP_STATUS`，带 `http_status=<actual>` |
| `ImageContentTypeError` | `CONTENT_TYPE_MISMATCH` |
| `ImageJpegError` | `INVALID_JPEG` |
| `ImageDimensionError` | `INVALID_DIMENSIONS` |
| 角色的候选数超过 `max_candidates_per_role` | `CANDIDATE_LIMIT`（14.8） |
| 接受该图片会超过 `max_total_bytes` | `TOTAL_BYTES_LIMIT`（14.7） |

内容层面的失败永远不会被并入 `TRANSPORT_ERROR`。

### 14.6 Artifact 构造

`AcquiredImage(role, candidate_index, content, width, height, size_bytes,
sha256)`，其中 `content` 是响应的原始字节，`width` / `height` 复制自 SOF header 的 `JpegInfo`，
`size_bytes = len(content)`，`sha256 = hashlib.sha256(content).hexdigest()`。URL、Content-Type、HTTP 状态、
header 和响应对象都不保留。不去重：不同角色中相同的字节，或 extrafanart 中重复的字节，全部保留。

### 14.7 结果总量上限

`current_total` 是已接受图片的总和。一个大小为 `new_size` 的新合法 JPEG，当且仅当
`current_total + new_size <= max_total_bytes` 时才被接受（恰好等于边界时接受）。否则为该候选记录一个
`TOTAL_BYTES_LIMIT` 失败，**不**加入该载荷，并且整个 `acquire_images` 调用停止：不再对任何角色发出请求，
也不再记录任何失败；结果中包含此前已接受的图片以及到此为止的失败。非法载荷（non-200、错误的媒体类型、
非法 JPEG / 尺寸）永远不计入总量。瞬时内存以 `current_total + max_image_bytes` 为上限。

### 14.8 候选数量上限

如果 `len(candidates) > max_candidates_per_role`，该角色发送**零**个请求，并记录一个 `CANDIDATE_LIMIT` 失败，
其 `candidate_index = max_candidates_per_role`（第一个不允许进入处理的下标）。不做静默截断。其他角色继续处理。
恰好 `max_candidates_per_role` 个候选时正常处理。

### 14.9 Extrafanart 上限

成功获取 `max_extrafanart` 张 extrafanart 图片之后，extrafanart 的处理正常结束：后续候选既不会被请求，
也不会被记录（这**不是** `CANDIDATE_LIMIT`）。失败的候选不计入该上限。

### 14.10 角色隔离与失败排序

一个角色中的失败永远不会清除另一个角色中的成功；每个单一角色保留其第一个成功结果，extrafanart 按候选顺序
保留其成功结果。`failures` 按实际处理顺序排列（先按角色顺序，再按候选顺序）。
对于相同的记录、策略和脚本化的 client 应答，`acquire_images` 返回相等的结果（相同的请求顺序、失败、
extrafanart 顺序、候选下标、摘要和尺寸）。

### 14.11 取消与致命异常

`asyncio.CancelledError`（调用方的取消，或由 client 抛出）原样传播；它永远不会被记录为失败，也不会再尝试任何
后续候选。`KeyboardInterrupt`、`SystemExit`、`GeneratorExit` 以及其他所有非 `Exception` 的 `BaseException`
都原封不动地传播。只有 client 抛出的普通 `Exception` 才会变成失败。

### 14.12 敏感数据排除与副作用

`ImageAcquisitionResult` 的对象图只保存由内置类型构成的 `AcquiredImage` /
`ImageCandidateFailure` 值：没有 URL（用一个 `?token=SUPERSECRET` 候选测试），没有 `ImageHttpResponse`、
httpx 对象、异常、traceback、header 或 cookie。一个失败恰好是
`(role, candidate_index, kind, http_status)`。输入错误的消息写出字段名，绝不写出值。输入的记录、其 metadata
以及策略都不会被修改。`acquisition.py` 不做任何文件系统操作（只在内存中），只 import `__future__`、`hashlib`、
images 模块（包括 `transport` 的 Protocol / 响应模型）和 `fc2_organizer.publication`；从不 import `httpx`、
`fc2_metadata_core`、`amane`，不做 `asyncio` 任务扇出，也不 import 任何文件系统模块。

开发期间做过变异检查：在 `TOTAL_BYTES_LIMIT` 之后不停止、总量上限差一、静默截断候选、没有 extrafanart 上限、
捕获 `BaseException`、跳过 URL 预检查、把超时映射为 `TRANSPORT_ERROR`、接受 tuple 子类，以及单一角色在第一次
成功之后继续处理，都会让 `test_image_acquisition.py` 失败。

## 15. 合成图片门槛 -- IMPLEMENTED IN SUBSTEP 5

测试：`tests/unit/images/test_image_synthetic_gate.py`。

* **400** 个合成的 `PublicationRecord`（200 个 `SUCCESS`，200 个 `PARTIAL`），使用真实的 `build_organize_plan`
  和 `NormalizedMetadata` 构建，通过一个脚本化的内存 `ImageHttpClient` 获取（没有任何形式的网络）。
* 13 个场景族：没有候选；poster 第一个即成功；poster 回退
  （1-3 次失败后成功，覆盖 `None` / `image/jpeg` / 带参数的大小写混合 / `application/octet-stream` / `image/pjpeg`
  等媒体类型）；poster 全部失败；fanart + thumb；extrafanart 有 0..6 个候选、成功与失败混合；角色隔离场景；
  候选数量上限（其中一个角色恰好处于上限）；extrafanart 成功数上限；结果总量上限（恰好等于边界时接受 /
  超过时 -> 停止）；所有角色之间的重复内容；secret 哨兵值；全面混合。
* 失败变体：HTTP 404 / 403 / 429 / 500、超时、连接错误、重定向上限、不安全的重定向、过大的响应、`image/png`
  和 `text/html` 媒体类型、格式错误的 JPEG、过大和为零的尺寸、抛出普通异常的 client、不安全的 IP URL、
  `*.localhost` URL、相对（非法）URL、带 secret query 且超时的 URL。**每一种** `ImageFailureKind`
  都至少产生一次。
* 预期值来自用例定义，绝不来自生产结果：严格的请求顺序、同时最多一个请求在进行中、失败 tuple
  `(role, candidate_index, kind, http_status)`、每个角色的 artifact 角色 / 下标 / 字节 / 宽度 / 高度 / 大小 /
  SHA-256（由测试根据 fixture 字节计算）、extrafanart 顺序以及 `total_bytes`。
* 确定性：每个用例都在一个新的事件循环上重新运行；结果和请求顺序都相等。这证明了对于固定的响应脚本，
  算法是确定的 -- 它**不**对真实网络响应作出任何声明。
* 敏感数据：使用 `?token=SUPERSECRET` URL、在被拒绝的响应体中放入 `SECRET_RESPONSE_BODY`、在 client 异常中放入
  `SECRET_EXCEPTION_TEXT`，结果的 `repr` / `str`、失败的 `repr`、结果对象图中的任何节点都不包含 secret 或 URL，
  对象图中也不含任何异常、`ImageHttpResponse`、`httpx.Response` / `Request` / `Headers` / `Cookies`、
  traceback、dict 或 list。
* 文件系统：整个门槛在以下拦截下运行：`open`、`io.open`、`os`
  （`open`、`stat`、`lstat`、`listdir`、`scandir`、`mkdir`、`makedirs`、
  `remove`、`unlink`、`rename`、`replace`、`rmdir`、`getcwd`、`walk`）、
  `os.path`（`exists`、`isfile`、`isdir`、`getsize`、`realpath`）、`pathlib.Path` 的文件方法，以及 `shutil` 的
  copy / move / rmtree -- **0 次命中**（一个正向对照证明这些拦截确实会触发）。
* 取消回归：在获取过程中抛出 `asyncio.CancelledError` 的 client 会让它传播出去，不记录任何失败，也不再请求
  任何后续候选；`KeyboardInterrupt` / `SystemExit` / `GeneratorExit` 会传播。
* 直接复现 A-H（poster 404 回退；经由真实的 `HttpxImageClient` 搭配 `httpx.MockTransport` 的公网 -> 私网重定向，
  私网目标从未被请求；声明为 `image/png` 的合法 JPEG；格式错误的 JPEG；总量上限停止；fanart 失败隔离；
  secret token；取消时的对象身份一致）。

变异检查：substep-4 的 9 个获取变异体中有 8 个仅凭本门槛就能被杀死；第九个（接受 `tuple` 子类）无法由合法记录
产生，由 `test_image_acquisition.py` 杀死。

## 16. Package 状态与明确的范围之外（冻结）

实现状态：本合同的每一节（1-15）都已实现；P4-C5 内部没有任何待定内容。P4-C5 的关闭仍然需要独立复查。

P4-C5 **只产出内存中的 artifact**（`ImageAcquisitionResult`）。它**不做**、P4-C5 之后的任何 substep 也不会做：

* 文件系统写入或图片落盘（不创建任何文件，也不把任何角色映射到路径）；
* 覆盖 / 冲突决策；
* 缩放、裁剪、重新编码或转码；
* 修改 NFO（NFO 仍然不携带任何图片引用）；
* CLI / UI；
* 持久化 / 缓存；
* Amane 集成；
* DNS 解析或 DNS rebinding 防御（第 8.5、12.11 节）。

P4-C5：**NOT CLOSED**。Phase 4：**NOT CLOSED**。独立复查：**REQUIRED**。
