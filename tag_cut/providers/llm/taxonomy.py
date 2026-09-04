"""
Back-compat facade over config/taxonomy.yaml via services.taxonomy.

Prefer: `from services.taxonomy import load_taxonomy`
"""
from __future__ import annotations

from services.taxonomy import load_taxonomy


def _vals(name: str) -> list[str]:
    return load_taxonomy().values(name)


def _dims() -> list[str]:
    return [
        str(d.get("label_type"))
        for d in load_taxonomy().dimensions
        if d.get("label_type")
    ]


# Lazy module attributes — resolve on access so taxonomy.local.yaml overlays apply.
def __getattr__(name: str):
    mapping = {
        "INDEX_DIMENSIONS": lambda: _dims() or [
            "shot_scale", "camera_move", "duration", "dog_breed", "fur_color",
            "has_person", "has_logo", "lighting", "auth_status", "valid_until",
            "emotion", "applicable_types", "quality_grade",
        ],
        "L1_FLAGS": lambda: [
            "has_person", "has_dog", "has_product", "has_bowl", "has_logo",
            "subject_layout", "subject_count", "lighting_metrics",
        ],
        "SUBJECT_TYPES": lambda: [
            "subject_type", "subject_count", "subject_layout", "subject_id", "subject_role",
        ],
        "RELATION_TYPES": lambda: ["relation_hint", "relation_chain", "behavior_chain"],
        "BEHAVIOR_V03": lambda: _vals("behavior"),
        "AUDIO_TYPES": lambda: ["audio_event", "audio_texture", "audio_role"],
        "COMMERCIAL_TYPES": lambda: [
            "product_presence", "product_clarity", "packaging_version",
            "ingredient_evidence", "process_evidence", "price_signal",
            "gift_signal", "store_signal", "category_code", "commercial_evidence",
            "content_intent",
        ],
        "EMOTION_VALUES": lambda: _vals("emotion"),
        "EDIT_TYPES": lambda: ["edit_value", "hook_role", "usable_duration", "platform_fit"],
        "COMPLIANCE_TYPES": lambda: ["compliance", "portrait_risk", "claim_risk"],
        "CATEGORY_CODES": lambda: _vals("category_code"),
    }
    if name in mapping:
        return mapping[name]()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
