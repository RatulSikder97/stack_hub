"""calibrate end-to-end in local + provider modes."""

from __future__ import annotations

import importlib

import pytest


@pytest.fixture
def seeded_corpus(tmp_project):  # noqa: ANN001
    corpus = tmp_project / "corpus"
    for writer in ("oliver_burkeman", "morgan_housel", "shane_parrish"):
        wd = corpus / writer
        wd.mkdir(exist_ok=True)
        for i in range(2):
            (wd / f"post_{i + 1}.md").write_text(
                f"# {writer} sample {i + 1}\n\nAttention follows commitment.\n",
                encoding="utf-8",
            )
    yield tmp_project


@pytest.fixture
def calibrate_module(seeded_corpus):  # noqa: ANN001
    import calibrate
    return importlib.reload(calibrate)


def test_local_calibration_runs(calibrate_module, seeded_corpus) -> None:  # noqa: ANN001
    rc = calibrate_module.main(["--seed", "1"])
    # Local mode should generally pass the gate since AI samples contain
    # multiple kill-list patterns by design.
    assert rc in {0, 1}
    cal_dir = seeded_corpus / "drafts" / "calibration"
    assert any(cal_dir.glob("ai_*.md"))
    assert any(cal_dir.glob("human_*.md"))
