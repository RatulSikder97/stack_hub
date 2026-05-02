#!/usr/bin/env bash
# Re-deploy after a code change. Pulls latest from git (or rsyncs from a local
# clone if REPO is unset), reinstalls deps, rebuilds the React app, restarts
# the service. Does NOT touch /opt/stack-hub/.env.

set -euo pipefail

INSTALL_DIR="/opt/stack-hub"
REPO="${REPO:-}"

if [[ $EUID -ne 0 ]]; then
    echo "Run with sudo." >&2
    exit 1
fi

log() { printf '\n\033[1;36m==>\033[0m %s\n' "$*"; }

if [[ -n "$REPO" ]]; then
    log "Pulling latest from $REPO"
    if [[ -d "$INSTALL_DIR/.git" ]]; then
        git -C "$INSTALL_DIR" fetch --all
        git -C "$INSTALL_DIR" reset --hard origin/main
    else
        echo "$INSTALL_DIR is not a git checkout; either set REPO_LOCAL=/path/to/clone or re-run install.sh"
        exit 1
    fi
elif [[ -n "${REPO_LOCAL:-}" ]]; then
    log "rsync'ing from $REPO_LOCAL"
    rsync -a --delete \
        --exclude '.git' \
        --exclude '.venv' \
        --exclude '.env' \
        --exclude 'webapp/node_modules' \
        --exclude 'webapp/dist' \
        --exclude '__pycache__' \
        "$REPO_LOCAL/" "$INSTALL_DIR/"
else
    echo "Set REPO=https://github.com/.../stack-hub or REPO_LOCAL=/path/to/clone" >&2
    exit 1
fi

log "Updating Python deps"
"$INSTALL_DIR/.venv/bin/pip" install --quiet -r "$INSTALL_DIR/requirements.txt"

log "Rebuilding React app"
cd "$INSTALL_DIR/webapp"
npm ci --silent
npm run build
cd "$INSTALL_DIR"

chown -R stackhub:stackhub "$INSTALL_DIR"

log "Restarting service"
systemctl restart stack-hub
systemctl status stack-hub --no-pager --lines=8

log "Done."
