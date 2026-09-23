# Phase 4 / P4-C5 Handoff -- 图片获取（Image Acquisition）

```text
Phase        = 4
Package      = P4-C5
Role         = Developer
Branch       = claude/phase4-c5-image-acquisition
```

## 1. 坐标

```text
Frozen Base                  = 97f6aeba8d11d9bc8a29d5397b9a1e1711d36cd6
Substep 1 Head               = a961dda486bc8377bd2cec8ae9dd107f5379eba4   foundation: models / policy / URL safety
Substep 2 Head               = d7c1bd9173cb88be399368a4a7a9083f52f73e72   binary HTTP transport
Substep 3 Head               = 4c780a88dd97613e97fe6a0f139deddcbfb40066   JPEG-only content validation
Substep 4 Head               = 9fff05ec1e8dbec3fce65dd9453fa41b8a4b786e   acquire_images orchestration
P4-C5 Code Review Candidate  = 3ef881b416439accf634ce792723b49d01db0d64   synthetic gate + frozen contract
P4-C5 Docs Head              = <this commit; see `git log -1 -- fc2-organizer/docs/review/P4_C5_HANDOFF.md`>
Remote Head                  = <== Docs Head after push of this commit>

Code Review Range: 97f6aeba8d11d9bc8a29d5397b9a1e1711d36cd6..3ef881b416439accf634ce792723b49d01db0d64
Docs Review Range: 3ef881b416439accf634ce792723b49d01db0d64..<Docs Head>
```

历史是线性的：`97f6aeb -> a961dda -> d7c1bd9 -> 4c780a8 -> 9fff05e -> 3ef881b -> Docs Head`。
每个 substep 都从一个经过验证的 `HEAD == origin/claude/phase4-c5-image-acquisition == <parent>` 开始，
工作区干净（只有未跟踪的测试框架目录 `.claude/`）。没有 rebase、amend、squash 或 force push。Code Review Candidate 包含代码、
测试以及冻结的合同（`PHASE4_IMAGE_ACQUISITION_CONTRACT.md`）；Docs Head 提交只包含本文件。

## 2. 类型

**NEW PACKAGE**（`fc2_organizer.images`）+ 四处一行的 package 集合作用域守卫更新
（`{"discovery", "planning", "publication", "nfo"}` -> `+ "images"`）。`fc2_organizer/images/` 之外没有任何生产文件被触碰；
`fc2_organizer/__init__.py` 没有改变。Substep 5 没有改动任何生产代码（只有门槛测试 + 合同）。

## 3. 变更文件（Code Review Range，22 个文件，+5890 / -4）

新增（18）：
```text
fc2-organizer/docs/specifications/PHASE4_IMAGE_ACQUISITION_CONTRACT.md
fc2-organizer/src/fc2_organizer/images/__init__.py
fc2-organizer/src/fc2_organizer/images/errors.py
fc2-organizer/src/fc2_organizer/images/models.py
fc2-organizer/src/fc2_organizer/images/policy.py
fc2-organizer/src/fc2_organizer/images/urls.py
fc2-organizer/src/fc2_organizer/images/transport.py
fc2-organizer/src/fc2_organizer/images/jpeg.py
fc2-organizer/src/fc2_organizer/images/acquisition.py
fc2-organizer/tests/contract/test_images_architecture.py
fc2-organizer/tests/unit/images/__init__.py
fc2-organizer/tests/unit/images/test_image_models.py
fc2-organizer/tests/unit/images/test_image_policy.py
fc2-organizer/tests/unit/images/test_image_urls.py
fc2-organizer/tests/unit/images/test_image_transport.py
fc2-organizer/tests/unit/images/test_image_jpeg.py
fc2-organizer/tests/unit/images/test_image_acquisition.py
fc2-organizer/tests/unit/images/test_image_synthetic_gate.py
```

修改（4，各一行 -- 只是 package 集合；没有改动任何禁止 import 守卫、运行时阻断器、允许列表或反向依赖守卫）：
```text
fc2-organizer/tests/contract/test_discovery_architecture.py
fc2-organizer/tests/contract/test_planning_architecture.py
fc2-organizer/tests/contract/test_publication_architecture.py
fc2-organizer/tests/contract/test_nfo_architecture.py
```

## 4. 公开 API

