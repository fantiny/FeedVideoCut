"""Unit tests for config-driven taxonomy."""
from __future__ import annotations

from pathlib import Path

import yaml

from services.taxonomy import (
    Taxonomy,
    clear_taxonomy_cache,
    infer_audio_role,
    infer_audio_texture,
    infer_behaviors,
    load_taxonomy,
)


def test_load_default_taxonomy():
    clear_taxonomy_cache()
    tax = load_taxonomy()
    assert tax.version >= 1
    assert "大特写" in tax.values("shot_scale")
    assert "第一口" in tax.values("behavior")
    assert tax.closeup_scales() == {"大特写", "特写"}
    assert "bottle" in tax.product_like_classes()
    pub = tax.public_dict()
    assert "dimensions" in pub and "enums" in pub
    assert isinstance(pub["featured_label_types"], list)
    assert len(pub["featured_label_types"]) > 0


def test_shot_scale_thresholds():
    tax = load_taxonomy()
    assert tax.shot_scale_from_height(0.7) == "大特写"
    assert tax.shot_scale_from_height(0.45) == "特写"
    assert tax.shot_scale_from_height(0.05) == "全景"


def test_infer_behaviors_from_config():
    tax = load_taxonomy()
    out = infer_behaviors(tax, {
        "audio": ["speech"],
        "duration": 3.0,
        "has_dog": False,
        "has_person": True,
        "has_bowl": False,
        "closeup": False,
    })
    assert any(b["behavior"] == "人物讲解" for b in out)

    chew = infer_behaviors(tax, {
        "audio": ["chew"],
        "duration": 1.0,
        "has_dog": True,
        "has_person": False,
        "has_bowl": True,
        "closeup": True,
    })
    assert any(b["behavior"] == "第一口" for b in chew)


def test_audio_texture_and_role():
    tax = load_taxonomy()
    tex, _ = infer_audio_texture(tax, ["chew"])
    assert tex == "ASMR咀嚼"
    role, _ = infer_audio_role(tax, tex, 1.0)
    assert role == "钩子音效"


def test_extend_values_overlay():
    """Simulate taxonomy.local.yaml extend_values merge."""
    root = Path(__file__).resolve().parents[1]
    default = root / "config" / "taxonomy.yaml"
    base = yaml.safe_load(default.read_text(encoding="utf-8"))
    overlay = {
        "enums": {
            "behavior": {"extend_values": ["单元测试行为"]},
        },
        "extend_behavior_rules": [
            {
                "id": "unit_test_rule",
                "emit": "单元测试行为",
                "confidence": 0.9,
                "when": {"audio_any": ["bark"]},
            }
        ],
    }
    from services.config import _deep_merge

    merged = _deep_merge(base, overlay)
    base_vals = list(((merged.get("enums") or {}).get("behavior") or {}).get("values") or [])
    for v in overlay["enums"]["behavior"]["extend_values"]:
        if v not in base_vals:
            base_vals.append(v)
    merged.setdefault("enums", {}).setdefault("behavior", {})["values"] = base_vals
    merged["behavior_rules"] = list(merged.get("behavior_rules") or []) + list(
        overlay["extend_behavior_rules"]
    )

    tax = Taxonomy(merged)
    assert "单元测试行为" in tax.values("behavior")
    hits = infer_behaviors(tax, {
        "audio": ["bark"],
        "duration": 1.0,
        "has_dog": True,
        "has_person": False,
        "has_bowl": False,
        "closeup": False,
    })
    assert any(b["behavior"] == "单元测试行为" for b in hits)

    clear_taxonomy_cache()
    assert "单元测试行为" not in load_taxonomy().values("behavior")
