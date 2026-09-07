"""中文语义描述（语义标）：规则组合 + 可选 LLM 批量精修。

规则层把镜头的视觉信号（主体/物体/行为/景别/分类）组合成一句可读的中文描述；
LLM 层（可选，OpenAI 兼容接口）批量把规则描述改写得更自然、更贴合业务。
"""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

# 行为 → 动作短语（按叙事优先级排序）
_ACTION_PHRASES: list[tuple[str, str]] = [
    ("大口进食", "大口吃着碗里的鲜粮"),
    ("舔碗", "低头舔着碗"),
    ("第一口", "试探着吃下第一口"),
    ("凑近闻", "凑近闻一闻食物"),
    ("递碗投喂", "主人递碗投喂"),
    ("等待投喂", "眼巴巴地等待投喂"),
    ("摇尾", "开心地摇着尾巴"),
    ("人物讲解", "出镜讲解产品"),
]

_FOOD_OBJECTS_ZH = "鲜粮食材"


def compose_semantic_desc(
    *,
    has_dog: bool,
    has_person: bool,
    has_product: bool,
    behaviors: list[str],
    category: str = "",
    objects: list[str] | None = None,
    shot_scale: str = "",
) -> str:
    if has_dog:
        subject = "狗狗"
    elif has_person:
        subject = "人物"
    elif has_product:
        subject = "产品"
    else:
        subject = "画面"

    action = next((phrase for key, phrase in _ACTION_PHRASES if key in behaviors), None)
    if action:
        desc = f"{subject}{action}"
    elif has_product or "产品" in category:
        desc = f"产品特写：{_FOOD_OBJECTS_ZH}摆放展示"
    elif has_dog:
        desc = f"{subject}出镜，画面活泼"
    else:
        desc = f"{subject}出镜"

    if objects and "bowl" in objects and "碗" not in desc:
        desc += "，碗里的食材清晰可见"
    return desc


def resolve_semantic_llm(cfg: dict) -> dict | None:
    """Optional LLM (OpenAI-compatible) for refining rule-composed descriptions."""
    llm = dict((cfg.get("llm") or {}))
    if not bool(llm.get("enabled")):
        return None
    active = str(llm.get("active_profile") or "")
    profile = dict((llm.get("profiles") or {}).get(active) or {})
    merged = {k: v for k, v in llm.items() if k not in ("profiles", "active_profile")}
    merged.update({k: v for k, v in profile.items() if v not in (None, "")})
    api_base = str(merged.get("api_base") or "").strip()
    model = str(merged.get("model") or "").strip()
    if not api_base or not model:
        return None
    import os

    api_key = str(merged.get("api_key") or "").strip() or os.environ.get(
        str(merged.get("api_key_env") or ""), ""
    ).strip()
    if not api_key:
        return None
    return {
        "api_base": api_base,
        "api_key": api_key,
        "model": model,
        "timeout_s": float(merged.get("timeout_s") or 60),
    }


def refine_semantic_batch(
    items: list[dict], llm: dict, *, batch_size: int = 30
) -> dict[str, str]:
    """
    items: [{"shot_id", "rule_desc", "objects", "behaviors", "category"}]
    Returns {shot_id: refined_desc} for the shots the LLM answered for;
    missing/failed shots keep the rule description.
    """
    out: dict[str, str] = {}
    system = (
        "你是宠物鲜食广告的素材标注员。给你一批镜头的粗描述和信号"
        "（物体/行为/分类），把每条改写成一句 12–24 字的自然中文描述，"
        "描述画面主体正在做什么。只输出 JSON："
        '{"items":[{"shot_id":"...","desc":"..."}]}，不要多余文字。'
    )
    for i in range(0, len(items), batch_size):
        chunk = items[i:i + batch_size]
        body = json.dumps({"items": chunk}, ensure_ascii=False)
        req = urllib.request.Request(
            llm["api_base"].rstrip("/") + "/chat/completions",
            data=json.dumps({
                "model": llm["model"],
                "temperature": 0.3,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": body},
                ],
            }).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {llm['api_key']}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=llm["timeout_s"]) as resp:
                payload = json.loads(resp.read().decode())
            content = ((payload.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
            content = content.strip()
            if content.startswith("```"):
                import re
                content = re.sub(r"^```(?:json)?\s*", "", content)
                content = re.sub(r"\s*```$", "", content)
            parsed = json.loads(content)
            for it in parsed.get("items") or []:
                sid = str(it.get("shot_id") or "")
                desc = str(it.get("desc") or "").strip()
                if sid and desc:
                    out[sid] = desc[:60]
        except Exception:  # noqa: BLE001 — refinement is best-effort
            continue
    return out
