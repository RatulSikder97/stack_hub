#!/usr/bin/env bash
# =============================================================================
# One-shot server bootstrap — no `git clone` required.
#
# Pulls just the three files we need (compose + Caddyfile + env template),
# generates random auth secrets, and starts the stack. The container image
# itself is pulled from GHCR (built by the CI workflow on every merge to main).
#
# Usage:
#   sudo IMAGE=ghcr.io/you/stack-hub:latest \
#        DOMAIN=studio.example.com \
#        ACME_EMAIL=you@example.com \
#        bash bootstrap.sh
#
# Or run interactively — the script will prompt for missing values.
# =============================================================================

set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/stackhub}"
RAW_BASE="${RAW_BASE:-https://raw.githubusercontent.com/${REPO:-yourname/stack-hub}/main}"

log() { printf '\n\033[1;36m==>\033[0m %s\n' "$*"; }
err() { printf '\033[1;31m!!\033[0m %s\n' "$*" >&2; }

if [[ $EUID -ne 0 ]]; then
    err "Run with sudo (so the install directory + Docker can be set up)."
    exit 1
fi

# ---- Inputs ----
read_value() {
    local var="$1" prompt="$2" default="${3:-}"
    if [[ -z "${!var:-}" ]]; then
        if [[ -n "$default" ]]; then
            read -rp "$prompt [$default]: " value
            value="${value:-$default}"
        else
            read -rp "$prompt: " value
        fi
        printf -v "$var" '%s' "$value"
    fi
}

read_value IMAGE       "Image (e.g. ghcr.io/you/stack-hub:latest)"
read_value DOMAIN      "Public domain (must already point at this server)"
read_value ACME_EMAIL  "Email for Let's Encrypt notices" "admin@$DOMAIN"

# ---- Install Docker if missing ----
if ! command -v docker >/dev/null 2>&1; then
    log "Installing Docker"
    curl -fsSL https://get.docker.com | sh
    systemctl enable --now docker
fi

# ---- Layout ----
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

log "Fetching compose + Caddyfile + env template from $RAW_BASE"
curl -fsSL "$RAW_BASE/docker-compose.yml" -o docker-compose.yml
curl -fsSL "$RAW_BASE/Caddyfile"          -o Caddyfile

if [[ ! -f .env ]]; then
    curl -fsSL "$RAW_BASE/deploy/docker.env.example" -o .env

    # Auto-fill image / domain / email
    sed -i "s|^IMAGE=.*|IMAGE=$IMAGE|" .env
    sed -i "s|^DOMAIN=.*|DOMAIN=$DOMAIN|" .env
    sed -i "s|^ACME_EMAIL=.*|ACME_EMAIL=$ACME_EMAIL|" .env

    # Generate auth secrets
    ADMIN_PASS=$(openssl rand -base64 18 | tr -d '/+=' | head -c 20)
    USER_PASS=$(openssl rand -base64 18 | tr -d '/+=' | head -c 20)
    AUTH_SECRET=$(openssl rand -hex 32)
    sed -i "s|^ADMIN_PASSWORD=.*|ADMIN_PASSWORD=$ADMIN_PASS|" .env
    sed -i "s|^USER_PASSWORD=.*|USER_PASSWORD=$USER_PASS|" .env
    sed -i "s|^AUTH_SECRET=.*|AUTH_SECRET=$AUTH_SECRET|" .env

    chmod 600 .env

    cat <<EOF

================================================================
  Generated $INSTALL_DIR/.env. Credentials below — copy to a
  password manager NOW; they will not be shown again.

    Admin login : admin / $ADMIN_PASS
    User login  : user  / $USER_PASS

  Add your LLM API key (e.g. GEMINI_API_KEY) before continuing:
    sudo nano $INSTALL_DIR/.env
================================================================
EOF
    read -rp "Press Enter once you've added the LLM key…"
fi

log "Pulling image $IMAGE"
docker compose pull

log "Starting stack"
docker compose up -d

log "Waiting for healthcheck"
for i in {1..15}; do
    state=$(docker inspect --format='{{.State.Health.Status}}' stackhub 2>/dev/null || echo "starting")
    if [[ "$state" == "healthy" ]]; then break; fi
    sleep 2
done

log "Done. Check logs with:  docker compose -f $INSTALL_DIR/docker-compose.yml logs -f"
log "Open: https://$DOMAIN"