```python
# stdlib-only, from fc2_organizer.images
validate_image_url(url) -> str
validate_image_content_type(content_type) -> ContentTypeVerdict
inspect_jpeg(content) -> JpegInfo
validate_acquired_image(content, content_type) -> JpegInfo
ImageRole, ImageFailureKind, AcquiredImage, ImageCandidateFailure, ImageAcquisitionResult,
ImageAcquisitionPolicy, JpegInfo, error classes / reason enums, MAX_* constants

# explicit imports (depend on httpx / publication; not loaded by `import fc2_organizer.images`)
from fc2_organizer.images.transport import ImageHttpClient, ImageHttpResponse, HttpxImageClient
from fc2_organizer.images.acquisition import acquire_images

async def acquire_images(record: PublicationRecord, client: ImageHttpClient, *,
                         policy: ImageAcquisitionPolicy | None = None) -> ImageAcquisitionResult
```

不存在任何 `write`、`save`、`materialize`、`download_to`、路径或文件 API。

## 5. 模型（合同 3-6）

全部为 `@dataclass(frozen=True, slots=True)`，按严格类型校验（`bool` 永远不算 `int`，任何子类都不能通过）。
`AcquiredImage(role, candidate_index, content, width, height, size_bytes,
sha256)`：严格 `bytes`（不出现在 `repr` 中），`size_bytes == len(content)`，`sha256` = **`content` 的**小写十六进制摘要。
`ImageCandidateFailure(role, candidate_index, kind, http_status)`：`http_status` 为严格 `int` 100..599，当且仅当
`kind is HTTP_STATUS`。`ImageAcquisitionResult(poster,
fanart, thumb, extrafanart, failures)`：角色匹配的槽位，严格 tuple，纯属性 `total_bytes`。
没有任何模型带有 URL / header / cookie / body / 异常 / 自由文本字段。

## 6. 策略（合同 7）

`ImageAcquisitionPolicy`：`request_deadline_seconds=15.0`、`max_redirects=5`、
`max_image_bytes=16 MiB`、`max_total_bytes=64 MiB`、`max_candidates_per_role=16`、
`max_extrafanart=12`；严格类型，有限 / `> 0`，`max_image_bytes <= max_total_bytes`
（`ImagePolicyError`）。运行时由 transport（deadline、重定向、单张图片字节数）以及 `acquire_images`
（总字节数、候选数量、extrafanart）强制执行。

## 7. URL 安全（合同 8）

`validate_image_url`：首先检查 `type(url) is str`（恶意 `str` 子类：运行的钩子为 0 个）；返回同一个对象，从不规范化 / strip /
重新加引号。只接受 `http` / `https`；拒绝相对 URL、`file:` / `data:` / `ftp:` / `javascript:`、userinfo、`localhost` /
`*.localhost`、空白 / 控制字符、反斜杠、`%` / 非 ASCII / 格式错误的 host、非规范的数字 host（`2130706433`、
`0x7f.1`、`127.1`、`0177.0.0.1`）以及非全局 IP（私有、回环、链路本地，包括 `169.254.169.254`、组播、保留、未指定、共享、
IPv4-mapped / 6to4 / NAT64 / Teredo 嵌入）。`ImageUrlError` 只带 reason。**不做 DNS 解析；明确没有处理 DNS rebinding**
（8.5、12.11）。

## 8. Transport（合同 12）

`HttpxImageClient`：每个实例一个 `AsyncClient`（在 `__init__` 中创建，绝不按请求创建，也绝不在 import 时创建），
`follow_redirects=False`、`trust_env=False`，只有固定的 `Accept` / `Accept-Encoding: identity` / `User-Agent`，
没有 auth / cookie / 调用方 header，服务器 cookie 永远不会被重放，并在 httpx 与校验器的解析结果之间交叉核对 host。
每一跳只发送一次（不重试）。生命周期：async 上下文管理器 / 幂等的 `aclose()`；关闭后使用 -> `ImageClientClosedError`。
`ImageHttpResponse(status_code, content_type, content)`：只含内置类型的值；除非状态为 200，否则响应体为 `b""`。

## 9. 重定向（合同 12.4）

301 / 302 / 303 / 307 / 308 手动处理。一个响应钩子会在 httpx 自己解析 `Location` 之前把它停下；目标通过 `urljoin` 解析，
并在下一跳**之前**用 `validate_image_url` 重新校验 -- 不安全的目标永远不会被请求（测试断言了请求列表）。
`max_redirects = N` 会跟随 N 次重定向；第 (N+1) 次 -> `ImageRedirectLimitError`，并且不请求它（边界 0 / 1 / 5 / 6）。
缺失 / 空白的 `Location` -> `ImageRedirectError`。重定向的响应体永远不会被读取。

## 10. 流式读取的上界（合同 12.5-12.7）

