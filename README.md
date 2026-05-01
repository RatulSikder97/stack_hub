# Stack Hub — Substack Pipeline

A voice-preserving, human-gated content pipeline that takes a post from idea
to publish while enforcing anti-AI-tells, tracking pattern rotation, and
keeping a single source of truth in flat files plus git.

## Project purpose

Most "AI writing pipelines" produce content that reads like AI. This one is
designed to fail loudly when its own output starts sounding like a model:
voice fingerprints are built from a real human corpus, every draft passes
through a kill-list detector before it leaves the pipeline, and a quarterly
calibration ritual catches voice drift before it ships.

## Architecture

```
scripts/
├── pipeline/                 # internal library
│   ├── paths.py              # filesystem layout
│   ├── config.py             # typed Settings (pydantic-settings, .env)
│   ├── models.py             # PostRecord, PostStatus enum, RetentionAnswer
│   ├── repository.py         # PostRepository CRUD with atomic writes
│   ├── templating.py         # Jinja2 master prompt rendering
│   ├── logging_config.py     # structured logger
│   ├── llm/                  # provider abstraction (SOLID OCP)
│   │   ├── base.py           # LLMProvider ABC
│   │   ├── openai_provider.py
│   │   ├── gemini_provider.py
│   │   ├── anthropic_provider.py
│   │   ├── novita_provider.py
│   │   ├── factory.py        # build_provider(settings)
│   │   └── text_utils.py
│   ├── detectors/            # AI-tells detection
│   │   ├── base.py           # Detector ABC + DetectionResult/Flag
│   │   ├── local_kill_list.py # all 6 kill-list patterns, regex, no API
│   │   └── llm_judge.py      # LLM-as-judge detector
│   └── voice/
│       └── extractor.py      # corpus -> voice_map.md (LLM or local)
├── new_brief.py              # entry points (CLI)
├── draft_post.py
├── run_ai_tells.py
├── retention_check.py
├── log_publish.py
├── log_metrics.py
├── calibrate.py
├── pattern_audit.py
├── cadence_check.py
├── health_check.py
└── extract_voice.py
```

The pipeline depends on abstract interfaces (`LLMProvider`, `Detector`),
never on a specific SDK. Adding a new provider is a single file and a
factory registration; adding a new detector is the same.

## Setup

```bash
# 1. Install deps
pip install -r requirements.txt
# or, with uv:
uv pip install -r requirements.txt

# 2. Configure provider
cp .env.example .env
# edit .env, set LLM_PROVIDER and the matching API key

# 3. Drop your real corpus into corpus/{writer_name}/{post_title}.md
#    (the bundled corpus is PLACEHOLDER and labeled as such).

# 4. Build voice fingerprints from that corpus
python scripts/extract_voice.py            # uses provider if key set
python scripts/extract_voice.py --local    # forces local heuristic

# 5. Verify the test suite passes
python -m pytest
```

## LLM providers

Set `LLM_PROVIDER` in `.env` to one of:

| Provider  | Env var pair                                | Notes                                              |
|-----------|---------------------------------------------|----------------------------------------------------|
| openai    | `OPENAI_API_KEY`, `OPENAI_MODEL`            | Uses Responses API. Default model `gpt-4.1`.       |
| gemini    | `GEMINI_API_KEY`, `GEMINI_MODEL`            | Uses `google-genai`. Default `gemini-1.5-pro`.     |
| anthropic | `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`      | Uses Messages API. Default `claude-opus-4-7`.      |
| novita    | `NOVITA_API_KEY`, `NOVITA_MODEL`, `NOVITA_BASE_URL` | OpenAI-compatible at `/v3/openai`.        |

Switch providers without restarting anything else: change the env var, run
the next CLI command.

## IDEA → PUBLISH workflow

```bash
# 1. Capture the idea as a brief.
python scripts/new_brief.py --title "Decision Fatigue Is a Default Problem"
# -> /briefs/20260502-decision-fatigue-is-a-default-problem.md

# 2. Manually fill: One Big Idea, Why this why now, hook pattern,
#    framework, Reader Transformation, Forbidden Moves.

# 3. Generate a draft. Skips the API in --mock mode.
python scripts/draft_post.py --post-id 20260502-decision-fatigue-is-a-default-problem

# 4. Run the AI-tells detector. Exits 1 if any kill-list pattern fires.
python scripts/run_ai_tells.py drafts/20260502-decision-fatigue-is-a-default-problem_v1.md

# 5. Edit the draft by hand, then run the human retention checklist.
python scripts/retention_check.py --post-id 20260502-decision-fatigue-is-a-default-problem

# 6. Publish to Substack manually, then log it. Refuses example.com URLs.
python scripts/log_publish.py --post-id 20260502-decision-fatigue-is-a-default-problem
# (or non-interactive: --url https://stackhub.substack.com/p/decision-fatigue)

# 7. After analytics roll in, log metrics.
python scripts/log_metrics.py \
  --post-id 20260502-decision-fatigue-is-a-default-problem \
  --open-rate 45.2 --share-count 18
```

