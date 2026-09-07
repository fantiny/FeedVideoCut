# 2026-09-06 FeedVideoMake 与资产仓

> 补充 tag_cut 设计：制作阶段独立工程。

- **FeedVideoCut**：打标 / 审核 / 导出 → 写入 `asset_hub_root`
- **FeedVideoMake**：只读 hub，SOP 槽位编导 + CLI 流水线 → `runs/`
- 设计真源：`FeedVideoMake/docs/DESIGN.md`
- 共享契约：`FeedVideoAssets/CONTRACT.md`

本仓文档入口：`tag_cut/docs/ASSET_HUB.md`。
