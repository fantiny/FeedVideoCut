"""
Configurable taxonomy loader.

Source of truth: config/taxonomy.yaml
Optional overlay: config/taxonomy.local.yaml (business extensions, gitignored)

Pipelines/UI/export should read vocab via this module — not hardcode lists.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from services.config import _deep_merge  # reuse merge helper

_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT = _ROOT / "config" / "taxonomy.yaml"
_LOCAL = _ROOT / "config" / "taxonomy.local.yaml"


def _load_raw(path: Path | None = None) -> dict[str, Any]:
    src = path or _DEFAULT
    if not src.exists():
        raise FileNotFoundError(f"taxonomy not found: {src}")
    data = yaml.safe_load(src.read_text(encoding="utf-8")) or {}
    if path is None and _LOCAL.exists():
        overlay = yaml.safe_load(_LOCAL.read_text(encoding="utf-8")) or {}
        # enums / dimensions: deep-merge; list fields in overlay replace unless
        # using special extend keys handled below
        data = _deep_merge(data, overlay)
        # Allow taxonomy.local.yaml to *append* enum values:
        # enums.<name>.extend_values: [...]
        for name, spec in (overlay.get("enums") or {}).items():
            if isinstance(spec, dict) and "extend_values" in spec:
                base = list(((data.get("enums") or {}).get(name) or {}).get("values") or [])
                for v in spec["extend_values"]:
                    if v not in base:
                        base.append(v)
                data.setdefault("enums", {}).setdefault(name, {})["values"] = base
        if "extend_behavior_rules" in overlay:
            data.setdefault("behavior_rules", [])
            data["behavior_rules"] = list(data["behavior_rules"]) + list(
                overlay["extend_behavior_rules"]
            )
    return data


@lru_cache(maxsize=4)
def load_taxonomy(path: str | None = None) -> "Taxonomy":
    raw = _load_raw(Path(path) if path else None)
    return Taxonomy(raw)


def clear_taxonomy_cache() -> None:
    load_taxonomy.cache_clear()


class Taxonomy:
    def __init__(self, raw: dict[str, Any]):
        self.raw = raw
        self.version = raw.get("version", 1)
        self.dimensions: list[dict[str, Any]] = list(raw.get("dimensions") or [])
        self.enums: dict[str, dict[str, Any]] = dict(raw.get("enums") or {})
        self.vision: dict[str, Any] = dict(raw.get("vision") or {})
        self.behavior_rules: list[dict[str, Any]] = list(raw.get("behavior_rules") or [])
        self.audio_texture_rules: list[dict[str, Any]] = list(raw.get("audio_texture_rules") or [])
        self.audio_role_rules: list[dict[str, Any]] = list(raw.get("audio_role_rules") or [])
        self.search: dict[str, Any] = dict(raw.get("search") or {})
        self.ui: dict[str, Any] = dict(raw.get("ui") or {})
        self.export: dict[str, Any] = dict(raw.get("export") or {})

    def values(self, enum_name: str) -> list[str]:
        spec = self.enums.get(enum_name) or {}
        return list(spec.get("values") or [])

    def unknown(self, enum_name: str, default: str = "未知") -> str:
        spec = self.enums.get(enum_name) or {}
        return str(spec.get("unknown") or default)

    def default(self, enum_name: str, fallback: str = "") -> str:
        spec = self.enums.get(enum_name) or {}
        return str(spec.get("default") or fallback)

    def allowed(self, enum_name: str, value: Any) -> bool:
        vals = self.values(enum_name)
        if not vals:
            return True
        return value in vals

    def normalize(self, enum_name: str, value: Any) -> Any:
        if value is None:
            return self.unknown(enum_name)
        if self.allowed(enum_name, value):
            return value
        return self.unknown(enum_name)

    def dim_by_label_type(self, label_type: str) -> dict[str, Any] | None:
        for d in self.dimensions:
            if d.get("label_type") == label_type:
                return d
        return None

    def featured_label_types(self) -> list[str]:
        explicit = list(self.ui.get("featured_label_types") or [])
        if explicit:
            return explicit
        return [
            str(d["label_type"])
            for d in self.dimensions
            if d.get("ui_featured") and d.get("label_type")
        ]

    def skip_match_types(self) -> set[str]:
        return set(self.search.get("skip_match_types") or [])

    def export_columns(self) -> list[str]:
        return list(self.export.get("columns") or [])

    def closeup_scales(self) -> set[str]:
        return set(self.vision.get("closeup_scales") or ["大特写", "特写"])

    def product_like_classes(self) -> set[str]:
        return set(self.vision.get("product_like_classes") or [])

    def shot_scale_from_height(self, norm_h: float) -> str:
        spec = self.enums.get("shot_scale") or {}
        thresholds = sorted(
            list(spec.get("thresholds") or []),
            key=lambda t: float(t.get("min_height", 0)),
            reverse=True,
        )
        for t in thresholds:
            mh = float(t.get("min_height", 0))
            label = str(t.get("label") or self.unknown("shot_scale"))
            if mh <= 0:
                return label
            if norm_h > mh:
                return label
        return self.unknown("shot_scale")

    def public_dict(self) -> dict[str, Any]:
        """Payload for GET /taxonomy (UI / agents)."""
        return {
            "version": self.version,
            "dimensions": self.dimensions,
            "enums": {
                k: {"values": v.get("values"), "unknown": v.get("unknown"), "default": v.get("default")}
                for k, v in self.enums.items()
            },
            "featured_label_types": self.featured_label_types(),
            "export_columns": self.export_columns(),
            "behavior_rule_ids": [r.get("id") for r in self.behavior_rules],
        }


# ---------------------------------------------------------------------------
# Rule evaluators (L2)
# ---------------------------------------------------------------------------

def _ctx_match(when: dict[str, Any], ctx: dict[str, Any]) -> bool:
    if not when:
        return True
    audio = set(ctx.get("audio") or [])
    if "audio_any" in when and not audio.intersection(when["audio_any"] or []):
        return False
    if "audio_none" in when and audio.intersection(when["audio_none"] or []):
        return False
    for flag in ("has_dog", "has_person", "has_bowl", "closeup"):
        if flag in when and bool(ctx.get(flag)) != bool(when[flag]):
            return False
    dur = float(ctx.get("duration") or 0)
    if "duration_lt" in when and not (dur < float(when["duration_lt"])):
        return False
    if "duration_lte" in when and not (dur <= float(when["duration_lte"])):
        return False
    if "duration_gt" in when and not (dur > float(when["duration_gt"])):
        return False
    if "duration_gte" in when and not (dur >= float(when["duration_gte"])):
        return False
    if "texture" in when and ctx.get("texture") != when["texture"]:
        return False
    if "texture_any" in when and ctx.get("texture") not in (when["texture_any"] or []):
        return False
    return True


def infer_behaviors(tax: Taxonomy, ctx: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Evaluate declarative behavior_rules.
    Non-fallback rules run first; fallback_only rules run only if nothing emitted.
    """
    allowed = set(tax.values("behavior"))
    primary: list[dict[str, Any]] = []
    fallback: list[dict[str, Any]] = []

    for rule in tax.behavior_rules:
        when_full = dict(rule.get("when") or {})
        is_fb = bool(when_full.pop("fallback_only", False))
        if not _ctx_match(when_full, ctx):
            continue
        emit = rule.get("emit")
        if allowed and emit not in allowed:
            continue
        item = {"behavior": emit, "confidence": float(rule.get("confidence", 0.5))}
        (fallback if is_fb else primary).append(item)

    chosen = primary if primary else fallback
    best: dict[str, dict] = {}
    for b in chosen:
        name = b["behavior"]
        if name not in best or b["confidence"] > best[name]["confidence"]:
            best[name] = b
    return list(best.values())


def infer_audio_texture(tax: Taxonomy, audio_events: list[str]) -> tuple[str, float]:
    audio = set(audio_events)
    for rule in tax.audio_texture_rules:
        if audio.intersection(rule.get("audio_any") or []):
            emit = rule.get("emit")
            if tax.values("audio_texture") and emit not in tax.values("audio_texture"):
                continue
            return str(emit), float(rule.get("confidence", 0.5))
    return tax.unknown("audio_texture"), 0.2


def infer_audio_role(tax: Taxonomy, texture: str, duration: float) -> tuple[str, float]:
    ctx = {"texture": texture, "duration": duration}
    for rule in tax.audio_role_rules:
        when = {k: v for k, v in rule.items() if k not in ("emit", "confidence")}
        if _ctx_match(when, ctx):
            emit = rule.get("emit")
            if tax.values("audio_role") and emit not in tax.values("audio_role"):
                continue
            return str(emit), float(rule.get("confidence", 0.5))
    return tax.unknown("audio_role"), 0.2