只有最终为 200 的响应才会被流式读取；其他状态在不读取响应体的情况下返回（拉取的块为 0 个）。`Content-Encoding` 必须是 identity。
在追加之前先计算块的大小；恰好 `max_bytes` 会被接受，`max_bytes + 1` 会立即停止（不再拉取任何后续块）。格式正确的
`Content-Length > max_bytes` 会在读取之前拒绝（按长度比较，绝不对超长字符串调用 `int()`）；格式错误 / 谎报的值会被忽略，
流式计数器仍然生效。一个 `asyncio.timeout` 覆盖所有跳转 + header + 响应体（不会每一跳都重置）；每一种超时 -> `ImageTimeoutError`。

## 11. JPEG 校验与尺寸（合同 13）

只接受 JPEG（没有 Pillow，不转码）。Content-Type：接受 `image/jpeg|jpg|pjpeg`；`None` / `application/octet-stream` 交由字节
内容判断；其他任何显式类型 -> `CONTENT_TYPE_MISMATCH`，即使响应体是合法的 JPEG。`inspect_jpeg`：单次有界遍历 -- SOI、
填充字节、TEM / RSTn、带长度检查的段、只接受 13 个真正的 SOF marker（绝不是 DHT / JPG / DAC）、SOF / SOS header 形态、
恰好位于末尾的 EOI；不扫描熵编码数据。只是结构性的：不承诺每一个解码器都能解码。尺寸来自 SOF：`0 < w, h <= 20000`，
`w*h <= 100_000_000`（`INVALID_DIMENSIONS`），在结构校验之后判断。严格的 `bytes` / `str` 边界，恶意钩子运行 0 次；
没有任何内部异常泄漏出来（所有前缀 + 3000-case fuzz）。

## 12. 编排与失败隔离（合同 14）

角色 `POSTER <- poster_urls`、`FANART <- fanart_urls`、`THUMB <- thumb_urls`、
`EXTRAFANART <- extrafanart`；没有跨角色回退。按 poster -> fanart -> thumb -> extrafanart 的顺序严格串行，候选按 tuple 顺序，
同时最多一个请求在进行中，每个候选最多请求一次。每个候选：URL 门 -> `get` -> 200 -> Content-Type -> JPEG ->
尺寸 -> 总量上限 -> `AcquiredImage`。任何失败都记录为
`(role, candidate_index, kind[, http_status])`，然后尝试同一角色的下一个候选；一个角色的失败永远不会清除另一个角色的成功。
失败映射依据异常类型（URL / 重定向 -> `INVALID_URL` / `UNSAFE_URL`；超时、连接、重定向上限、过大；其他 transport / client 错误 ->
`TRANSPORT_ERROR`；non-200 -> 带状态码的 `HTTP_STATUS`；Content-Type / JPEG / 尺寸失败保持各自的 kind）。候选的形态
（由严格 str 组成的严格 tuple，四个角色全部检查）在任何请求之前检查 -> `ImageInputError`，消息只写出字段名。不去重。

## 13. 内存上限（合同 14.7-14.9）

* 单张图片：`max_image_bytes`（transport 的流式上限）。
* 总量：当且仅当 `current_total + new_size <= max_total_bytes` 时接受一张图片（恰好等于边界时接受）；否则记录
  `TOTAL_BYTES_LIMIT`，丢弃该载荷，并且**不再对任何角色发出请求**。瞬时内存 <= `current_total + max_image_bytes`。
* 候选：`len > max_candidates_per_role` -> 该角色发出 0 个请求，并在 `candidate_index = max_candidates_per_role` 处记录一个
  `CANDIDATE_LIMIT`；不做静默截断。
* Extrafanart：成功 `max_extrafanart` 次之后，处理正常结束（不再请求或记录任何内容）。

## 14. 敏感数据（合同 12.9、14.12、15）

结果只保存内置类型的值 / images 模型：对象图中任何地方都没有 URL、query token、`ImageHttpResponse`、httpx 对象、异常、
traceback、header、cookie、dict 或 list。所有错误消息都是固定文本 + reason 枚举；绝不包含 URL、Content-Type 值、载荷字节、
库消息或异常 `repr`；transport 错误永远不做异常链接。已用 `?token=SUPERSECRET`、`SECRET_RESPONSE_BODY`、
`SECRET_EXCEPTION_TEXT` 哨兵值验证。

## 15. 取消

`asyncio.CancelledError`（来自调用方或 client）从 transport 和 `acquire_images` 中都原样传播：绝不映射，绝不记录，也不再尝试任何
后续候选。`KeyboardInterrupt`、`SystemExit`、`GeneratorExit` 以及其他非 `Exception` 的 `BaseException` 都会传播。
只有普通的 `Exception` 才会被映射。

