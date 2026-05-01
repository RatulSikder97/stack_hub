"""Voice extractor — local mode + LLM mode (with stub provider)."""

from __future__ import annotations

import pytest

from pipeline.voice import VoiceExtractor


@pytest.fixture
def seeded_corpus(tmp_project):  # noqa: ANN001
    corpus = tmp_project / "corpus"
    for writer in ("oliver_burkeman", "morgan_housel"):
        writer_dir = corpus / writer
        writer_dir.mkdir(exist_ok=True)
        for i in range(3):
            (writer_dir / f"post_{i + 1}.md").write_text(
                f"# {writer} sample {i + 1}\n\n"
                "Attention is the scarce resource. Defaults reduce friction.\n"
                "Focus is a choice repeated across many days.\n"
                "Decisions made early prevent rework later.\n",
                encoding="utf-8",
            )
    yield tmp_project


def test_local_extract_produces_per_writer_fingerprints(seeded_corpus) -> None:  # noqa: ANN001
    voice_map = VoiceExtractor(provider=None).extract()
    writers = [fp.writer for fp in voice_map.fingerprints]
    assert {"oliver_burkeman", "morgan_housel"} <= set(writers)
    md = voice_map.to_markdown()
    assert "## Per-Writer Fingerprints" in md
    assert "## Brand Voice Synthesis" in md
    assert "## Anti-Voice" in md


def test_extract_raises_when_corpus_empty(tmp_project) -> None:  # noqa: ANN001
    extractor = VoiceExtractor(provider=None)
    with pytest.raises(FileNotFoundError):
        extractor.extract()


def test_llm_extract_uses_provider(seeded_corpus, fake_provider) -> None:  # noqa: ANN001
    extractor = VoiceExtractor(provider=fake_provider, max_tokens=512)
    voice_map = extractor.extract()
    # Each writer should have produced "fake-response" plus the synthesis.
    assert all(fp.paragraph for fp in voice_map.fingerprints)
    assert voice_map.brand_synthesis
