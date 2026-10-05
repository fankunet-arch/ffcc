"""P5-C2（合同第 11.1 / 11.4 节）：准备真实 Amane 见证宿主（源码宿主 venv + 官方冻结桌面包）。

只使用标准库。联网仅限：``git``（读取 upstream 标签）、``pip``（安装该 Amane 检出的依赖，属环境前提）、
GitHub Release 资产下载（下载后以 Release 元数据里的 SHA-256 摘要校验）。**不触碰**任何用户的 Amane 实例 / 数据目录：
所有产物都在 ``--work`` 之下。``pip`` 只用于准备宿主 venv，**不是** locator 的 Core 信任来源。

用法::

    python tools/prepare_amane_hosts.py --work <dir> --python <py3.14> --amane-repo <local clone> --tags v0.15.0 v0.18.0 --out <hosts.json>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

REPO_URL = "https://github.com/sqzw-x/amane.git"
RELEASE_API = "https://api.github.com/repos/sqzw-x/amane/releases/tags/{tag}"
ASSET_TEMPLATE = "Amane-{tag}-windows-x64.zip"
FROZEN_EXE = Path("Amane") / "onedir" / "Amane.Server.exe"


def _run(command: list[str], *, cwd: Path | None = None) -> str:
    completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"{' '.join(command[:4])} failed ({completed.returncode}): {completed.stderr[-800:]}")
    return completed.stdout.strip()


def _git(repo: Path, *args: str) -> str:
    return _run(["git", "-C", str(repo), *args])


def ensure_checkout(repo: Path, work: Path, tag: str) -> dict[str, str]:
    """``<work>/amane-<tag>``：detached worktree，必须等于标签的 peeled commit 且干净。"""
    target = work / f"amane-{tag}"
    if not target.exists():
        _git(repo, "worktree", "add", "--detach", str(target), tag)
    peeled = _git(repo, "rev-parse", f"{tag}^{{commit}}")
    if _git(target, "rev-parse", "HEAD") != peeled:
        raise RuntimeError(f"{tag}: checkout is not at the peeled commit")
    if _git(target, "status", "--porcelain"):
        raise RuntimeError(f"{tag}: checkout is not clean")
    return {"tag": tag, "tag_object": _git(repo, "rev-parse", tag), "peeled_commit": peeled, "source_dir": str(target)}


def ensure_venv(python: str, source: Path, work: Path, tag: str) -> dict[str, str]:
    venv = work / f"venv-{tag}"
    interpreter = venv / "Scripts" / "python.exe"
    if not interpreter.exists():
        _run([python, "-m", "venv", str(venv)])
    _run([str(interpreter), "-m", "pip", "install", "--disable-pip-version-check", "-q", "-e", str(source)])
    frozen = _run([str(interpreter), "-m", "pip", "freeze", "--exclude-editable", "--disable-pip-version-check"])
    lines = sorted(line.strip() for line in frozen.splitlines() if line.strip())
    version = _run([str(interpreter), "-c", "import sys;print('.'.join(map(str, sys.version_info[:3])))"])
    return {
        "venv_python": str(interpreter),
        "python_version": version,
        "deps_lock_sha256": hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest(),
        "deps_count": str(len(lines)),
    }


def fetch_release_asset(tag: str, work: Path) -> dict[str, str]:
    """下载官方 Windows x64 冻结包，以 Release 元数据的 SHA-256 摘要校验后解压到 ``<work>/frozen-<tag>/``。"""
    name = ASSET_TEMPLATE.format(tag=tag)
    request = urllib.request.Request(RELEASE_API.format(tag=tag), headers={"User-Agent": "ffcc-prepare-hosts", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310 - 固定的 https GitHub API
        release = json.loads(response.read().decode("utf-8"))
    if release.get("draft") or release.get("prerelease"):
        raise RuntimeError(f"{tag}: release is a draft or prerelease")
    asset = next(item for item in release["assets"] if item["name"] == name)
    digest = str(asset.get("digest", ""))
    if not digest.startswith("sha256:"):
        raise RuntimeError(f"{tag}: release metadata has no sha256 digest for {name}")
    expected = digest.split(":", 1)[1]
    downloads = work / "downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    archive_path = downloads / name
    if not archive_path.exists() or hashlib.sha256(archive_path.read_bytes()).hexdigest() != expected:
        request = urllib.request.Request(asset["browser_download_url"], headers={"User-Agent": "ffcc-prepare-hosts"})
        with urllib.request.urlopen(request, timeout=600) as response, archive_path.open("wb") as handle:  # noqa: S310
            while block := response.read(1 << 20):
                handle.write(block)
    actual = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    if actual != expected:
        raise RuntimeError(f"{name}: sha256 {actual} does not match the release digest {expected}")
    target = work / f"frozen-{tag}"
    if not (target / FROZEN_EXE).exists():
        with zipfile.ZipFile(archive_path) as archive:
            archive.extractall(target)
    if not (target / FROZEN_EXE).exists():
        raise RuntimeError(f"{name}: {FROZEN_EXE} not found after extraction")
    return {"frozen_dir": str(target), "frozen_exe": str(target / FROZEN_EXE), "frozen_asset_sha256": actual, "frozen_asset_name": name}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--python", required=True, help="Python 3.14.x 解释器（用于创建宿主 venv）")
    parser.add_argument("--amane-repo", type=Path, help="本地 upstream 克隆；缺省时克隆到 <work>/amane")
    parser.add_argument("--tags", nargs="+", required=True)
    parser.add_argument("--skip-frozen", action="store_true")
    parser.add_argument("--skip-venv", action="store_true")
    parser.add_argument("--out", required=True, type=Path)
    options = parser.parse_args(argv)
    work = options.work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    repo = (options.amane_repo or work / "amane").resolve()
    if not repo.exists():
        _run(["git", "clone", "-q", REPO_URL, str(repo)])
    _git(repo, "fetch", "-q", "--tags", "origin")
    report: dict[str, dict[str, str]] = {}
    for tag in options.tags:
        entry = ensure_checkout(repo, work, tag)
        if not options.skip_venv:
            entry.update(ensure_venv(options.python, Path(entry["source_dir"]), work, tag))
        if not options.skip_frozen:
            entry.update(fetch_release_asset(tag, work))
        report[tag] = entry
        print(f"{tag}: prepared", file=sys.stderr)
    options.out.parent.mkdir(parents=True, exist_ok=True)
    options.out.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