## 16. 架构（合同 10）

```text
fc2_organizer.images  foundation (__init__, errors, models, policy, urls, jpeg): stdlib only
fc2_organizer.images.transport   : + httpx            (the ONLY httpx importer)
fc2_organizer.images.acquisition : + images modules, transport Protocol / response, fc2_organizer.publication
```

从不：（直接）依赖 `fc2_metadata_core`、`amane`、文件系统模块，也不在获取过程中做 `asyncio` 扇出。没有反向依赖
（core、discovery、planning、publication、nfo 从不 import images）。`import fc2_organizer` 不加载任何 images 模块；
`import fc2_organizer.images` 既不加载 `transport`、`acquisition`、`publication`，也不加载 httpx。顶层子 package 恰好是
`{"discovery", "planning", "publication", "nfo", "images"}`。由
`tests/contract/test_images_architecture.py` 强制执行（19 个测试：模块集合、按模块的允许列表、AST 调用禁令、client 的构造
位置 / 标志、在网络 / core / amane 被阻断时的运行时 import）。

## 17. 合成门槛（合同 15）

`tests/unit/images/test_image_synthetic_gate.py`（18 个测试）：

* 400 个记录（200 SUCCESS / 200 PARTIAL），13 个场景族，19 种失败变体；每一种 `ImageFailureKind` 都被产生；
  extrafanart 有 0..6 个候选。
* 预期的请求顺序、角色、下标、kind、状态、字节、宽度 / 高度、SHA-256（用 hashlib 对 fixture 字节计算）、extrafanart 顺序以及
  `total_bytes` 都来自用例定义 -- 而不是生产输出。全部 400 个都匹配。
* 确定性：每个用例都重新运行 -> 结果和请求顺序都相等（仅针对固定的响应脚本；不对线上响应作任何声明）。
* 对全部 400 个结果做敏感数据对象图遍历：secret / URL / 存活对象命中为 0。
* 文件系统拦截（`open`、`io.open`、`os`、`os.path`、`pathlib.Path`、`shutil`、`getcwd`），带正向对照：**0 次命中**。
  没有真实网络（假 client；复现 B 使用 `httpx.MockTransport`）。
* 取消 / 致命异常回归。
* 变异：8 / 9 个 substep-4 获取变异体仅凭本门槛就被杀死（第 9 个，即接受 `tuple` 子类，无法由合法记录产生，
  由 `test_image_acquisition.py` 杀死）。更早的 substep 也以同样方式做过变异检查（transport 3/3、JPEG 6/6、
  acquisition 9/9，在各自的测试文件中；URL 严格类型 1/1）。

## 18. 直接复现（全部在门槛文件中，全部通过）

```text
A  poster 404 -> second candidate valid           => second wins, failure (HTTP_STATUS, 404)
B  public URL 302 -> http://10.1.2.3/...           => private target never requested (real HttpxImageClient
                                                      over MockTransport); UNSAFE_URL; next candidate wins
C  valid JPEG declared image/png                   => CONTENT_TYPE_MISMATCH
D  malformed JPEG                                  => INVALID_JPEG
E  fanart would exceed max_total_bytes             => TOTAL_BYTES_LIMIT; thumb / extrafanart never requested
F  fanart timeout                                  => poster and thumb successes remain
G  ?token=SUPERSECRET failing (+ forged shape)     => no secret in result repr / str / failures / error
H  CancelledError from the client                  => the same exception object propagates; no next request
```

## 19. 测试

针对性测试（`-p no:cacheprovider --basetemp=<job temp>`）：

```text
tests/unit/images/test_image_models.py           59
tests/unit/images/test_image_policy.py           63
tests/unit/images/test_image_urls.py            102
tests/unit/images/test_image_transport.py       125
tests/unit/images/test_image_jpeg.py            119
tests/unit/images/test_image_acquisition.py      86
tests/unit/images/test_image_synthetic_gate.py   18
tests/contract/test_images_architecture.py       19
tests/contract/test_discovery_architecture.py    12
tests/contract/test_planning_architecture.py     13
tests/contract/test_publication_architecture.py  19
tests/contract/test_nfo_architecture.py          17
-------------------------------------------------
652 passed, 0 failed, 0 skipped
```

