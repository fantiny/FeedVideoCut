"""Tests for batch index export."""
from pathlib import Path
import json
import csv
import pytest

SAMPLE = (
    Path(__file__).resolve().parents[2]
    / "input" / "8月第60条信息流" / "v1" / "v1.mp4"
)
SAMPLE_BATCH = SAMPLE.parent.parent  # 8月第60条信息流 dir


@pytest.fixture
def prepared_data(tmp_path):
    if not SAMPLE.exists():
        pytest.skip("sample video not found")
    from pipelines.ingest import ingest_video
    from pipelines.split import split_video
    from pipelines.tag_l1 import tag_l1
    from pipelines.tag_l2 import tag_l2
    from pipelines.tag_l3_l6 import tag_l3_l6
    ingest_video(SAMPLE, data_root=tmp_path / "data", batch_id="test_batch")
    split_video(SAMPLE, data_root=tmp_path / "data", batch_id="test_batch")
    tag_l1(SAMPLE, data_root=tmp_path / "data", batch_id="test_batch")
    tag_l2(SAMPLE, data_root=tmp_path / "data", batch_id="test_batch")
    tag_l3_l6(SAMPLE, data_root=tmp_path / "data", batch_id="test_batch")
    return tmp_path


def test_export_creates_json_and_csv(prepared_data):
    from pipelines.export_index import export_batch
    out = export_batch(
        batch_id="test_batch",
        data_root=prepared_data / "data",
        exports_root=prepared_data / "exports",
    )
    assert (out / "index.json").exists()
    assert (out / "index.csv").exists()


def test_export_json_has_rows(prepared_data):
    from pipelines.export_index import export_batch
    out = export_batch("test_batch", prepared_data / "data", prepared_data / "exports")
    rows = json.loads((out / "index.json").read_text())
    assert isinstance(rows, list) and len(rows) > 0


def test_export_row_count_matches_non_rejected_shots(prepared_data):
    from pipelines.export_index import export_batch
    from services.config import anchor_root, load_config
    from services.paths import material_id, ensure_material_dir
    mat_id = material_id(SAMPLE, anchor_root(load_config()))
    mat_dir = ensure_material_dir(prepared_data / "data", "test_batch", mat_id)
    shots = json.loads((mat_dir / "shots.json").read_text())
    non_rejected = [s for s in shots if not s.get("is_rejected")]

    out = export_batch("test_batch", prepared_data / "data", prepared_data / "exports")
    rows = json.loads((out / "index.json").read_text())
    assert len(rows) == len(non_rejected)


def test_export_csv_has_header_columns(prepared_data):
    from pipelines.export_index import export_batch, COLUMNS
    out = export_batch("test_batch", prepared_data / "data", prepared_data / "exports")
    with open(out / "index.csv", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames or []
    for col in ["编号", "景别", "时长(s)", "适用类型", "hook_score"]:
        assert col in header
