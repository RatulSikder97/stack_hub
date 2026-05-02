#!/usr/bin/env bash
# Container entrypoint: seed /data on first run, fix perms, drop to non-root.
set -euo pipefail

DATA_DIR="${STACK_HUB_ROOT:-/data}"
SEED_DIR="/seed"
RUN_AS="${RUN_AS:-stackhub}"

mkdir -p \
    "$DATA_DIR/corpus" \
    "$DATA_DIR/voice" \
    "$DATA_DIR/prompts" \
    "$DATA_DIR/libraries" \
    "$DATA_DIR/briefs" \
    "$DATA_DIR/drafts" \
    "$DATA_DIR/published" \
    "$DATA_DIR/data" \
    "$DATA_DIR/rituals/audits" \
    "$DATA_DIR/growth"

# First-run seed: copy default content into /data only when missing.
# `cp -n` (no-clobber) means existing user edits are never overwritten.
if [[ -d "$SEED_DIR" ]]; then
    if [[ ! -f "$DATA_DIR/data/config.json" ]]; then
        echo "stack-hub: seeding $DATA_DIR from $SEED_DIR (first run)"
    fi
    # Use cp -rn so re-runs are no-ops if files already exist.
    if command -v rsync >/dev/null 2>&1; then
        rsync -a --ignore-existing "$SEED_DIR/" "$DATA_DIR/"
    else
        cp -rn "$SEED_DIR/." "$DATA_DIR/"
    fi
fi

# Initialize empty posts.json so the repository can read on first call.
if [[ ! -f "$DATA_DIR/data/posts.json" ]]; then
    echo "[]" > "$DATA_DIR/data/posts.json"
fi

# Fix ownership — Docker mounts come up root-owned by default.
chown -R "$RUN_AS:$RUN_AS" "$DATA_DIR"

# If we are already non-root, just exec; otherwise drop privileges via gosu.
if [[ "$(id -u)" -eq 0 ]]; then
    exec gosu "$RUN_AS" "$@"
fi
exec "$@"