全量测试（`python -m pytest -q -p no:cacheprovider --basetemp=<job temp>`，PYTHONPATH=src）：
**3811 passed, 14 skipped, 0 failed**。每一次 P4-C5 substep 运行的跳过数都是 14
（3454 / 3583 / 3704 / 3793 / 3811 passed）；没有任何 P4-C5 测试被跳过。P4-C1 / P4-C2 / P4-C3 /
P4-C4 / Phase 3 都没有回归。

观察（不是 P4-C5 的改动）：较早的一次全量运行在一台负载较高的机器上（耗时 96 s，而不是约 ~50-60 s）失败了
`tests/unit/aggregation/test_agg_retry_execution.py::test_17_total_deadline_covers_attempt_backoff_and_retry_not_deadline_times_attempts`
（冻结的 Phase 3 代码中的一个墙钟计时断言）；该文件单独运行时通过（56 passed），在随后的全量运行中也通过。同一次运行暴露了新门槛
文件中的一个测试顺序 bug（在架构测试清理 `sys.modules` 之后的一个函数内局部 import）；已在候选提交之前在门槛测试中修复。

## 20. 已知局限（记录在合同中，非阻塞）

* 没有 DNS 解析 / 连接时地址检查：解析到私有地址的公网 hostname 仍然会被连接；没有处理 DNS rebinding（8.5、12.11）。
* JPEG 校验只是结构性的；不解码熵编码数据 / 表的内容（13.3）。
* `record.metadata` 的可信程度以 `PublicationRecord` 所保证的为限（`isinstance`）；恶意的 `NormalizedMetadata` 子类属于延续下来的
  P4-C4-R-01 那一类 finding（14.2）。
* 明确的范围之外（合同 16）：文件系统写入 / 落盘、覆盖 / 冲突、缩放 / 裁剪 / 转码、修改 NFO、CLI / UI、持久化、Amane。

## 21. 阻塞性的已知问题

无。

## 22. 延续的 finding（P4-C5 未改变）

```text
P4-C4-R-01 -- LOW
P4-C3-R-01 -- LOW
P4-C3-R-02 -- LOW
P4-C2-R1-02 -- LOW
OrganizePlan operation-graph hardening
overwrite executor semantics = NEVER
extended Windows reserved names
P4-C1-R-02..R-05
P2-R-05
P2-R-06
P2-R-07
C3-N1..N4
C4-N1
C4-R1-N1..N3
F3
F5
C5-R1-L1
fc2db_net release normalization = un-numbered upstream observation
```

更早之前已关闭、不再延续：P4-C2 metadata 身份缺口、C2-L2、P2-R-10。

## 23. 整洁性

`git diff --check` 在 Code Review Range 和 Docs Review Range 上都干净；推送后工作区干净；Remote Head == Docs Head。

## 24. 状态

```text
Independent Review = REQUIRED
P4-C5              = NOT CLOSED
Phase 4            = NOT CLOSED
```

开发者不宣布 P4-C5 或 Phase 4 关闭。


---

# R1 修复 -- P4-C5-R-01（HIGH）、P4-C5-R-02（MEDIUM）

上面的各节是未改动的原始 handoff。本节只记录 R1：没有新功能，没有触碰其他 package。

```text
Branch                       = claude/phase4-c5-image-acquisition
R1 Base                      = d8831d255e7a509fe24544ef5e1652d6c2fdb513
Previous Reviewed Code Head  = 3ef881b416439accf634ce792723b49d01db0d64
R1 Code Review Candidate     = 65036e3857f87d821b5b282d7162ddbdabd42773
R1 Docs Head                 = <this commit; see `git log -1 -- fc2-organizer/docs/review/P4_C5_HANDOFF.md`>
Remote Head                  = <== R1 Docs Head after push>

R1 Code Review Range: d8831d255e7a509fe24544ef5e1652d6c2fdb513..65036e3857f87d821b5b282d7162ddbdabd42773
R1 Docs Review Range: 65036e3857f87d821b5b282d7162ddbdabd42773..<R1 Docs Head>
```

在任何改动之前已验证：`git fetch --all --tags`；HEAD ==
`origin/claude/phase4-c5-image-acquisition` == `d8831d2`；工作区干净。没有
rebase / amend / squash / force push。

## R1.1 变更文件（R1 Code Review Candidate，3 个文件，+407 / -17）

```text
fc2-organizer/src/fc2_organizer/images/transport.py                  (fix)
fc2-organizer/tests/unit/images/test_image_transport.py              (+47 regression tests, appended)
fc2-organizer/docs/specifications/PHASE4_IMAGE_ACQUISITION_CONTRACT.md (12.7 note, new 12.9a)
```

没有触碰：`errors.py`（不需要新的错误类）、`urls.py`、`jpeg.py`、
`acquisition.py`、`models.py`、`policy.py`，以及其他每一个 Phase 4 package。

