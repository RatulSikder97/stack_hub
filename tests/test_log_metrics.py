"""log_metrics CLI behavior."""

from __future__ import annotations

import importlib

import pytest

from pipeline.models import PostRecord
from pipeline.repository import PostRepository


@pytest.fixture
def log_metrics_module(tmp_project):  # noqa: ANN001
    import log_metrics
    return importlib.reload(log_metrics)


def test_updates_metrics(log_metrics_module, tmp_project) -> None:  # noqa: ANN001
    repo = PostRepository()
    repo.append(PostRecord(post_id="20260501-x"))

    rc = log_metrics_module.main(
        ["--post-id", "20260501-x", "--open-rate", "42.5", "--share-count", "9"]
    )
    assert rc == 0

    refreshed = repo.get("20260501-x")
    assert refreshed.open_rate == 42.5
    assert refreshed.share_count == 9


def test_rejects_negative_share_count(log_metrics_module, tmp_project) -> None:  # noqa: ANN001
    rc = log_metrics_module.main(
        ["--post-id", "20260501-x", "--open-rate", "10", "--share-count", "-1"]
    )
    assert rc == 2


def test_rejects_out_of_range_open_rate(log_metrics_module, tmp_project) -> None:  # noqa: ANN001
    rc = log_metrics_module.main(
        ["--post-id", "20260501-x", "--open-rate", "150", "--share-count", "1"]
    )
    assert rc == 2
