# Post Schema

- `post_id`: Stable ID (`YYYYMMDD-slug`).
- `working_title`: Human working title for the post.
- `niche`: Selected niche for topic constraints.
- `hook_pattern_used`: Hook pattern chosen for opening.
- `structural_framework_used`: Framework chosen for structure.
- `status`: One of `idea|brief|drafting|ai_tells_pass|editing|retention_check|scheduled|published`.
- `publish_date`: Planned publish date.
- `open_loop_resolved`: Whether early open loop was resolved.
- `ai_tells_check_passed`: AI-tells gate result.
- `human_edit_completed`: Human edit + retention confirmation status.
- `share_count`: Shares captured from analytics.
- `open_rate`: Open rate percentage.
- `substack_url`: Published Substack URL.
- `created_at`: Record creation timestamp (ISO 8601).
- `published_at`: Actual published timestamp (ISO 8601).
- `retention_check_answers`: Array of retention checklist answers.
