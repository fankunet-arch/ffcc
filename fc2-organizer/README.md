# FC2 Organizer

基于现有开源媒体管理器构建的 FC2 批量刮削与整理扩展项目。

## 项目目标

- 保持 Amane 官方主程序不修改；
- 通过独立 Adapter / Plugin 接入；
- 使用当前可用的新 FC2 数据源，并支持多源聚合；
- 支持批量扫描、批量刮削、失败重试、NFO / 图片生成以及批量整理；
- 将站点 scraper、metadata core 与宿主适配层解耦，降低 Amane 升级影响。

## 正式规格

唯一正式规格真相源：

`docs/specifications/FC2_Organizer_v1.0_开发规格书.md`

## Claude Code 执行

实施者首先阅读：

1. `CLAUDE.md`
2. `docs/specifications/FC2_Organizer_v1.0_开发规格书.md`
3. `docs/prompts/ClaudeCode_00_实施总提示词.md`

第一轮只允许执行 **Phase 0**。

独立复查者使用：

`docs/prompts/ClaudeCode_10_独立复查提示词模板.md`

最终发布验收使用：

`docs/prompts/ClaudeCode_20_最终验收提示词.md`

## 上游 Amane

正式兼容基线：

- Repository: `https://github.com/sqzw-x/amane.git`
- Baseline tag: `v0.15.0`

上游源码不得直接提交进本仓库，也不得修改后混入本项目历史。
