#!/usr/bin/env python3
"""Print resolved asset hub / data / exports paths from tag_cut config."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.config import load_config  # noqa: E402


def _resolve(p: str | None, base: Path) -> str | None:
    if p is None or p == "" or p == "null":
        return None
    path = Path(str(p))
    if not path.is_absolute():
        path = (base / path).resolve()
    else:
        path = path.resolve()
    return str(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    cfg = load_config()
    base = ROOT
    hub = _resolve(cfg.get("asset_hub_root"), base)
    data = _resolve(cfg.get("data_root"), base)
    exports = _resolve(cfg.get("exports_root"), base)
    out = {
        "asset_hub_root": hub,
        "data_root": data,
        "exports_root": exports,
        "hub_aligned": bool(
            hub
            and data
            and exports
            and data.startswith(hub + "/")
            and exports.startswith(hub + "/")
        ),
        "expected_layout": {
            "data": f"{hub}/data" if hub else None,
            "exports": f"{hub}/exports" if hub else None,
            "clips": f"{hub}/clips" if hub else None,
            "contract": f"{hub}/CONTRACT.md" if hub else None,
        },
    }
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        for k, v in out.items():
            if k == "expected_layout":
                print("expected_layout:")
                for sk, sv in (v or {}).items():
                    print(f"  {sk}={sv}")
            else:
                print(f"{k}={v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
