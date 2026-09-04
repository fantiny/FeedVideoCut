# tag_cut — Agent 安装文档（给人 / 给 Agent 读）

把 `tag_cut` 安装成可在 **Cursor / Claude Code / Codex** 等 agent 里通过对话调用的 **Skill**。  
Skill 内部只通过 **CLI**（`scripts/tag_cut_cli.py`）干活，禁止 agent 手写流水线代码。

> 从 zip 包安装整机环境请先看同目录 [`INSTALL.md`](INSTALL.md)（或解压根目录 `INSTALL.md`）。

## 0. 给 Agent 的最短指令（复制即用）

当你（Agent）读到本文件且用户要求「安装 tag-cut skill」时，按顺序执行：

```bash
# 1) 进入仓库内的 tag_cut 根目录（含 requirements.txt / scripts/）
#    zip 包布局：.../tag_cut-<date>/tag_cut
cd /ABS/PATH/TO/tag_cut

# 2) 优先一键引导（创建 venv + 依赖 + 可选 YOLO）
chmod +x scripts/bootstrap.sh
./scripts/bootstrap.sh --with-skill
# 若已有 venv，可只装 skill：
# .venv/bin/python scripts/install_agent_skill.py --targets all --force

# 3) 自检
.venv/bin/python scripts/tag_cut_cli.py env-check
```
然后回复用户：

> 已安装 `tag-cut` skill 到 Cursor / Claude / Codex。请 **新开一轮对话**（或重启 agent）后再说：  
> 「用 tag-cut 分析 …」或「搜索第一口片段」。

若用户只要某一个平台：

```bash
python scripts/install_agent_skill.py --targets cursor --force
python scripts/install_agent_skill.py --targets claude --force
python scripts/install_agent_skill.py --targets codex --force
```

可选：同时写入当前仓库的项目级 skill：

```bash
python scripts/install_agent_skill.py --targets all --project-skill --force
```

## 1. 安装后落盘位置

| 平台 | 目录 |
|------|------|
| Cursor | `~/.cursor/skills/tag-cut/` |
| Claude Code | `~/.claude/skills/tag-cut/` |
| Codex | `$CODEX_HOME/skills/tag-cut/`（默认 `~/.codex/skills/tag-cut/`） |

每个目录含：

- `SKILL.md` — agent 触发与工作流
- `reference.md` — CLI 细节
- `TAG_CUT_ROOT` — 绝对路径指针（安装时写入）
- `env.json` — `TAG_CUT_ROOT` / `CLI` / `PYTHON` / `PYTHONPATH`

## 2. 对话调用方式（安装成功后）

用户可以说：

- 「用 tag-cut 把 `input/8月第60条信息流` 拆镜打标，先跑 1 条」
- 「搜索自然光 / 第一口 / 种草 片段」
- 「导出这批索引」
- 「下载 yolov8s 并设为当前模型」

Agent 应：

1. 发现/加载 `tag-cut` skill（读 `SKILL.md`）
2. 从 `TAG_CUT_ROOT` 或 `env.json` 解析路径
3. 执行 CLI，例如：

```bash
cd "$TAG_CUT_ROOT"
PYTHONPATH=. .venv/bin/python scripts/tag_cut_cli.py analyze \
  --batch "../input/8月第60条信息流" --limit 1
```

4. 把 JSON 结果摘要给用户（路径、镜头数、标签命中）

## 3. CLI 一览

```bash
python scripts/tag_cut_cli.py env-check
python scripts/tag_cut_cli.py analyze --batch <dir> [--limit N] [--force] [--batch-id NAME]
python scripts/tag_cut_cli.py search --q <kw> [--batch-id NAME] [--label-type TYPE]
python scripts/tag_cut_cli.py export --batch-id NAME
python scripts/tag_cut_cli.py models list|probe|ensure|download|activate
python scripts/tag_cut_cli.py serve --port 8765
```

完整参数见 `agent_skill/tag-cut/reference.md`。

## 4. 依赖前提

- macOS / Linux；Python 3.11+（推荐用仓库 `.venv`）
- 系统 `ffmpeg` / `ffprobe`（`brew install ffmpeg`）
- YOLO 权重可选：`python scripts/tag_cut_cli.py models ensure`

**硬约束：** 不得修改/删除 `input/` 原片；分析结果只写 `data/`、`exports/`、`models/`、`config/local.yaml`。

## 5. 人工安装（不经过 agent）

```bash
cd tag_cut
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/install_agent_skill.py --targets all --force
```

验证 skill 文件存在：

```bash
ls ~/.cursor/skills/tag-cut/SKILL.md
ls ~/.claude/skills/tag-cut/SKILL.md
ls ~/.codex/skills/tag-cut/SKILL.md
```

## 6. 卸载

```bash
rm -rf ~/.cursor/skills/tag-cut ~/.claude/skills/tag-cut ~/.codex/skills/tag-cut
```

## 7. 故障排查

| 现象 | 处理 |
|------|------|
| Agent 找不到 skill | 新开对话；确认 `--targets` 对应平台目录存在 |
| `Failed to fetch` / 旧 API | 桌面端请完全退出 Electron；CLI 不依赖 8765 |
| `ModuleNotFoundError` | 用 `.venv/bin/python`，并设 `PYTHONPATH=$TAG_CUT_ROOT` |
| YOLO 全空 | `models ensure` 或 `models download --model-id yolov8n` |
| 路径漂移（仓库搬家） | 重新跑 `install_agent_skill.py --force` 刷新 `TAG_CUT_ROOT` |

## 8. 源码位置（本仓库）

```
tag_cut/
├── docs/AGENT_INSTALL.md          ← 本文件
├── agent_skill/tag-cut/           ← skill 源（被复制到各 agent）
│   ├── SKILL.md
│   └── reference.md
└── scripts/
    ├── install_agent_skill.py     ← 安装器
    └── tag_cut_cli.py             ← 对话调用的唯一推荐入口
```
