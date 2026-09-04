# tag_cut 工具脚本

| 脚本 | 作用 |
|------|------|
| `scripts/bootstrap.sh` | 新机器：建 venv、装依赖、可选 YOLO / Electron / Agent skill |
| `scripts/start_desktop.sh` | **一键启动**：先停旧进程，再开 Vite + Electron（Electron 内起 API） |
| `scripts/stop_desktop.sh` | 关掉占用 5173/8765 及本应用相关 Electron/Vite |
| `scripts/tag_cut_cli.py` | CLI：analyze / search / export / models |
| `scripts/install_agent_skill.py` | 安装 Cursor/Claude/Codex skill |
| `scripts/package_release.py` | 打跨机安装 zip |
| `scripts/smoke_batch.py` | 批次流水线冒烟 |

标签词表扩展见 **`docs/TAXONOMY.md`**（`config/taxonomy.yaml` + 可选 `taxonomy.local.yaml`）。

## 日常开发（桌面审核台）

```bash
cd tag_cut
./scripts/start_desktop.sh
```

只停不启：

```bash
./scripts/stop_desktop.sh
```

环境变量（可选）：

- `TAG_CUT_VITE_PORT` 默认 `5173`
- `TAG_CUT_API_PORT` 默认 `8765`
- `TAG_CUT_PYTHON` 指定 Python 解释器（Electron 后端也会读）

## 首次 / 换机

```bash
./scripts/bootstrap.sh --with-desktop
./scripts/start_desktop.sh
```
