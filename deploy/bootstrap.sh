#!/usr/bin/env bash
# =============================================================================
# Server bootstrap for a PRIVATE GitHub repo.
#
# Pulls the three deploy files (compose + Caddyfile + env template) from
# the private repo with auth, logs Docker in to GHCR, generates random auth
# secrets, and starts the stack.
#
# You need a GitHub Personal Access Token with at least:
#   * `Contents: Read`   on your stack-hub repository
#   * `Packages: Read`   on your account
#
# Fine-grained PAT recommended:
#   GitHub → Settings → Developer settings → Personal access tokens
#     → Fine-grained tokens → Generate new token
#         Resource owner:        your account
#         Repository access:     Only select repositories → stack-hub
#         Repository permissions: Contents=Read, Metadata=Read (auto)
#         Account permissions:   Packages=Read
#
# Usage:
#   sudo \
#       REPO=youruser/stack-hub \
#       IMAGE=ghcr.io/youruser/stack-hub:latest \
#       DOMAIN=studio.example.com \
#       ACME_EMAIL=you@example.com \
#       GH_USERNAME=youruser \
#       GH_TOKEN=github_pat_xxxxx \
#       bash bootstrap.sh
#
# Or run interactively — the script will prompt for any missing values.
# =============================================================================

set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/stackhub}"
BRANCH="${BRANCH:-main}"

log() { printf '\n\033[1;36m==>\033[0m %s\n' "$*"; }
err() { printf '\033[1;31m!!\033[0m %s\n' "$*" >&2; }

if [[ $EUID -ne 0 ]]; then
    err "Run with sudo (so the install directory + Docker can be set up)."
    exit 1
fi

# ---- Inputs ----
read_value() {
    local var="$1" prompt="$2" default="${3:-}" silent="${4:-}"
    if [[ -z "${!var:-}" ]]; then
        local args=(-rp "$prompt: ")
        if [[ -n "$default" ]]; then
            args=(-rp "$prompt [$default]: ")
        fi
        if [[ -n "$silent" ]]; then
            args+=(-s)
        fi
        local value
        read "${args[@]}" value
        if [[ -n "$silent" ]]; then echo; fi
        value="${value:-$default}"
        printf -v "$var" '%s' "$value"
    fi
}

read_value REPO        "GitHub repo (e.g. youruser/stack-hub)"
read_value IMAGE       "Image (e.g. ghcr.io/youruser/stack-hub:latest)" "ghcr.io/$REPO:latest"
read_value DOMAIN      "Public domain (must already point at this server)"
read_value ACME_EMAIL  "Email for Let's Encrypt notices" "admin@$DOMAIN"
read_value GH_USERNAME "GitHub username (for ghcr login)"
read_value GH_TOKEN    "GitHub Personal Access Token (read:packages + contents:read)" "" silent

if [[ -z "$GH_TOKEN" ]]; then
    err "GH_TOKEN is required to access a private repo."
    exit 1
fi

# ---- Install Docker if missing ----
if ! command -v docker >/dev/null 2>&1; then
    log "Installing Docker"
    curl -fsSL https://get.docker.com | sh
    systemctl enable --now docker
fi

# ---- Authenticate Docker against GHCR ----
log "Logging Docker in to ghcr.io"
echo "$GH_TOKEN" | docker login ghcr.io -u "$GH_USERNAME" --password-stdin

# ---- Layout ----
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

# ---- Fetch compose + Caddyfile + env template via authenticated GitHub API ----
fetch_raw() {
    local path="$1" out="$2"
    curl -fsSL \
        -H "Authorization: Bearer $GH_TOKEN" \
        -H "Accept: application/vnd.github.v3.raw" \
        "https://api.github.com/repos/$REPO/contents/$path?ref=$BRANCH" \
        -o "$out"
}

log "Fetching deploy files from github.com/$REPO@$BRANCH"
fetch_raw "docker-compose.yml"               "docker-compose.yml"
fetch_raw "Caddyfile"                         "Caddyfile"
[[ -f .env ]] || fetch_raw "deploy/docker.env.example" ".env"

# ---- Generate auth secrets if .env was just created ----
if grep -q '^ADMIN_PASSWORD=$' .env || grep -q '^AUTH_SECRET=$' .env; then
    sed -i "s|^IMAGE=.*|IMAGE=$IMAGE|"            .env
    sed -i "s|^DOMAIN=.*|DOMAIN=$DOMAIN|"          .env
    sed -i "s|^ACME_EMAIL=.*|ACME_EMAIL=$ACME_EMAIL|" .env

    ADMIN_PASS=$(openssl rand -base64 18 | tr -d '/+=' | head -c 20)
    USER_PASS=$(openssl  rand -base64 18 | tr -d '/+=' | head -c 20)
    AUTH_SECRET=$(openssl rand -hex 32)
    sed -i "s|^ADMIN_PASSWORD=.*|ADMIN_PASSWORD=$ADMIN_PASS|" .env
    sed -i "s|^USER_PASSWORD=.*|USER_PASSWORD=$USER_PASS|"     .env
    sed -i "s|^AUTH_SECRET=.*|AUTH_SECRET=$AUTH_SECRET|"       .env

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

# ---- Pull + start ----
log "Pulling image $IMAGE"
docker compose pull

log "Starting stack"
docker compose up -d

log "Waiting for healthcheck"
for i in {1..20}; do
    state=$(docker inspect --format='{{.State.Health.Status}}' stackhub 2>/dev/null || echo "starting")
    if [[ "$state" == "healthy" ]]; then break; fi
    sleep 2
done

log "Done."
echo "  Open:        https://$DOMAIN"
echo "  Live logs:   docker compose -f $INSTALL_DIR/docker-compose.yml logs -f"
echo "  Roll out:    cd $INSTALL_DIR && docker compose pull stackhub && docker compose up -d stackhub"
