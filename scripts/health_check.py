#!/usr/bin/env python3
from __future__ import annotations

import subprocess
from datetime import datetime, timezone

from common import ROOT, load_posts


def score_color(value: float, green_at: float, yellow_at: float, inverse: bool = False) -> str:
    if inverse:
        if value <= green_at:
            return "green"
        if value <= yellow_at:
            return "yellow"
        return "red"
    if value >= green_at:
        return "green"
    if value >= yellow_at:
        return "yellow"
    return "red"


def main() -> None:
    posts = load_posts()
    published = [p for p in posts if p.status == "published"]
    recent = posts[-10:]

    diversity = len({p.hook_pattern_used for p in published if p.hook_pattern_used}) + len(
        {p.structural_framework_used for p in published if p.structural_framework_used}
    )
    diversity_color = score_color(float(diversity), green_at=6, yellow_at=3)

    cadence_out = subprocess.run(
        ["python3", str(ROOT / "scripts" / "cadence_check.py")], capture_output=True, text=True, check=False
    )
    cadence_text = cadence_out.stdout.strip() or cadence_out.stderr.strip()
    cadence_color = "green" if "ON TRACK" in cadence_text else "yellow" if "SLIPPING" in cadence_text else "red"

    flags_per_draft = sum(0 if p.ai_tells_check_passed else 1 for p in recent) / max(len(recent), 1)
    flags_color = score_color(flags_per_draft, green_at=0.2, yellow_at=0.5, inverse=True)

    retention_pass_rate = sum(1 for p in recent if p.human_edit_completed) / max(len(recent), 1)
    retention_color = score_color(retention_pass_rate, green_at=0.8, yellow_at=0.5)

    report = [
        f"# Health Check - {datetime.now(timezone.utc):%Y-%m-%d}",
        "",
        f"- Rotation diversity: {diversity} ({diversity_color})",
        f"- Cadence: {cadence_color}",
        f"- Avg AI tells flags per draft (proxy): {flags_per_draft:.2f} ({flags_color})",
        f"- Retention check pass rate (last 10): {retention_pass_rate:.2%} ({retention_color})",
        "",
        "## Cadence Output",
        cadence_text,
    ]

    out = ROOT / "rituals" / "audits" / f"{datetime.now(timezone.utc):%Y-%m-%d}_health.md"
    out.write_text("\n".join(report) + "\n")
    print(f"Health report written: {out}")


if __name__ == "__main__":
    main()
