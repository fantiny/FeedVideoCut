# 标签维度配置（Taxonomy）

标签词表与维度不再硬编码在流水线里，统一由配置驱动。

## 文件

| 文件 | 作用 |
|------|------|
| `config/taxonomy.yaml` | 默认词表、维度注册表、L2 行为/音频规则、导出列、搜索跳过类型 |
| `config/taxonomy.local.yaml` | 本机/业务扩展（**已 gitignore**），合并叠加到默认配置 |

改完配置后：CLI 下次运行即生效；常驻 API / Electron 需 `POST /taxonomy/reload` 或重启进程。

## 新增枚举值

在 `taxonomy.yaml`（或 local）对应 `enums.<name>.values` 追加：

```yaml
enums:
  behavior:
    values:
      - 凑近闻
      # ...
      - 新行为名
```

仅加词表不会自动打出该标签；还需要规则或人工改标 / VLM。

## 本机扩展（推荐）

```yaml
# config/taxonomy.local.yaml
enums:
  behavior:
    extend_values: [新行为]
  emotion:
    extend_values: [安心]
extend_behavior_rules:
  - id: custom_chew
    emit: 新行为
    confidence: 0.5
    when: { audio_any: [chew] }
```

`extend_values` / `extend_behavior_rules` 会**追加**，不会整段覆盖默认列表。

## L2 规则字段

`behavior_rules[].when` 支持：

- `audio_any` / `audio_none`
- `has_dog` / `has_person` / `has_bowl` / `closeup`
- `duration_lt` / `duration_lte` / `duration_gt` / `duration_gte`
- `fallback_only: true` — 仅当没有任何主规则命中时参与

`audio_texture_rules` / `audio_role_rules` 同理，见 `taxonomy.yaml`。

## UI / 导出 / 搜索

- UI 精选标签：`dimensions[].ui_featured` 或 `ui.featured_label_types`
- 导出 CSV 列：`export.columns`
- 搜索忽略的重字段：`search.skip_match_types`

## API

```http
GET  /taxonomy          # 维度 + 枚举（给桌面端 / Agent）
POST /taxonomy/reload   # 清缓存后重载
```
