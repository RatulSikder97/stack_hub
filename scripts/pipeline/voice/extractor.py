"""Generate `voice/voice_map.md` from `corpus/{writer}/*.md`.

Two modes:

* **LLM mode** — when an `LLMProvider` is supplied, it produces 4-6 sentence
  fingerprints per writer plus a brand-voice synthesis paragraph.
* **Local mode** — when no provider is available, the extractor produces a
  deterministic baseline that surfaces real corpus statistics (word count,
  average sentence length, top distinctive words) so the file is not empty
  and the user can see at a glance whether their corpus is rich enough.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from pipeline import paths as _paths
from pipeline.llm.base import LLMProvider

_STOPWORDS = frozenset(
    """
    a an and are as at be but by for from has have he her his i if in is it its
    of on or our she so that the their them then there these they this to was
    we were will with you your i'm i've don't can't won't isn't aren't they're
    you're we're it's that's there's would could should might may make made not
    do does did been being just like more than into through over under above
    very also out off up down very what when where why how which who whom whose
    one two three four five six seven eight nine ten about because while where
    """.split()
)


@dataclass(frozen=True)
class WriterFingerprint:
    writer: str
    paragraph: str

    def to_markdown(self) -> str:
        return f"### {self.writer}\n{self.paragraph.strip()}\n"


@dataclass(frozen=True)
class VoiceMap:
    fingerprints: list[WriterFingerprint]
    brand_synthesis: str
    anti_voice: list[str]

    def to_markdown(self) -> str:
        lines = ["# Voice Map", "", "## Per-Writer Fingerprints", ""]
        for fp in self.fingerprints:
            lines.append(fp.to_markdown())
        lines.extend(["## Brand Voice Synthesis", "", self.brand_synthesis.strip(), ""])
        lines.append("## Anti-Voice")
        for item in self.anti_voice:
            lines.append(f"- {item}")
        return "\n".join(lines).rstrip() + "\n"


class VoiceExtractor:
    """Build a `VoiceMap` from a corpus directory.

    Pass a `LLMProvider` to use the LLM path; pass `None` for the local
    deterministic path.
    """

    def __init__(
        self,
        *,
        provider: LLMProvider | None = None,
        max_tokens: int = 2000,
        corpus_dir: Path | None = None,
    ) -> None:
        self._provider = provider
        self._max_tokens = max_tokens
        self._corpus_dir = corpus_dir if corpus_dir is not None else _paths.CORPUS_DIR

    def extract(self) -> VoiceMap:
        writers = self._load_writers()
        if not writers:
            raise FileNotFoundError(
                f"No corpus files found under {self._corpus_dir}. "
                "Drop markdown posts into corpus/{writer}/{post}.md first."
            )

        if self._provider is not None:
            fingerprints = [
                self._llm_fingerprint(writer, posts) for writer, posts in writers.items()
            ]
            brand = self._llm_brand_synthesis(writers)
        else:
            fingerprints = [
                self._local_fingerprint(writer, posts) for writer, posts in writers.items()
            ]
            brand = self._local_brand_synthesis(writers)

        return VoiceMap(
            fingerprints=fingerprints,
            brand_synthesis=brand,
            anti_voice=_DEFAULT_ANTI_VOICE,
        )

    def write_voice_map(self, target: Path | None = None) -> Path:
        target = target if target is not None else _paths.VOICE_MAP_PATH
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.extract().to_markdown(), encoding="utf-8")
        return target

    # --- Corpus loading -----------------------------------------------------

    def _load_writers(self) -> dict[str, list[str]]:
        if not self._corpus_dir.exists():
            return {}
        result: dict[str, list[str]] = {}
        for writer_dir in sorted(self._corpus_dir.iterdir()):
            if not writer_dir.is_dir() or writer_dir.name.startswith("."):
                continue
            posts = [
                p.read_text(encoding="utf-8")
                for p in sorted(writer_dir.glob("*.md"))
                if p.is_file()
            ]
            if posts:
                result[writer_dir.name] = posts
        return result

    # --- LLM path -----------------------------------------------------------

    def _llm_fingerprint(self, writer: str, posts: list[str]) -> WriterFingerprint:
        provider = self._provider
        assert provider is not None
        joined = "\n\n---\n\n".join(posts)
        system = (
            "You analyze writing samples and produce concise voice fingerprints. "
            "Output a single 4-6 sentence paragraph describing cadence, posture, "
            "2-3 signature moves, and one trait the brand should NOT inherit. "
            "No bullet points, no headings, no preamble."
        )
        user = f"Writer: {writer}\n\nPosts:\n{joined}"
        paragraph = provider.generate(
            system, user, max_tokens=self._max_tokens, temperature=0.4
        )
        return WriterFingerprint(writer=writer, paragraph=paragraph)

    def _llm_brand_synthesis(self, writers: dict[str, list[str]]) -> str:
        provider = self._provider
        assert provider is not None
        all_posts = "\n\n===\n\n".join(
            "\n\n".join(posts) for posts in writers.values()
        )
        system = (
            "You synthesize a single 150-word brand voice description by reading "
            "multiple writers and distilling shared, transferable moves. Output one "
            "paragraph. No headings, no lists."
        )
        return provider.generate(
            system, all_posts, max_tokens=self._max_tokens, temperature=0.4
        )

    # --- Local path ---------------------------------------------------------

    def _local_fingerprint(self, writer: str, posts: list[str]) -> WriterFingerprint:
        stats = _CorpusStats.from_posts(posts)
        paragraph = (
            f"Cadence runs at roughly {stats.avg_sentence_words:.0f} words per sentence "
            f"across {stats.post_count} posts ({stats.total_words:,} words total). "
            f"Distinctive vocabulary skews toward: {', '.join(stats.distinctive_words[:8]) or 'none yet'}. "
            f"Dominant signature moves to study before drafting: short paragraphs, named "
            f"frictions, and unglamorous next steps. Do not inherit any move "
            f"that flattens nuance or substitutes confidence for evidence. "
            f"NOTE: Generated locally without LLM — re-run extract_voice with a "
            f"provider key for a richer fingerprint."
        )
        return WriterFingerprint(writer=writer, paragraph=paragraph)

    def _local_brand_synthesis(self, writers: dict[str, list[str]]) -> str:
        flat: list[str] = [post for posts in writers.values() for post in posts]
        stats = _CorpusStats.from_posts(flat)
        names = ", ".join(writers.keys())
        return (
            f"Synthesizing across {len(writers)} writer(s) ({names}) covering "
            f"{stats.post_count} posts and {stats.total_words:,} words: write "
            f"like a calm operator helping a thoughtful reader make a clearer "
            f"decision this week. Average sentence length is "
            f"{stats.avg_sentence_words:.0f} words; favor concrete observation over "
            f"abstraction. Lead with the friction, name the principle behind it, "
            f"return to one action a reader can apply by the next morning. The "
            f"voice should feel decided but not certain, specific but not narrow, "
            f"and warm without being soft. (Local synthesis — re-run with provider "
            f"for a real model-driven distillation.)"
        )


_DEFAULT_ANTI_VOICE = [
    "Do not write motivational slogans disguised as insight.",
    "Do not use cinematic openings that delay the core idea.",
    "Do not over-stack frameworks when one lens is enough.",
    "Do not end with vague empowerment lines; close with a precise sentence worth saving.",
]


@dataclass(frozen=True)
class _CorpusStats:
    post_count: int
    total_words: int
    avg_sentence_words: float
    distinctive_words: list[str]

    @classmethod
    def from_posts(cls, posts: Iterable[str]) -> _CorpusStats:
        post_list = list(posts)
        joined = " ".join(post_list)
        words = re.findall(r"[A-Za-z][A-Za-z'-]+", joined)
        sentences = [s for s in re.split(r"[.!?]+", joined) if s.strip()]
        sentence_word_counts = [len(re.findall(r"\w+", s)) for s in sentences]
        avg = (
            sum(sentence_word_counts) / len(sentence_word_counts)
            if sentence_word_counts
            else 0.0
        )
        counts = Counter(
            w.lower()
            for w in words
            if len(w) >= 4 and w.lower() not in _STOPWORDS
        )
        distinctive = [w for w, _ in counts.most_common(20)]
        return cls(
            post_count=len(post_list),
            total_words=len(words),
            avg_sentence_words=avg,
            distinctive_words=distinctive,
        )
