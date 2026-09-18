#!/usr/bin/env python3
"""
tag_cut CLI — agent-friendly entrypoint for analyze / search / export / models.

Usage (from tag_cut root):
  PYTHONPATH=. python scripts/tag_cut_cli.py <command> ...

Or after skill install, agents resolve TAG_CUT_ROOT and call the same.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _py() -> Path:
    venv = ROOT / ".venv" / "bin" / "python"
    return venv if venv.exists() else Path(sys.executable)


def cmd_env_check(_: argparse.Namespace) -> int:
    from services.yolo_models import probe_environment, list_models_with_status

    issues: list[str] = []
    try:
        import fastapi  # noqa: F401
    except ImportError:
        issues.append("fastapi missing — pip install -r requirements.txt")
    try:
        import ultralytics  # noqa: F401
    except ImportError:
        issues.append("ultralytics missing (optional for L1 YOLO)")

    ffprobe = False
    import shutil
    ffprobe = shutil.which("ffprobe") is not None and shutil.which("ffmpeg") is not None
    if not ffprobe:
        issues.append("ffmpeg/ffprobe not on PATH (brew install ffmpeg)")

    env = probe_environment()
    models = list_models_with_status()
    out = {
        "ok": len(issues) == 0,
        "tag_cut_root": str(ROOT),
        "python": str(_py()),
        "ffmpeg": ffprobe,
        "environment": env,
        "active_weights": models.get("active_weights"),
        "recommended_model": models.get("recommended_id"),
        "issues": issues,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out["ok"] else 1


def cmd_analyze(args: argparse.Namespace) -> int:
    from pipelines.run import run_pipeline
    from pipelines.export_index import export_batch
    from services.config import load_config
    from services.paths import resolve_batch_path

    cfg = load_config(Path(args.config) if args.config else None)
    data_root = (ROOT / cfg["data_root"]).resolve()
    input_root = Path(cfg["input_root"])
    if not input_root.is_absolute():
        input_root = (ROOT / input_root).resolve()
    batch = resolve_batch_path(args.batch, cwd=Path.cwd(), input_root=input_root)
    if batch is None:
        batch = Path(args.batch).expanduser().resolve()
    if not batch.exists():
        print(json.dumps({"ok": False, "error": f"batch not found: {args.batch}"}, ensure_ascii=False))
        return 2

    batch_id = args.batch_id or batch.name
    videos = sorted(batch.rglob("*.mp4"))
    if args.limit:
        videos = videos[: args.limit]
    if not videos:
        print(json.dumps({"ok": False, "error": "no mp4 found"}, ensure_ascii=False))
        return 2

    if args.force:
        dest = data_root / batch_id
        if dest.exists():
            import shutil
            shutil.rmtree(dest)

    results = []
    for video in videos:
        status = run_pipeline(
            video_path=video,
            batch_id=batch_id,
            data_root=data_root,
            layers=args.layers.split(",") if args.layers else None,
        )
        results.append({"video": str(video), "status": status})

    export_path = None
    if not args.no_export:
        out = export_batch(batch_id=batch_id, data_root=data_root)
        export_path = str(out)

    print(json.dumps({
        "ok": True,
        "batch_id": batch_id,
        "videos": len(videos),
        "data_dir": str(data_root / batch_id),
        "export_dir": export_path,
        "results": results,
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    from services.config import load_config
    from services.search import search_labels

    cfg = load_config()
    data_root = (ROOT / cfg["data_root"]).resolve()
    out = search_labels(
        data_root,
        args.q or "",
        batch_id=args.batch_id,
        label_type=args.label_type,
        layer=args.layer,
        limit=args.limit,
    )
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    from pipelines.export_index import export_batch
    from services.config import load_config

    cfg = load_config()
    data_root = (ROOT / cfg["data_root"]).resolve()
    out = export_batch(batch_id=args.batch_id, data_root=data_root)
    print(json.dumps({
        "ok": True,
        "index_json": str(out / "index.json"),
        "index_csv": str(out / "index.csv"),
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_models(args: argparse.Namespace) -> int:
    from services.yolo_models import (
        list_models_with_status,
        download_model,
        set_active_model,
        probe_environment,
        ensure_recommended_downloaded,
    )

    if args.models_cmd == "list":
        print(json.dumps(list_models_with_status(), ensure_ascii=False, indent=2))
        return 0
    if args.models_cmd == "probe":
        print(json.dumps(probe_environment(), ensure_ascii=False, indent=2))
        return 0
    if args.models_cmd == "ensure":
        print(json.dumps(ensure_recommended_downloaded(), ensure_ascii=False, indent=2))
        return 0
    if args.models_cmd == "download":
        if not args.model_id:
            print(json.dumps({"ok": False, "error": "--model-id required"}, ensure_ascii=False))
            return 2
        print(json.dumps(download_model(args.model_id, force=args.force), ensure_ascii=False, indent=2))
        return 0
    if args.models_cmd == "activate":
        if not args.model_id:
            print(json.dumps({"ok": False, "error": "--model-id required"}, ensure_ascii=False))
            return 2
        print(json.dumps({"ok": True, **set_active_model(args.model_id)}, ensure_ascii=False, indent=2))
        return 0
    print(json.dumps({"ok": False, "error": f"unknown models subcommand: {args.models_cmd}"}, ensure_ascii=False))
    return 2


def cmd_serve(args: argparse.Namespace) -> int:
    import subprocess
    py = str(_py())
    cmd = [
        py, "-m", "uvicorn", "services.app:app",
        "--host", args.host, "--port", str(args.port),
    ]
    if args.reload:
        cmd.append("--reload")
    print(json.dumps({"ok": True, "cmd": cmd, "cwd": str(ROOT)}, ensure_ascii=False))
    return subprocess.call(cmd, cwd=str(ROOT), env={**dict(**{k: v for k, v in __import__("os").environ.items()}), "PYTHONPATH": str(ROOT)})


def cmd_clone(args: argparse.Namespace) -> int:
    """复用已有批次创建新批次：索引直接拷贝，关键帧硬链接（零额外空间），
    已用次数归零 —— 新旧批次后续业务（用次统计/内容/生成）完全独立。"""
    import shutil
    import subprocess
    from datetime import datetime
    from services.config import load_config

    cfg = load_config(Path(args.config) if args.config else None)
    data_root = (ROOT / cfg["data_root"]).resolve()
    exports_root = data_root.parent / "exports"

    src_exports = exports_root / args.batch
    src_index = src_exports / "index.json"
    if not src_index.exists():
        print(json.dumps({"ok": False,
                          "error": f"源批次不存在或未打标：{args.batch}"}, ensure_ascii=False))
        return 2
    new_id = args.new or f"{args.batch}-复用-{datetime.now():%Y%m%d}"
    dst_exports = exports_root / new_id
    if dst_exports.exists():
        print(json.dumps({"ok": False,
                          "error": f"目标批次已存在：{new_id}"}, ensure_ascii=False))
        return 2

    # 1) 索引（exports/）：小文件，直接拷贝
    shutil.copytree(src_exports, dst_exports)
    # 2) 关键帧与打标数据（data/）：硬链接拷贝（同卷零空间，删除互不影响）
    src_data = data_root / args.batch
    dst_data = data_root / new_id
    linked = False
    if src_data.exists():
        proc = subprocess.run(["cp", "-R", "-l", str(src_data), str(dst_data)],
                              capture_output=True, text=True)
        if proc.returncode == 0:
            linked = True
        else:   # 文件系统不支持硬链接时回退为完整拷贝
            shutil.copytree(src_data, dst_data)
    # 3) 新索引：关键帧路径改指向新批次 data 目录，已用次数归零
    rows = json.loads((dst_exports / "index.json").read_text(encoding="utf-8"))
    for row in rows:
        kf = row.get("keyframe_mid")
        if isinstance(kf, str) and f"/{args.batch}/" in kf:
            row["keyframe_mid"] = kf.replace(f"/{args.batch}/", f"/{new_id}/", 1)
        if "已用次数" in row:
            row["已用次数"] = 0
    (dst_exports / "index.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    csv_path = dst_exports / "index.csv"
    if csv_path.exists():   # CSV 同步换路径与清零用次
        text = csv_path.read_text(encoding="utf-8")
        head, *lines = text.splitlines()
        out_lines = [head]
        for ln in lines:
            ln = ln.replace(f"/{args.batch}/", f"/{new_id}/")
            cells = ln.split(",")
            if len(cells) > 3 and cells[-1].strip().isdigit():
                cells[-1] = "0"
            out_lines.append(",".join(cells))
        csv_path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")

    print(json.dumps({
        "ok": True, "batch_id": new_id, "reused_from": args.batch,
        "shots": len(rows), "keyframes_hardlinked": linked,
        "independent": True,
        "note": "新批次已用次数归零；源视频文件为共享只读，两批次业务互不影响",
    }, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tag_cut_cli", description="tag_cut agent CLI")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("env-check", help="Check local deps + YOLO env")
    s.set_defaults(func=cmd_env_check)

    s = sub.add_parser("analyze", help="Run multilayer tagging on a batch")
    s.add_argument("--batch", required=True, help="Input directory with mp4 files")
    s.add_argument("--batch-id", default=None, help="Output subdirectory under data/")
    s.add_argument("--limit", type=int, default=None)
    s.add_argument("--force", action="store_true", help="Wipe data/<batch_id> then re-run")
    s.add_argument("--layers", default=None, help="Comma list e.g. l0,split,l1,l2,l3_l6")
    s.add_argument("--no-export", action="store_true")
    s.add_argument("--config", default=None)
    s.set_defaults(func=cmd_analyze)

    s = sub.add_parser("search", help="Search shots by tag text")
    s.add_argument("--q", default="", help="Keyword e.g. 自然 / 第一口 / 种草")
    s.add_argument("--batch-id", default=None)
    s.add_argument("--label-type", default=None)
    s.add_argument("--layer", default=None)
    s.add_argument("--limit", type=int, default=50)
    s.set_defaults(func=cmd_search)

    s = sub.add_parser("clone", help="复用已有批次创建新批次（资源复用，业务独立）")
    s.add_argument("--batch", required=True, help="源批次 ID（已打标）")
    s.add_argument("--new", default=None, help="新批次 ID（默认 <源>-复用-YYYYMMDD）")
    s.add_argument("--config", default=None)
    s.set_defaults(func=cmd_clone)

    s = sub.add_parser("export", help="Export index.json/csv for a batch")
    s.add_argument("--batch-id", required=True)
    s.set_defaults(func=cmd_export)

    s = sub.add_parser("models", help="YOLO model catalog / download / activate")
    s.add_argument("models_cmd", choices=["list", "probe", "ensure", "download", "activate"])
    s.add_argument("--model-id", default=None)
    s.add_argument("--force", action="store_true")
    s.set_defaults(func=cmd_models)

    s = sub.add_parser("serve", help="Start FastAPI on 8765 (blocks)")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8765)
    s.add_argument("--reload", action="store_true")
    s.set_defaults(func=cmd_serve)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
