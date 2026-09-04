"""Tests for path helpers used by the API."""
from pathlib import Path

from services.paths import resolve_batch_path


def test_resolve_batch_by_folder_name():
    repo_input = Path(__file__).resolve().parents[2] / "input" / "8月第60条信息流"
    if not repo_input.exists():
        import pytest
        pytest.skip("sample batch missing")
    found = resolve_batch_path(
        "8月第60条信息流",
        cwd=Path(__file__).resolve().parents[1],
        input_root=Path("../input"),
    )
    assert found is not None
    assert found.name == "8月第60条信息流"


def test_resolve_batch_relative_input():
    tag_cut = Path(__file__).resolve().parents[1]
    sample = tag_cut.parent / "input" / "8月第60条信息流"
    if not sample.exists():
        import pytest
        pytest.skip("sample batch missing")
    found = resolve_batch_path(
        "../input/8月第60条信息流",
        cwd=tag_cut,
        input_root=Path("../input"),
    )
    assert found is not None
    assert found.exists()
