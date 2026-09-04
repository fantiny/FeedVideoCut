# tag-cut CLI reference

All commands from `TAG_CUT_ROOT` with `PYTHONPATH=.`.

## env-check
```bash
python scripts/tag_cut_cli.py env-check
```
Returns JSON: ffmpeg, ram, accelerator, recommended YOLO, issues[].

## analyze
```bash
python scripts/tag_cut_cli.py analyze \
  --batch "/abs/or/rel/input/batch" \
  --batch-id "my_batch" \
  --limit 2 \
  --force
```
- `--layers l0,split,l1,l2,l3_l6` optional subset
- `--no-export` skip index write

## search
```bash
python scripts/tag_cut_cli.py search --q "自然" --batch-id "8月第60条信息流" --limit 40
python scripts/tag_cut_cli.py search --q "种草" --label-type applicable_types
```

## export
```bash
python scripts/tag_cut_cli.py export --batch-id "8月第60条信息流"
```

## models
```bash
python scripts/tag_cut_cli.py models list
python scripts/tag_cut_cli.py models probe
python scripts/tag_cut_cli.py models ensure
python scripts/tag_cut_cli.py models download --model-id yolov8s
python scripts/tag_cut_cli.py models activate --model-id yolov8s
```

## serve
```bash
python scripts/tag_cut_cli.py serve --port 8765
```
HTTP API includes `/tags/query`, `/models/yolo`, `/jobs`, etc. Prefer CLI for agents unless UI/API explicitly needed.

## HTTP equivalents (optional)
| CLI | HTTP |
|-----|------|
| search | `GET /tags/query?q=` |
| models list | `GET /models/yolo` |
| export | `POST /exports/{batch_id}` |
| analyze | `POST /jobs` |
