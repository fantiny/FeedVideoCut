# tag_cut 视频拆解打标工具 · 设计文档

> 状态：已确认（2026-09-03）  
> 依据：`input/ai_cut_design_cut_tag.html`、`input/宠物食品短视频AI自动化生产系统_三份资料综合分析与AI开发设计原则_V2.0.html`、三份业务 Excel

## 1. 目标

在工作目录新建 `tag_cut/`，实现**全自动、分多层次**的视频拆解打标工具，并提供 **Electron 桌面审核台** 做人工抽检、改标签与导出索引。

短期交付（对齐文档 P0，并预留 L2–L6）：

- 只读扫描 `input/` 下视频（含 `8月第60条信息流/v1…v10`）
- 先拆再标：媒体事实 → 镜头分割 → 关键帧 → L0–L6 分层标签
- 人工审核界面：浏览切片、改标签、废片、导出
- **不删除、不改写** 原始素材

## 2. 范围决策

| 项 | 决策 |
|---|---|
| 产品形态 | Electron 桌面应用 + Python 分析引擎（sidecar） |
| 识别策略 | 全自动多层；低置信度进审核台 |
| 云端 VLM | L3–L6 支持；`config` 默认 **关闭** |
| 存储（v1） | 文件系统 JSON + 关键帧；不加 PostgreSQL |
| 输入 | `input/` 只读；输出在 `tag_cut/data/`、`tag_cut/exports/` |

## 3. 架构

```
input/*.mp4（只读）
        │
        ▼
┌───────────────────┐     HTTP/IPC      ┌─────────────────────┐
│ Electron 审核台    │ ◄──────────────► │ Python FastAPI      │
│ 时间线 / 改标签    │                   │ 任务队列 + 进度     │
│ 导出索引          │                   └──────────┬──────────┘
└───────────────────┘                              │
                                                   ▼
                              pipelines: L0 → 切镜 → L1 → L2 → L3–L6
                              providers/*（可替换）
                              data/: keyframes + JSON
```

### 3.1 Electron

- 选择批次目录 → 一键分析 → 进度
- 布局：左成片列表 / 中当前镜与关键帧播放 / 右 L0–L6 标签编辑
- 低置信度高亮；废片标记；导出索引
- 展示每条标签的 `source`（model / rule / local_vlm / cloud_vlm / human）

### 3.2 Python

- `ingest`：扫描视频，写 materials
- `split`：PySceneDetect + 关键帧
- `tag_l1` … `tag_l6`：按层 Provider；单层失败不中断整片
- 支持按层重跑（例如仅重跑 L3–L6）

## 4. 多层识别

| 层 | 内容 | 默认技术 | 云端 |
|---|---|---|---|
| L0 | 时长、分辨率、帧率、编码、音轨 | ffprobe | 否 |
| 切镜 | 镜头边界、scene_number、首/中/尾关键帧 | PySceneDetect + FFmpeg | 否 |
| L1 | 狗/人/碗/产品、景别、运镜启发式、画质 | YOLOv8 + 规则 + BRISQUE 等 | 否 |
| L2 | 人声/犬叫/咀嚼等；行为（凑近闻、第一口、舔碗…） | VAD/音效 + bbox 时序规则 | 否 |
| L3 | 主体关系、行为链草稿 | 规则；可选 VLM | 可选云端 |
| L4 | 内容价值 / 适用类型 | 规则 + 可选 VLM | 可选云端 |
| L5 | 编辑价值（可剪性等） | CV 指标 + 可选 VLM | 可选云端 |
| L6 | 合规占位（授权/风险字段） | 规则 + 可选 OCR/VLM | 可选云端 |

### 4.1 云端 VLM 约束

- `providers.llm.cloud_vlm.enabled: false`（默认）
- 仅用于 L3–L6；可配置信度门槛（如底层 &lt; 0.6 才调用）
- 输入裁剪：关键帧（每镜最多 3 帧）+ 时间码 + 已有标签；**不传完整视频**
- 按镜头特征缓存，避免重复调用
- 密钥缺失或关闭时静默回落规则，不致命失败
- 人工标签优先覆盖同类型自动标签

## 5. 目录结构

```
tag_cut/
├── apps/desktop/              # Electron
├── services/                  # FastAPI + 任务编排
├── pipelines/
├── providers/
│   ├── vision/
│   ├── audio/
│   └── llm/                   # local_vlm | cloud_vlm
├── schemas/
├── config/
│   └── default.yaml
├── data/                      # 分析结果（可重建）
├── exports/
├── tests/
└── README.md
```

单条视频数据目录示例：

```
tag_cut/data/<batch_id>/<material_id>/
  material.json
  shots.json
  labels.json
  scores.json
  layer_status.json
  keyframes/
```

## 6. 核心数据模型

对齐项目说明书 Schema，v1 用 JSON 文件：

- **material**：id, file_name, file_path, duration, width, height, fps, codec, has_audio, ingest_time
- **shot**：id, material_id, start_time, end_time, key_frames, scene_number, quality_grade, is_rejected, layer_status
- **label**：id, shot_id, layer, label_type, label_value, source, confidence
- **capability_scores**：hook, evidence, emotion, product, conversion, ending, transition, trust

## 7. 流水线与失败处理

任务进度：`queued → l0 → split → l1 → l2 → l3_l6 → ready`

- 单层失败：`layer_status=failed` + error；后续层尽量继续
- 模型权重缺失：该层 `skipped`，切镜 + L0 仍可用，UI 提示下载模型
- 云端超时/限流：该镜 `fallback=rule`
- **永不删除/改写 `input/` 原片**

## 8. 导出

`tag_cut/exports/<batch_id>/index.json` + `index.csv`

列对齐素材库索引表：编号、一级/二级分类建议、文件名、景别、运镜、时长、画面主体、犬种/主体、是否含人、是否含 LOGO、适用类型、存储路径、备注、能力分摘要等。

## 9. 非功能

- 成本：默认本地；云端按镜头限次与缓存
- 隐私：默认不发云；开启后仅脱敏关键帧包
- 可替换：所有 AI 能力经 Provider，禁止核心逻辑硬编码模型名
- 可评测：关键路径预留 `tag_cut/tests/` 与后续 `/evals/`

## 10. 明确不做（本设计 v1）

- 全自动成片 / 剪映工程导出
- PostgreSQL / pgvector（后续可迁）
- 发布数据复盘闭环
- 默认开启云端调用

## 11. 成功标准

1. 对 `input/8月第60条信息流` 十条成片可一键批量分析
2. 每条产出镜头列表、关键帧、多层标签 JSON
3. Electron 可浏览、改标签、标废片并导出索引
4. `cloud_vlm.enabled=false` 时全流程可离线完成（除未下载的本地权重）
5. 开启云端后 L3–L6 可增强，且可在审核台看到 `source=cloud_vlm`
