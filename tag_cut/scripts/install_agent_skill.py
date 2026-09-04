#!/usr/bin/env python3
"""
Install the tag-cut agent skill into Cursor / Claude Code / Codex skill dirs.

Agent-readable: run this when the user asks to install tag_cut into their agent.

Examples:
  python scripts/install_agent_skill.py --targets all
  python scripts/install_agent_skill.py --targets cursor,claude,codex
  python scripts/install_agent_skill.py --targets cursor --force
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL_SRC = ROOT / "agent_skill" / "tag-cut"
SKILL_NAME = "tag-cut"


def target_dirs() -> dict[str, Path]:
    home = Path.home()
    codex_home = Path(os.environ.get("CODEX_HOME") or (home / ".codex"))
    return {
        "cursor": home / ".cursor" / "skills" / SKILL_NAME,
        "claude": home / ".claude" / "skills" / SKILL_NAME,
        "codex": codex_home / "skills" / SKILL_NAME,
        # Optional: project-local Cursor skill (only if --project-skill)
    }


def write_root_pointer(dest: Path) -> None:
    """Embed absolute TAG_CUT_ROOT so the skill works from any cwd."""
    pointer = dest / "TAG_CUT_ROOT"
    pointer.write_text(str(ROOT) + "\n", encoding="utf-8")
    # Also patch a small local env file agents can source mentally
    (dest / "env.json").write_text(
        json.dumps({
            "TAG_CUT_ROOT": str(ROOT),
            "CLI": str(ROOT / "scripts" / "tag_cut_cli.py"),
            "PYTHON": str(ROOT / ".venv" / "bin" / "python")
            if (ROOT / ".venv" / "bin" / "python").exists()
            else sys.executable,
            "PYTHONPATH": str(ROOT),
        }, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )


def install_one(dest: Path, force: bool) -> dict:
    if not SKILL_SRC.is_dir() or not (SKILL_SRC / "SKILL.md").exists():
        return {"ok": False, "dest": str(dest), "error": f"skill source missing: {SKILL_SRC}"}

    if dest.exists():
        if not force:
            return {"ok": False, "dest": str(dest), "error": "already exists (pass --force)"}
        shutil.rmtree(dest)

    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SKILL_SRC, dest)
    write_root_pointer(dest)
    return {"ok": True, "dest": str(dest), "skill": SKILL_NAME}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Install tag-cut skill for Cursor/Claude/Codex")
    p.add_argument(
        "--targets",
        default="all",
        help="Comma list: cursor,claude,codex or 'all'",
    )
    p.add_argument("--force", action="store_true", help="Overwrite existing skill dirs")
    p.add_argument(
        "--project-skill",
        action="store_true",
        help="Also install into <repo>/.cursor/skills/tag-cut",
    )
    args = p.parse_args(argv)

    names = [t.strip().lower() for t in args.targets.split(",") if t.strip()]
    if names == ["all"]:
        names = ["cursor", "claude", "codex"]

    mapping = target_dirs()
    results = []
    for name in names:
        if name not in mapping:
            results.append({"ok": False, "target": name, "error": "unknown target"})
            continue
        r = install_one(mapping[name], force=args.force)
        r["target"] = name
        results.append(r)

    if args.project_skill:
        # Prefer monorepo .cursor if present, else tag_cut/.cursor
        candidates = [
            ROOT.parent.parent / ".cursor" / "skills" / SKILL_NAME,  # pet_cut_tag
            ROOT / ".cursor" / "skills" / SKILL_NAME,
        ]
        # worktree: .worktrees/tag-cut → repo root may be parents[2]
        for c in list(ROOT.parents)[:4]:
            candidates.append(c / ".cursor" / "skills" / SKILL_NAME)
        dest = candidates[0]
        for c in candidates:
            if (c.parent.parent / "AGENTS.md").exists() or (c.parent.parent / ".git").exists():
                dest = c
                break
        r = install_one(dest, force=args.force)
        r["target"] = "project"
        results.append(r)

    ok = all(r.get("ok") for r in results)
    print(json.dumps({
        "ok": ok,
        "tag_cut_root": str(ROOT),
        "installed": results,
        "next": "Restart / start a new agent turn so the skill is discovered. Then say: 用 tag-cut 分析某某视频批次",
    }, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