The pipeline gates publication on **both** `ai_tells_check_passed` and
`human_edit_completed`. You cannot bypass either; `log_publish.py` exits
non-zero if either is missing.

## Rituals

All four cadences plus the human retention checklist live in
`rituals/RITUALS.md`.

| Cadence    | Time   | Output                                           |
|------------|--------|--------------------------------------------------|
| Daily      | 15 min | One new brief ready                              |
| Weekly     | 90 min | Metrics logged, 2 ideas promoted                 |
| Monthly    | 30 min | `rituals/audits/{YYYY-MM}_pattern_audit.md`      |
| Quarterly  | 2 hr   | Calibration <30% gate verified                   |

```bash
python scripts/pattern_audit.py    # 30-day hooks/frameworks audit
python scripts/cadence_check.py    # ON TRACK / SLIPPING / LATE
python scripts/health_check.py     # 4-signal one-page report
python scripts/calibrate.py        # Sprint-grade voice calibration
```

## Voice drift handling

If quarterly calibration detects ≥30%, follow the Quarterly Voice Drift
Gate in `rituals/RITUALS.md`:

1. Identify which AI samples scored highest and why.
2. Update `/voice/voice_map.md` and `/prompts/master_system_prompt.md` to
   re-tighten the moves the model is failing to inherit.
3. Re-run `python scripts/extract_voice.py` if your corpus changed.
4. Re-run `python scripts/calibrate.py` until under 30%.
5. Do **not** publish in the meantime.

## How to add a new LLM provider

1. Create `scripts/pipeline/llm/<name>_provider.py`. Subclass `LLMProvider`
   and implement `_generate(GenerationRequest) -> str`.
2. Add the API-key field and model fields to `Settings` in
   `scripts/pipeline/config.py`.
3. Register the builder in `scripts/pipeline/llm/factory.py`.
4. Add the env vars to `.env.example`.
5. Add a test mirroring `tests/test_llm_factory.py::test_build_provider_*`.

No CLI script needs to change; they all depend on the `LLMProvider` ABC.

## Project layout

```
stack_hub/
├── pyproject.toml             # build, ruff, mypy, pytest config
├── requirements.txt
├── .env.example
├── corpus/                    # human-source posts (PLACEHOLDER until replaced)
├── voice/                     # voice_map, brand_promise, kill list
├── prompts/                   # master_system_prompt, detector prompt
├── libraries/                 # hook_library, structure_library
├── briefs/                    # one .md per upcoming post
├── drafts/                    # drafts/{post_id}_v{n}.md
├── published/                 # successfully published drafts
├── data/                      # posts.json + config.json (schema = Pydantic models.py)
├── rituals/                   # RITUALS.md (all 4 cadences + retention checklist)
│   └── audits/                # monthly + daily reports
├── growth/                    # PHASE_4_ROADMAP.md
├── scripts/                   # CLI entry points + pipeline package
└── tests/                     # 73+ tests, pytest
```

## Testing

```bash
python -m pytest                       # all tests
python -m pytest -k repository         # subset
python -m pytest --cov=scripts/pipeline   # with coverage (requires pytest-cov)
```

## Phase 4 monetization

Read `growth/PHASE_4_ROADMAP.md` only when the trust-account checklist is
met. Do not build paid infrastructure ahead of trust.

## Known limitations

- The bundled corpus is **placeholder** content (clearly marked in each
  file). For real publishing, drop authentic source posts into
  `corpus/{writer}/` and re-run `extract_voice.py`.
- Calibration is sprint-grade AI-as-judge. A real human panel is more
  reliable; treat the 70% gate as a smoke test, not a quality bar.
- Single-brand. Multi-brand support would require threading a `--brand`
  argument through the CLI scripts and namespacing `data/`.
- Pipeline is human-gated by design. There is no auto-publish; this is
  a feature, not a missing piece.

## Recommended next 30 days

1. Drop a real corpus into `corpus/`.
2. Re-run `python scripts/extract_voice.py` to refresh `voice/voice_map.md`.
3. Run `python scripts/calibrate.py` end-to-end and verify <70%.
4. Ship 4 posts on cadence (one per week).
5. Run `pattern_audit.py` and `health_check.py` weekly.
6. After 30 days, run the monthly pattern audit and decide which 2 hook
   patterns and frameworks to retire/try next.
