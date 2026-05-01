# Stack Hub — Substack Pipeline

## Project purpose
This project runs a lightweight, human-gated writing pipeline that takes an idea from brief to publish while preserving voice, enforcing anti-AI-tell checks, and tracking output quality over time.

## IDEA -> PUBLISH workflow
1. Create brief: `python scripts/new_brief.py --title "..."`
2. Fill brief manually in `briefs/{post_id}.md`
3. Draft post: `python scripts/draft_post.py --post-id {post_id}`
4. AI-tells check: `python scripts/run_ai_tells.py drafts/{post_id}_v1.md`
5. Human edit + retention gate: `python scripts/retention_check.py --post-id {post_id}`
6. Publish to Substack manually, then log: `python scripts/log_publish.py --post-id {post_id}`
7. Log metrics later: `python scripts/log_metrics.py --post-id {post_id} --open-rate 45.2 --share-count 18`

## Rituals
- Daily (15 min): `rituals/daily_idea_grooming.md`
- Weekly (90 min): `rituals/weekly_postmortem.md`
- Monthly: `rituals/monthly_pattern_audit.md`
- Quarterly: `rituals/quarterly_voice_drift.md`

## How to add a new post
1. Run `new_brief.py`.
2. Complete strategy fields in the brief.
3. Run `draft_post.py`.
4. Pass detector.
5. Human edit + retention check.
6. Publish in Substack and log publication.

## Handling voice drift
Follow `rituals/quarterly_voice_drift.md` and recalibrate before publishing if drift exceeds the gate.

## Phase 4 monetization
Read `growth/PHASE_4_ROADMAP.md` only when trust-account conditions are met.

## Known limitations
- Corpus currently placeholder until human uploads source posts.
- Calibration is sprint-grade AI-as-judge.
- No live post shipped in this one-shot bootstrap.
- Single-brand flow only.

## Next 30 days
Ship 4 posts, run weekly postmortems, run first monthly pattern audit at day 30, and expand corpus opportunistically.
