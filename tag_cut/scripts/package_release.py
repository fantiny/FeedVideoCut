#!/usr/bin/env python3
"""
Build a portable source zip for installing tag_cut on another machine.

Usage (from tag_cut root):
  python scripts/package_release.py
  python scripts/package_release.py --out /path/to/dir
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKTREE = ROOT.parent  # .worktrees/tag-cut


EXCLUDE_DIR_NAMES = {
    ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache",
    ".git", "data", "exports", "dist", "out", ".DS_Store",
}
EXCLUDE_FILE_SUFFIXES = {".pyc", ".pyo", ".pt", ".part"}
EXCLUDE_FILE_NAMES = {".DS_Store", "local.yaml", ".env"}


def should_skip(path: Path, root: Path) -> bool:
    rel = path.relative_to(root)
    parts = set(rel.parts)
    if parts & EXCLUDE_DIR_NAMES:
        return True
    if path.name in EXCLUDE_FILE_NAMES:
        return True
    if path.suffix in EXCLUDE_FILE_SUFFIXES:
        return True
    # keep models/.gitkeep only
    if "models" in rel.parts and path.is_file() and path.name != ".gitkeep":
        return True
    return False


def copy_tree(src: Path, dst: Path) -> int:
    n = 0
    for item in src.rglob("*"):
        if should_skip(item, src):
            continue
        if item.is_dir():
            continue
        if item.is_symlink():
            continue
        rel = item.relative_to(src)
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, target)
        n += 1
    return n


def build(out_dir: Path) -> Path:
    version = dt.datetime.now().strftime("%Y%m%d")
    name = f"tag_cut-{version}"
    staging = out_dir / f".staging-{name}"
    if staging.exists():
        shutil.rmtree(staging)
    pkg_root = staging / name
    tag_dst = pkg_root / "tag_cut"
    input_dst = pkg_root / "input"

    tag_dst.mkdir(parents=True)
    input_dst.mkdir(parents=True)

    n_files = copy_tree(ROOT, tag_dst)

    # Ensure empty runtime dirs exist in package
    for d in ("data", "exports", "models"):
        (tag_dst / d).mkdir(exist_ok=True)
    (tag_dst / "models" / ".gitkeep").write_text("")

    # input placeholder
    input_readme = ROOT / "docs" / "input_README.md"
    if input_readme.exists():
        shutil.copy2(input_readme, input_dst / "README.md")
    else:
        (input_dst / "README.md").write_text("# Put mp4 batches here\n")

    # Root INSTALL.md
    install_src = ROOT / "docs" / "INSTALL.md"
    shutil.copy2(install_src, pkg_root / "INSTALL.md")

    # Design plans (from worktree docs if present)
    plans_src = WORKTREE / "docs" / "plans"
    if plans_src.is_dir():
        plans_dst = pkg_root / "docs" / "plans"
        plans_dst.mkdir(parents=True, exist_ok=True)
        for f in plans_src.glob("*.md"):
            shutil.copy2(f, plans_dst / f.name)

    # Also mirror plans into tag_cut/docs/plans for in-app docs
    if plans_src.is_dir():
        plans_dst2 = tag_dst / "docs" / "plans"
        plans_dst2.mkdir(parents=True, exist_ok=True)
        for f in plans_src.glob("*.md"):
            shutil.copy2(f, plans_dst2 / f.name)

    # Manifest
    manifest = {
        "name": "tag_cut",
        "version": version,
        "built_at": dt.datetime.now().isoformat(timespec="seconds"),
        "python_requires": ">=3.11",
        "layout": {
            "engine": "tag_cut/",
            "input": "input/",
            "install_doc": "INSTALL.md",
        },
        "excluded": sorted(EXCLUDE_DIR_NAMES) + sorted(EXCLUDE_FILE_SUFFIXES),
        "file_count": n_files,
        "bootstrap": "cd tag_cut && ./scripts/bootstrap.sh",
    }
    (pkg_root / "MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    # Sanity: required files
    required = [
        tag_dst / "requirements.txt",
        tag_dst / "scripts" / "tag_cut_cli.py",
        tag_dst / "scripts" / "install_agent_skill.py",
        tag_dst / "scripts" / "bootstrap.sh",
        tag_dst / "docs" / "INSTALL.md",
        tag_dst / "docs" / "AGENT_INSTALL.md",
        tag_dst / "agent_skill" / "tag-cut" / "SKILL.md",
        tag_dst / "services" / "app.py",
        tag_dst / "config" / "default.yaml",
        pkg_root / "INSTALL.md",
        input_dst / "README.md",
    ]
    missing = [str(p.relative_to(pkg_root)) for p in required if not p.exists()]
    if missing:
        raise SystemExit(f"package missing required files: {missing}")

    # Forbid accidental absolutes / secrets / machine paths
    # Build needles without embedding full literals in this file (self-scan safe).
    leak_needles = ("/" + "Volumes/", "/" + "Users/", "C:\\" + "Users\\")
    skip_leak_scan = {"package_release.py"}
    for p in tag_dst.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() in {".pt", ".mp4", ".mov"}:
            raise SystemExit(f"refusing to package binary media/weights: {p}")
        if p.name == "local.yaml":
            raise SystemExit(f"refusing to package local config: {p}")
        if p.name in skip_leak_scan:
            continue
        if p.suffix.lower() in {".md", ".py", ".yaml", ".yml", ".txt", ".json", ".ts", ".tsx", ".js", ".cjs"}:
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for needle in leak_needles:
                if needle in text:
                    raise SystemExit(f"machine path leak {needle!r} in {p.relative_to(pkg_root)}")

    zip_path = out_dir / f"{name}.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for f in pkg_root.rglob("*"):
            if f.is_file():
                zf.write(f, arcname=str(f.relative_to(staging)))

    shutil.rmtree(staging)
    return zip_path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--out",
        default=str(WORKTREE / "dist"),
        help="Output directory for the zip",
    )
    args = ap.parse_args()
    out_dir = Path(args.out).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = build(out_dir)
    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(json.dumps({
        "ok": True,
        "zip": str(zip_path),
        "size_mb": round(size_mb, 2),
        "hint": f"unzip and read INSTALL.md; then: cd tag_cut && ./scripts/bootstrap.sh",
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
