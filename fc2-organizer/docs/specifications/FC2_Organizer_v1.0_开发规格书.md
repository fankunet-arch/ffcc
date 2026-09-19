# FC2 Organizer v1.0 开发规格书

**文档版本：** 1.0-draft1  
**基线日期：** 2026-09-19  
**状态：** 开发基线  
**项目定位：** FC2 专用的 TMM 式批量媒体整理系统

## 核心冻结决策

1. 宿主采用官方 Amane 原版，不直接修改主程序源码。
2. FC2 能力拆为 `amane-fc2-adapter` + 独立 `FC2 Metadata Engine`。
3. **新片源/多片源是 P0。** 发布时至少 3 个可配置来源，至少 2 个替代/新来源在用户实际环境通过测试。
4. **批量是 P0。** 扫描、刮削、重刮、NFO/图片、整理、失败重试都必须支持批量。
5. 多源必须支持字段级聚合，单个来源失败不得判整片失败。
6. 主程序升级最多影响 Adapter；Metadata Engine 与 scraper 不应随宿主升级重写。
7. 任何失败场景不得静默删除或覆盖源视频。

## 用户目标流程

```text
脏下载目录
→ 递归批量扫描
→ FC2 番号规范化
→ 新片源 + 多片源批量刮削
→ 字段级聚合
→ NFO / poster / fanart / extrafanart
→ 批量预览整理
→ 自动建目录 + 改名 + 移动
→ 失败项独立批量补刮
```

## 当前现成软件问题

- `fc2cmadb-crawler`：不是本地媒体整理器。
- `MDCz`：整理链完整，但实测 FC2Hub cooldown，批次 10/10 无元数据。
- `OpenAver`：适合 Fork，但现成工作流不够自动化；若长期跟随上游需持续合并。
- `Amane`：宿主能力最符合；实测番号识别正确，但 10/10 FC2 刮削失败，缺口集中在数据源。
- `MDCx`：已归档，长期维护风险高。
- `Movie Data Capture`：流水线强，但不够 TMM 式。
- `JavLuv`：可识别 FC2，但 FC2 scraper 能力仍不足。

## v1.0 P0 功能

- 批量递归扫描。
- 强 FC2 脏文件名解析。
- 至少 3 个可配置来源；至少 2 个新/替代来源实测可用。
- 字段级多源聚合。
- 全流程批量操作。
- 任务隔离与失败子集重试。
- 批量 NFO / 图片。
- 批量建目录 / 改名 / 移动。
- 来源可插拔。
- 宿主升级解耦。
- 安全失败、无静默覆盖。
- 来源级日志、字段来源追踪。

## 架构

```text
官方 Amane（不修改）
        ↓ Plugin API
amane-fc2-adapter
        ↓ versioned JSON/HTTP
FC2 Metadata Engine
        ↓
Source A / Source B / Source C / FC2 Official ...
```

## 初始来源候选

FC2CMADB、FD2PPV、FC2DB/JavTen、FC2 官方等。具体 P0 来源必须在开工时重新做可访问性与覆盖率探针，不把任何单站作为永久依赖。

## 批量状态

`PENDING → RUNNING → SUCCESS | PARTIAL | FAILED`，失败/部分条目可单独 `RETRY`。

## 默认输出建议

```text
E:\FC2-Library\
  FC2-4825061\
    FC2-4825061.mp4
    FC2-4825061.nfo
    poster.jpg
    fanart.jpg
    thumb.jpg
    extrafanart\
```

## v1.0 关键验收

- 脏文件名回归集解析正确。
- 至少 3 个来源可配置，至少 2 个替代/新来源在用户环境通过。
- 冻结的 50-ID 有效回归集上，至少 90% 获得 `number + title`。
- 500 项批次中注入单源/单项失败，整体任务仍完成。
- Failed/Partial 可单独批量重刮。
- 整理冲突、跨盘、目标不可写等场景不得导致源视频静默丢失。
- Amane 升级在兼容矩阵内无需重新应用主程序 patch。

## 一句话工程任务

在不修改官方 Amane 主程序的前提下，交付一个可批量工作的、多新片源/多片源的 FC2 Metadata Engine，并通过薄 Adapter 接入 Amane，形成从脏目录扫描到 NFO/图片/建目录/改名/移动的完整安全闭环。