## R1.2 P4-C5-R-01 -- 清理异常边界：FIXED

根因：`_follow` 在一个裸的 `finally: await
response.aclose()` 中关闭响应，`_read_body` 也以同样方式关闭它的字节迭代器。因此，清理时抛出的普通异常会：(a) 替换一个已经返回的
值（non-200 / `TOO_LARGE` 路径），从而以一个携带消息、`httpx.Request` 和 URL/token 的原始 httpx 异常形式逃过 `_map_exception`；
以及 (b) 替换一个正在传播的 `CancelledError`。在 (b) 之后，`asyncio.timeout` 再也无法把 deadline 转换为 `ImageTimeoutError`，
调用方的取消也丢失了。

修复（`transport.py`）：

* `_cleanup(close)` 执行一个清理步骤。普通 `Exception` 通过现有的基于类型的 `_map_exception` 变成一个新的错误值（httpx
  `NetworkError`，包括 `CloseError` / `ProtocolError` / `ProxyError` ->
  `ImageConnectionError`；超时系列 -> `ImageTimeoutError`；其他任何异常 ->
  `ImageTransportError`）。它只是被创建，从不被抛出，因此没有 cause、context 或 traceback。清理本身抛出的 `BaseException`
  会继续传播。
* 响应处理的主体移到了 `_response_outcome` 中，它把每一种普通失败都作为值返回。然后 `_follow` 要么 (a) 正常关闭，要么 (b)
  在遇到 `BaseException` 时通过 `_cleanup` 关闭，并重新抛出**原始对象**（裸 `raise`）。
* 优先级：已有的错误值胜过清理错误。清理错误只会替换一个成功的 `ImageHttpResponse`（fail closed）。正在传播的取消 / 致命异常
  总是胜过普通的清理错误。
* `_read_body` 对字节迭代器使用同样的模式（使用 `too_large` 标志，而不是在 `try` 内部返回）。

## R1.3 保持取消 / 致命异常

* 主异常为 `CancelledError`、自定义 `BaseException`、`KeyboardInterrupt`、`SystemExit` 和 `GeneratorExit`，并伴随一次失败的清理
  （httpx `CloseError` 或 `RuntimeError`）：抛出的对象 `is` 主异常。共 10 个参数化用例，在同一个任务中捕获以验证身份一致。
* 读取响应体期间调用方真实地 `task.cancel()`，加上一次失败的清理：`CancelledError` 传播出去。
* 读取响应体期间 deadline 到期，加上一次失败的清理（httpx 或普通异常）：`ImageTimeoutError`。
* 由*清理本身*抛出的取消 / 致命异常（`_R1Fatal`、`KeyboardInterrupt`、`CancelledError`）以同一个对象传播：绝不被吞掉，也绝不被映射。

## R1.4 P4-C5-R-02 -- 超大 deadline：FIXED

可接受的输入域没有改变：`ImageAcquisitionPolicy(request_deadline_seconds=10**400)` 仍然合法，`get()` 仍然接受任何严格的正
`int`。`_deadline_delay` 依据异常类型（转换时的 `OverflowError`，不做消息嗅探），一次性地把 deadline 转换为 float。如果它无法
被表示（`10**400`、`10**309`、`2**1024`），`get()` **什么都不发送**，并抛出一个新的、消息固定的 `ImageTransportError`
（`TRANSPORT_ERROR`），其 cause 和 context 为 `None`。在 R1 之前，这些情况会从 `asyncio.timeout` 泄漏出 `OverflowError`。
获取层本来就会把 `get()` 抛出的任何 `Exception` 记录为单个候选的失败，因此对于这样的策略，它现在会记录 `TRANSPORT_ERROR`。
可以表示的 deadline 没有改变：`15.0`、`1`、`5`、`3600`、`10**300`、`10**308`、`1e300` 和 `sys.float_info.max`
都恰好以一个请求成功。

## R1.5 新增的回归测试（`test_image_transport.py`，47 个用例）

使用的 secret：异常消息 `SECRET_EXCEPTION_TEXT`，以及同时用作消息 URL 和异常的 `httpx.Request` 的
`https://example.com/x.jpg?token=SUPERSECRET`。`assert_r1_clean` 检查：
* `str` / `repr` / `args` 不包含 secret、token、host、httpx 名称或 `<Request` / `<Response`；
* `__cause__` 和 `__context__` 为 `None`；
* 对象图遍历（args、cause、context、`__dict__`、notes、reason）中没有 `httpx.Request` / `httpx.Response` /
  `httpx.HTTPError`，除了它自己之外也没有其他异常；
