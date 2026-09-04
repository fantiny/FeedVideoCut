# 在其他电脑上安装 tag_cut（从 zip 源码包）

本包布局（解压后）：

```
tag_cut-<version>/
├── INSTALL.md          ← 本说明（包根目录也会有一份）
├── input/              ← 把待分析 mp4 批次放这里（不要改原片）
│   └── README.md
└── tag_cut/            ← 引擎 + CLI + Electron + Agent skill 源
    ├── scripts/bootstrap.sh
    ├── scripts/tag_cut_cli.py
    ├── docs/AGENT_INSTALL.md
    └── ...
```

`config/default.yaml` 里 `input_root: ../input`，即相对 **tag_cut/** 的上一级 `input/`。

## 系统要求

| 项 | 要求 |
|----|------|
| OS | macOS 或 Linux（Windows 未作为一等公民测试） |
| Python | **3.11+**（推荐 3.11–3.13；勿用过旧 3.9） |
| FFmpeg | `ffmpeg` + `ffprobe` 在 PATH 中 |
| 网络 | 首次下载 YOLO 权重需要；可 `--skip-models` 稍后装 |
| 可选桌面 | Node.js 18+ / npm（仅 Electron 审核台需要） |

macOS 示例：

```bash
brew install ffmpeg
# 可选桌面：brew install node
```

## 一键引导（推荐）

```bash
cd tag_cut-<version>/tag_cut
chmod +x scripts/bootstrap.sh
./scripts/bootstrap.sh
# 可选：
# ./scripts/bootstrap.sh --with-desktop   # 安装 Electron 依赖
# ./scripts/bootstrap.sh --with-skill     # 安装到 Cursor/Claude/Codex
# ./scripts/bootstrap.sh --skip-models    # 跳过 YOLO 下载
```

成功后会创建 `.venv/`，并打印 `env-check` JSON（`ok: true` 即可）。

## 手动步骤（等价）

```bash
cd tag_cut-<version>/tag_cut
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -U pip
pip install -r requirements.txt
mkdir -p data exports models ../input
PYTHONPATH=. python scripts/tag_cut_cli.py models ensure
PYTHONPATH=. python scripts/tag_cut_cli.py env-check
```

## 放入素材

```bash
mkdir -p ../input/我的批次/v1
# 复制 mp4 到该目录（保持任意子目录结构均可，CLI 会 rglob *.mp4）
```

## 第一次分析（CLI）

```bash
cd tag_cut
PYTHONPATH=. .venv/bin/python scripts/tag_cut_cli.py analyze \
  --batch "../input/我的批次" \
  --limit 1
```

结果：`data/<批次名>/`；索引：`exports/<批次名>/index.csv`。

按标签搜索：

```bash
PYTHONPATH=. .venv/bin/python scripts/tag_cut_cli.py search --q "第一口" --limit 20
```

## 桌面审核台（可选）

```bash
./scripts/bootstrap.sh --with-desktop
./scripts/start_desktop.sh          # 一键：停旧进程 → 启 Vite + Electron + API
# 停止：./scripts/stop_desktop.sh
```

完全退出再开，避免 5173/8765 端口被旧进程占用（`start_desktop.sh` 会自动清理）。

## 安装到 Agent（Cursor / Claude / Codex）

```bash
cd tag_cut
./scripts/bootstrap.sh --with-skill
# 或：
PYTHONPATH=. .venv/bin/python scripts/install_agent_skill.py --targets all --force
```

详情：`docs/AGENT_INSTALL.md`。安装后请 **新开一轮对话**，再说「用 tag-cut 分析…」。

## 本包故意不包含的内容

| 排除项 | 原因 |
|--------|------|
| `.venv/`、`node_modules/` | 体积大且与本机绑定，需本地重建 |
| `data/`、`exports/` | 分析结果，可重建 |
| `models/*.pt` | 权重较大；用 `models ensure` 下载 |
| `config/local.yaml` | 本机当前模型选择，安装后自动生成 |
| 样例 mp4 | 请自备；放进 `input/` |

## 验收清单

- [ ] `env-check` → `"ok": true`
- [ ] `models/` 下有 `yolov8n.pt`（或你 activate 的权重）
- [ ] `analyze --limit 1` 能跑通并写出 `data/`
- [ ] （可选）`npm run electron:dev` 能打开审核台
- [ ] （可选）`~/.cursor/skills/tag-cut/SKILL.md` 存在

## 常见问题

| 问题 | 处理 |
|------|------|
| `python3` 版本过低 | 安装 3.11+ 再用该解释器建 venv |
| `ultralytics` / torch 安装失败 | 检查网络与 pip；Apple Silicon 一般可直接装 |
| YOLO 下载失败 | 稍后 `models ensure`；或手动下载到 `models/yolov8n.pt` |
| 找不到批次 | 确认路径是相对 **tag_cut/** 的 `../input/...` |
| Agent 找不到 skill | 重新 `install_agent_skill.py --force` 并新开对话 |

## 相关文档

- `tag_cut/README.md` — 功能与目录
- `tag_cut/docs/AGENT_INSTALL.md` — Agent skill 安装
- `docs/plans/`（若包内包含）— 设计与实现计划
