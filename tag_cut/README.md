# tag_cut — 宠物短视频拆解打标工具

全自动多层次视频拆解打标 + Electron 审核台。

## 技术栈

- **Python 3.11+**：分析引擎（FastAPI + Uvicorn）
- **FFmpeg / PySceneDetect**：镜头分割 + 关键帧
- **OpenCV**：画质评估（Laplacian 锐度）
- **Ultralytics YOLOv8**（可选）：目标检测（狗/人/碗等）
- **Electron 32 + React 18 + Vite**：桌面审核台

## 多层识别流水线

| 层 | 内容 | 技术 |
|---|---|---|
| L0 | 媒体事实（时长/分辨率/帧率/编码） | ffprobe |
| split | 镜头分割 + 首/中/尾关键帧 | PySceneDetect + FFmpeg |
| L1 | 目标检测 / 景别 / 画质等级 | YOLOv8（可选）+ 规则 |
| L2 | 音频事件（人声/犬叫/咀嚼）+ 行为（凑近闻/第一口/舔碗…） | 能量+ZCR 规则 |
| L3–L6 | 关系链 / 适用类型 / 编辑价值 / 合规占位 + 能力分 | 规则引擎；可选云端 VLM |

## 快速开始

### 1. 安装依赖

确保已安装 FFmpeg（`brew install ffmpeg`）。

```bash
cd tag_cut
pip install -r requirements.txt          # Python 依赖
cd apps/desktop && npm install            # Electron/React 依赖
```

### 2. 运行测试

```bash
cd tag_cut
PYTHONPATH=. pytest tests/ -v
```

### 3. CLI 一键 smoke 测试

```bash
cd tag_cut
PYTHONPATH=. python scripts/smoke_batch.py \
  --batch "../input/8月第60条信息流" \
  --limit 1
```

输出示例：
```
[smoke] Batch: 8月第60条信息流  |  Videos: 1
  ✓ l0: done  ✓ split: done  ✓ l1: done  ✓ l2: done  ✓ l3_l6: done
  shots=18  keyframes=54  labels=126  scores=18  elapsed: 12.2s
```

### 4. 启动 API 服务（独立使用）

```bash
cd tag_cut
PYTHONPATH=. uvicorn services.app:app --port 8765 --reload
```

### 5. 启动 Electron 桌面应用

```bash
cd tag_cut/apps/desktop
npm run electron:dev     # 开发模式（同时启动 Vite + Electron）
```

Electron 会自动启动 Python 后台服务；应用打开后：
1. 输入批次目录路径（默认 `../input/8月第60条信息流`）
2. 点击「开始分析」→ 查看逐层进度
3. 点击素材查看切片 / 关键帧 / 标签
4. 标记废片、导出索引

## 云端 VLM（L3–L6 增强，默认关闭）

编辑 `config/default.yaml`：

```yaml
providers:
  llm:
    cloud_vlm:
      enabled: true            # 改为 true
      model: gpt-4o
      api_key_env: OPENAI_API_KEY
      confidence_threshold: 0.6
```

然后设置环境变量：

```bash
export OPENAI_API_KEY=sk-...
```

开启后仅发送每镜最多 3 帧关键帧 + 已有标签摘要（不传完整视频）。

## 目录结构

```
tag_cut/
├── apps/desktop/      # Electron + React 审核台
├── config/            # 配置文件
├── schemas/           # JSON Schema 数据契约
├── services/          # FastAPI 服务 + 工具函数
├── pipelines/         # 各层流水线（ingest/split/tag_l1…）
├── providers/         # 视觉/音频/LLM Provider
├── tests/             # pytest 测试套件
├── scripts/           # CLI 工具
├── data/              # 分析结果（gitignored，可重建）
├── exports/           # 导出索引（gitignored）
└── models/            # 模型权重（gitignored）
```

## 设计文档

- `docs/plans/2026-09-03-tag-cut-design.md` — 完整设计
- `docs/plans/2026-09-03-tag-cut.md` — 实现计划