* traceback 中没有 worker / cleanup 栈帧，也没有这些类型的栈帧局部变量。

| # | 场景 | 预期 |
|---|---|---|
| 1 | non-200（404/500/204）+ 关闭时 httpx `CloseError` | `ImageConnectionError`，读取的响应体块为 0 |
| 1b | non-200 + 关闭时 `RuntimeError` | `ImageTransportError` |
| 2 | 200 成功 + 关闭时 `CloseError` / `ValueError` | `ImageConnectionError` / `ImageTransportError` |
| 3 | `TOO_LARGE`（流式读取与声明的两种）+ `CloseError` | `ImageResponseTooLargeError`（保留主错误） |
| 3b | 流式读取中途 `ReadError` + 清理时 `RuntimeError` | `ImageConnectionError`（保留主错误） |
| 4 | 读取响应体期间 deadline 到期 + `CloseError` / `RuntimeError` | `ImageTimeoutError` |
| 5 | 调用方取消 + `CloseError`；主异常 `CancelledError` + 清理错误 | `CancelledError`，同一个对象 |
| 6 | 主异常为自定义致命异常 / `KeyboardInterrupt` / `SystemExit` / `GeneratorExit` + 清理错误 | 同一个对象 |
| 7 | 清理本身抛出致命异常 / `KeyboardInterrupt` / `CancelledError` | 同一个对象，不映射 |
| 8 | `_cleanup` 按类型映射（消息具有误导性），并返回没有 cause / context / traceback 的值 | 由类型决定 |
| 9 | 清理成功 | 响应不变 |
| R2 | `10**400`、`10**309`、`2**1024` | `ImageTransportError`，没有请求，没有 `OverflowError` |
| R2 | 策略仍然接受 `10**400`；`_deadline_delay` 基于类型 | 输入域不变 |
| R2 | `15.0`、`1`、`5`、`3600`、`10**300`、`10**308`、`1e300`、`float max` | 成功，一个请求 |

变异检查：这 47 个用例针对 `d8831d2` 的 `transport.py` 运行。
**26 个失败**，表现为原始的 `httpx.CloseError`（带 secret 消息）、`RuntimeError`、`OverflowError` 或缺少 helper。在那里通过的
21 个是预期的对照：200 路径的关闭（httpx 在迭代内部关闭，本来就已被映射）、来自清理的致命异常、可以表示的 deadline、
策略输入域以及成功的清理。

## R1.6 测试

```text
New regression only : python -m pytest tests/unit/images/test_image_transport.py -k "r1 or r2" -q
                      47 passed
Targeted            : python -m pytest tests/unit/images tests/contract/test_images_architecture.py -q
                      632 passed, 0 failed, 0 skipped
Full suite          : python -m pytest -q
                      3852 passed, 14 skipped, 0 failed
```

所有运行都在 `fc2-organizer/` 下进行，带 `-p no:cacheprovider
--basetemp=<job-owned tmp>`（已知的本地 pytest 临时目录权限问题）。14 个跳过与 R1 之前的数量相同：原有的 Windows symlink 权限
跳过以及仅限 POSIX 的路径形式跳过。没有任何 images 测试被跳过。

## R1.7 延续 / 未改变

除 P4-C5-R-01 / R-02 之外，没有处理任何其他 finding。上面列出的每一项延续债务都没有改变，未编号的 fc2db_net release 观察也没有改变。

## R1.8 整洁性

```text
git diff --check (R1 code range, R1 docs range) -> clean
git status --porcelain after push             -> clean
```

## R1.9 状态

```text
P4-C5-R-01          = FIXED (pending independent re-review)
P4-C5-R-02          = FIXED (pending independent re-review)
Independent Re-review = REQUIRED
P4-C5               = NOT CLOSED
Phase 4             = NOT CLOSED
```


---

# 最终关闭 -- P4-C5 图片获取（Image Acquisition）

上面的各节没有改变。本节只追加、只涉及文档：它记录 P4-C5 的最终关闭。没有触碰任何代码、测试或合同文件，也没有开始任何后续 package。

## F.1 关闭记录

```text
Phase                        = 4
Package                      = P4-C5 Image Acquisition
Branch                       = claude/phase4-c5-image-acquisition
Status                       = CLOSED
Final Review                 = Incremental Level 1 PASS
Final Reviewed Code Head     = 65036e3857f87d821b5b282d7162ddbdabd42773
Previous Docs Head           = b0ee039a83228dc42d900b6423e2a4f0274a7926
Closure Docs Head            = <this commit; its parent is the Previous Docs Head>
```

