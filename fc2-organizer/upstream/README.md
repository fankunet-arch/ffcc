# Upstream Reference

不要把 Amane 源码提交到本目录。

Claude Code / 工程师需要参考时，应在工作机上另行克隆：

```bash
git clone https://github.com/sqzw-x/amane.git upstream/amane
cd upstream/amane
git checkout v0.15.0
```

`upstream/amane/` 已在 `.gitignore` 中排除。

Amane 只能作为只读 reference / compatibility target。
