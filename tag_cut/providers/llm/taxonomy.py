"""
Business label taxonomy (对齐素材库元数据 + 七层标签设计).

Used by pipelines/scorer/UI as the canonical label_type vocabulary.
"""

# Material-library index dimensions (sheet 02)
INDEX_DIMENSIONS = [
    "shot_scale",       # 景别
    "camera_move",      # 运镜
    "duration",         # 时长（也可从 shot 字段读）
    "dog_breed",        # 犬种
    "fur_color",        # 毛色
    "has_person",       # 是否含人物
    "has_logo",         # 是否含 LOGO
    "lighting",         # 光线类型
    "auth_status",      # 授权状态
    "valid_until",      # 有效期
    "emotion",          # 情绪值 / 情绪类别
    "applicable_types", # 适用类型
    "quality_grade",    # 画质等级
]

# L1 boolean / composition dims
L1_FLAGS = [
    "has_person", "has_dog", "has_product", "has_bowl", "has_logo",
    "subject_layout", "subject_count", "lighting_metrics",
]

# Extended design-doc dimensions
SUBJECT_TYPES = ["subject_type", "subject_count", "subject_layout", "subject_id", "subject_role"]
RELATION_TYPES = ["relation_hint", "relation_chain", "behavior_chain"]
BEHAVIOR_V03 = [
    "凑近闻", "第一口", "大口进食", "舔碗", "抬头看镜头", "摇尾", "等待投喂",
    "人物讲解", "递碗投喂", "状态镜头",
]
AUDIO_TYPES = ["audio_event", "audio_texture", "audio_role"]
COMMERCIAL_TYPES = [
    "product_presence", "product_clarity", "packaging_version",
    "ingredient_evidence", "process_evidence", "price_signal",
    "gift_signal", "store_signal", "category_code", "commercial_evidence",
    "content_intent",
]
EMOTION_VALUES = ["兴奋", "期待", "惊喜", "满足", "治愈", "反差", "搞笑", "悬念", "平静", "未知"]
EDIT_TYPES = ["edit_value", "hook_role", "usable_duration", "platform_fit"]
COMPLIANCE_TYPES = ["compliance", "portrait_risk", "claim_risk"]
CATEGORY_CODES = [
    "V01_产品特写", "V02_制作工艺", "V03_狗狗进食", "V04_人物出镜", "V99_待分类",
]
