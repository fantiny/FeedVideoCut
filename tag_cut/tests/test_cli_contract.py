"""CLI 契约回归：stdout 恒为单个可解析 JSON、退出码分层、崩溃兜底。"""
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "tag_cut_cli.py"


def _run(*argv: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CLI), *argv],
        capture_output=True, text=True, cwd=str(ROOT),
        env={**os.environ, "PYTHONPATH": str(ROOT)},
    )


def _load_cli_module():
    spec = importlib.util.spec_from_file_location("tag_cut_cli_test", CLI)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_models_list_stdout_is_single_json():
    proc = _run("models", "list")
    assert proc.returncode == 0
    d = json.loads(proc.stdout)  # stdout 必须整体可解析
    assert "models" in d or "active_weights" in d


def test_analyze_bad_batch_exit_2_with_error_json():
    proc = _run("analyze", "--batch", "/nonexistent_dir_xyz")
    assert proc.returncode == 2
    d = json.loads(proc.stdout)
    assert d["ok"] is False
    assert "error" in d


def test_unknown_subcommand_exit_2():
    proc = _run("no-such-cmd")
    assert proc.returncode == 2  # argparse 用法错误


def test_crash_emits_json_stdout(capsys, monkeypatch):
    mod = _load_cli_module()

    def boom(_: object) -> int:
        raise RuntimeError("kaboom")

    monkeypatch.setattr(mod, "cmd_search", boom)
    code = mod.main(["search", "--q", "x"])
    d = json.loads(capsys.readouterr().out)
    assert code == 1
    assert d["ok"] is False and d["code"] == "crash"
    assert "kaboom" in d["error"]
