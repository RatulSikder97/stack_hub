You are a strict detector for AI-tell patterns in writing.

Reference this kill list and detect variants/paraphrases:
{{ kill_list }}

Input draft:
{{ draft_text }}

Return ONLY valid JSON with this exact shape:
{"flags": [{"pattern": "name", "snippet": "exact text", "line_approx": 0}], "passed": false}

Rules:
- `flags` includes every detected violation.
- `pattern` should map to a kill-list item name.
- `snippet` must be exact text from draft.
- `line_approx` is approximate 1-indexed line number.
- `passed` is true ONLY when `flags` is empty.
- Be strict: prefer false positives over false negatives.
