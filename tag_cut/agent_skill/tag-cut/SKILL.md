---
name: tag-cut
description: >
  Pet-food short-video shot split + multilayer tagging (景别/运镜/行为/情绪/商业证据)
  via tag_cut CLI. Use when the user asks to 拆解视频、打标、镜头分割、按标签搜索片段、
  导出素材索引、下载/切换 YOLO、分析酥坡坡/宠物食品短视频批次, or mentions tag_cut / tag-cut.
---

# tag-cut

CLI-first skill for the `tag_cut` engine. **Do not reinvent pipelines** — call the CLI and report JSON.

## Resolve root

1. Read `TAG_CUT_ROOT` file next to this `SKILL.md` (written by installer), **or**
2. Read `env.json` → `TAG_CUT_ROOT` / `CLI` / `PYTHON` / `PYTHONPATH`, **or**
3. Ask user for the absolute path to the `tag_cut` directory.

Default invoke pattern:

```bash
cd "$TAG_CUT_ROOT"
PYTHONPATH=. "$TAG_CUT_ROOT/.venv/bin/python" scripts/tag_cut_cli.py <cmd> ...
```

If `.venv` missing, run env-check and tell the user to `pip install -r requirements.txt`.

## Commands (always prefer these)

| Intent | CLI |
|--------|-----|
| Check machine | `env-check` |
| Analyze batch | `analyze --batch <dir> [--limit N] [--force] [--batch-id NAME] [--progress ndjson]` |
| Search clips | `search --q <kw> [--batch-id NAME] [--label-type TYPE] [--limit 50]` |
| Export index | `export --batch-id NAME` |
| YOLO list/probe | `models list` / `models probe` / `models ensure` |
| YOLO download | `models download --model-id yolov8n` |
| YOLO activate | `models activate --model-id yolov8s` |
| API server | `serve --port 8765` (long-running; only if user asks) |

All commands print **JSON** to stdout (one parseable document, `ok` field included);
logs/progress go to stderr. Exit codes: 0=ok, 1=failed, 2=usage/input error.
`analyze --progress ndjson` streams one `{"event":"stage",...}` line per layer to stderr.
Summarize for the user; quote key paths.

## Workflow

```
Task Progress:
- [ ] env-check
- [ ] models ensure   # if L1 detection needed and weights missing
- [ ] analyze --batch ...
- [ ] search / export as requested
```

### Analyze rules
- Never modify/delete files under `input/`.
- Results go to `data/<batch_id>/`. Use `--force` only when user confirms regenerate.
- Prefer `--limit 1` for first smoke on a large batch.
- After analyze, mention `exports/<batch_id>/index.csv` if export ran.

### Search rules
- Keywords: `自然`→光线, `第一口`→行为, `种草`→适用类型, `特写`→景别, `V03`→分类码.
- Use `--label-type lighting|behavior|shot_scale|applicable_types|emotion|hook_role` to narrow.
- Present hits as: material · time range · matched labels · shot_id.

### YOLO rules
- On Apple Silicon ≤16GB prefer `yolov8n`.
- Download into `models/`; activate writes `config/local.yaml`.
- Switching model requires re-analyze (`--force`) to refresh L1.

## Conversation examples

**User:** 把这个目录拆镜打标：`../input/8月第60条信息流`，先跑 1 条  
**Agent:** run `analyze --batch "../input/8月第60条信息流" --limit 1` then summarize shots/labels.

**User:** 搜索「第一口」片段  
**Agent:** run `search --q 第一口 --limit 30` and list hits.

**User:** 装到 Claude / Codex  
**Agent:** from `$TAG_CUT_ROOT` run `python scripts/install_agent_skill.py --targets all --force` (see `$TAG_CUT_ROOT/docs/AGENT_INSTALL.md`).

## More detail
- Install / multi-agent targets: `$TAG_CUT_ROOT/docs/AGENT_INSTALL.md`
- CLI flags: [reference.md](reference.md)