在本次改动之前已验证：`git fetch --all --tags`；HEAD ==
`origin/claude/phase4-c5-image-acquisition` == `b0ee039`；工作区干净。没有
rebase / amend / squash / force push。

## F.2 复查历史

```text
Initial Level 1 review      (code 3ef881b, docs d8831d2)
  P4-C5-R-01 -- HIGH    response / stream cleanup raising an ordinary exception bypassed
                        the image transport error boundary: raw httpx exception,
                        httpx.Request and the token-bearing URL could escape.
  P4-C5-R-02 -- MEDIUM  a contract-accepted huge deadline (e.g. 10**400) leaked a bare
                        OverflowError.

R1 remediation
  R1 Code Review Candidate = 65036e3857f87d821b5b282d7162ddbdabd42773
  R1 Docs Head             = b0ee039a83228dc42d900b6423e2a4f0274a7926

Independent Incremental Level 1 re-review (d8831d2..65036e3, 65036e3..b0ee039)
  Verdict = PASS
  P4-C5-R-01 = CLOSED
  P4-C5-R-02 = CLOSED
```

两项 finding 都已关闭，不再延续。

## F.3 R1 独立证据（复查者自己的结果）

```text
Context Handshake                  = PASS
Diff Scope                         = PASS
P4-C5-R-01                         = CLOSED
Cleanup Error Mapping              = PASS
Sensitive-Data Boundary            = PASS
Cancellation / Fatal Preservation  = PASS
P4-C5-R-02                         = CLOSED
Huge Deadline Boundary             = PASS
Normal Deadline Regression         = PASS
Transport Regression               = PASS

Independent probes                 = 434 PASS / 0 FAIL
Targeted: test_image_transport.py  = 166 passed / 0 failed / 0 skipped
Targeted: images + architecture    = 632 passed / 0 failed / 0 skipped
Full Suite                         = 3852 passed / 14 skipped / 0 failed
git diff --check                   = clean on both R1 code and docs ranges

New Findings                       = NONE
Blocking Findings                  = NONE
```

## F.4 最终的 package 状态

```text
URL safety                  = CLOSED / accepted
Redirect safety             = CLOSED / accepted
Binary streaming bounds     = CLOSED / accepted
Deadline handling           = CLOSED / accepted
Transport error boundary    = CLOSED / accepted
JPEG / Content-Type         = CLOSED / accepted
Dimension validation        = CLOSED / accepted
Candidate ordering          = CLOSED / accepted
Role isolation              = CLOSED / accepted
Candidate limits            = CLOSED / accepted
Extrafanart limit           = CLOSED / accepted
Total-result memory cap     = CLOSED / accepted
Cancellation                = CLOSED / accepted
Sensitive-data exclusion    = CLOSED / accepted
Architecture boundary       = CLOSED / accepted
Synthetic gate              = CLOSED / accepted
```

## F.5 已记录的非阻塞边界（不是 finding）

这些是记录在合同中的已知边界（见第 20 节）。它们不是新的 finding，也不阻塞 P4-C5：

* DNS rebinding：P4-C5 中没有防御。
* JPEG 校验：只是结构性的，不是完整解码器的保证。
* 恶意的 `NormalizedMetadata` 子类：由延续下来的 P4-C4-R-01 背景覆盖。

## F.6 延续的 finding

```text
P4-C4-R-01 -- LOW
P4-C3-R-01 -- LOW
P4-C3-R-02 -- LOW
P4-C2-R1-02 -- LOW
OrganizePlan operation-graph hardening
overwrite executor semantics = NEVER
extended Windows reserved names
P4-C1-R-02..R-05
P2-R-05
P2-R-06
P2-R-07
C3-N1..N4
C4-N1
C4-R1-N1..N3
F3
F5
C5-R1-L1
fc2db_net release normalization = un-numbered upstream observation
```

不再延续（在 P4-C5 中 CLOSED）：P4-C5-R-01、P4-C5-R-02。
更早之前已关闭、不再延续：P4-C2 metadata 身份缺口、C2-L2、P2-R-10。

## F.7 最终状态

```text
P4-C5-R-01    = CLOSED
P4-C5-R-02    = CLOSED
New Findings  = NONE
Blocking      = NONE
Targeted      = 632 passed / 0 failed / 0 skipped
Full Suite    = 3852 passed / 14 skipped / 0 failed
P4-C5         = CLOSED
Phase 4       = NOT CLOSED
Next Package  = NOT STARTED
```
