# Rituals

The four cadenced rituals that keep the pipeline honest, plus the human
retention checklist that gates publishing.

## Daily Idea Grooming (15 min)

1. Review `status="idea"` records in `data/posts.json`.
2. Promote one to brief: `python scripts/new_brief.py --title "..."`.
3. Confirm tomorrow's drafting context and rotation variety.
4. Ensure one fresh brief is ready before ending.

## Weekly Postmortem (90 min, publish day +1)

1. Pull metrics manually from Substack.
2. Run `python scripts/log_metrics.py` for the latest post.
3. Capture what landed (specific phrases and structural choices).
4. Capture what did not and best-guess why.
5. Promote two new ideas to brief.
6. Confirm the next post is at least draft v1.

## Monthly Pattern Audit (30 min)

1. Run `python scripts/pattern_audit.py`.
2. Review latest report in `rituals/audits/`.
3. Retire two over-used patterns for next 30 days.
4. Deliberately test two under-used patterns next month.

## Quarterly Voice Drift Gate (2 hr)

1. Re-run `python scripts/calibrate.py` on last 10 published posts vs.
   10 fresh corpus samples.
2. If detection ≥30%, voice has drifted.
3. Refresh `voice/voice_map.md` (run `python scripts/extract_voice.py`)
   and tighten `prompts/master_system_prompt.md` if needed.
4. Do not publish new posts until calibration returns under 30%.

## Retention Check (per draft, before publish)

Run via `python scripts/retention_check.py --post-id {post_id}`. All four
must answer yes:

1. Open loop set in para 2, resolved in para 6+.
2. Pattern interrupts every 200–300 words (one-line para, question, fragment).
3. "Wait, what?" buried sentence two-thirds in.
4. Closing line is screenshot-able (deleted first 3 attempts before settling).

If any are no, the draft is not ready. The script blocks status from
advancing until all four pass.
