"""clone 命令测试：批次复用（索引拷贝 + 关键帧硬链接 + 用次归零）。

合成批次构造，不依赖真实素材与模型。
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "tag_cut_cli.py"


def _mk_batch(root: Path, batch: str, used: int = 3):
    """在 root/data（exports 为其同级目录）下造一个已打标批次。"""
    data = root / "data" / batch / "kfs"
    data.mkdir(parents=True)
    kf = data / "shotA.jpg"
    kf.write_bytes(b"\xff\xd8fake")
    exports = root / "exports" / batch
    exports.mkdir(parents=True)
    rows = [{"编号": "shotA", "是否有字幕": "否",
             "keyframe_mid": str(kf), "已用次数": used}]
    (exports / "index.json").write_text(
        json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    (exports / "index.csv").write_text(
        "编号,是否有字幕,keyframe_mid,已用次数\nshotA,否," + str(kf) + f",{used}\n",
        encoding="utf-8")
    return exports


def _run(root: Path, *args: str) -> tuple[int, dict]:
    cfg = root / "config.yaml"
    cfg.write_text(f"data_root: {root / 'data'}\n", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(CLI), "clone", "--config", str(cfg), *args],
        capture_output=True, text=True, cwd=str(ROOT))
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        payload = {"raw": proc.stdout[-300:]}
    return proc.returncode, payload


def test_clone_creates_independent_batch(tmp_path):
    _mk_batch(tmp_path, "src_batch", used=5)
    code, out = _run(tmp_path, "--batch", "src_batch", "--new", "new_batch")
    assert code == 0 and out.get("ok") is True
    assert out["batch_id"] == "new_batch" and out["reused_from"] == "src_batch"
    assert out["independent"] is True and out["shots"] == 1

    rows = json.loads((tmp_path / "exports" / "new_batch" / "index.json")
                      .read_text(encoding="utf-8"))
    assert rows[0]["已用次数"] == 0                      # 用次归零
    assert "/new_batch/" in rows[0]["keyframe_mid"]      # 关键帧路径指向新批次
    assert rows[0]["keyframe_mid"] != str(tmp_path / "data" / "src_batch")
    csv_text = (tmp_path / "exports" / "new_batch" / "index.csv").read_text(encoding="utf-8")
    assert "new_batch" in csv_text and csv_text.rstrip().endswith(",0")

    # 源批次不受影响（用次保持、索引仍在）
    src_rows = json.loads((tmp_path / "exports" / "src_batch" / "index.json")
                          .read_text(encoding="utf-8"))
    assert src_rows[0]["已用次数"] == 5


def test_clone_rejects_missing_source(tmp_path):
    code, out = _run(tmp_path, "--batch", "nope", "--new", "x")
    assert code == 2 and out.get("ok") is False
    assert "源批次不存在" in out.get("error", "")


def test_clone_rejects_existing_target(tmp_path):
    _mk_batch(tmp_path, "src_batch")
    _mk_batch(tmp_path, "taken")
    code, out = _run(tmp_path, "--batch", "src_batch", "--new", "taken")
    assert code == 2 and "目标批次已存在" in out.get("error", "")
