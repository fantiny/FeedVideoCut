# FeedVideoCut ↔ FeedVideoMake 共享资产仓（文件系统）

打标与制作是两个阶段/两个工程。共享的是**成果物目录**，不是代码。

## 真源

机器上的共享根目录（示例）：

`/Volumes/TRAVELSTAR/AICut/FeedVideoAssets`

完整布局与规则见该目录内 **`CONTRACT.md`**。

## 本仓如何接上

1. 复制 `tag_cut/config/local.yaml.example` → `tag_cut/config/local.yaml`
2. 将 `asset_hub_root` / `data_root` / `exports_root` 设为与 Make **相同**的 hub 路径：

```yaml
asset_hub_root: /Volumes/TRAVELSTAR/AICut/FeedVideoAssets
data_root: /Volumes/TRAVELSTAR/AICut/FeedVideoAssets/data
exports_root: /Volumes/TRAVELSTAR/AICut/FeedVideoAssets/exports
```

3. 之后分析写入 `data/`、导出写入 `exports/`，Make 侧只读同一路径。

校验：

```bash
cd tag_cut
PYTHONPATH=. python scripts/resolve_hub.py
```

## 写入内容（Cut → hub）

| 路径 | 内容 |
|------|------|
| `{hub}/data/<batch>/<mat>/` | material / shots / labels / scores / keyframes |
| `{hub}/exports/<batch>/` | index.json / index.csv |
| `{hub}/clips/` | 可选预切片段（后续） |

制作侧产物在 **FeedVideoMake/runs/**，不覆盖本仓 labels。

FeedVideoMake 设计见同级目录：`../FeedVideoMake/docs/DESIGN.md`（若本机按 AICut 并列放置）。
