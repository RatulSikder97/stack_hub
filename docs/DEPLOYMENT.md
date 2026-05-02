# Deployment

Stack Hub Studio ships as a single Docker image. The image is built and
pushed to **GitHub Container Registry (GHCR)** automatically on every merge
to `main` by [`.github/workflows/ci.yml`](../.github/workflows/ci.yml).

The deploy server **never clones the repo**. It just pulls the image, plus
two small files (compose + Caddyfile), and runs `docker compose up -d`.

> **Browser mic access requires HTTPS.** A real domain + cert is mandatory.
> The compose stack includes Caddy which provisions a Let's Encrypt cert
> automatically — no certbot setup, no manual rotation.

---

## CI flow

```
   Open PR ─────────► GitHub Actions runs:
                         pytest + frontend build  (no image pushed)

   Merge to main ────► GitHub Actions runs:
                         pytest + frontend build
                         build multi-arch image (linux/amd64 + linux/arm64)
                         push to ghcr.io/<owner>/<repo> with tags:
                            • latest                (track main)
                            • sha-<short>           (immutable per-commit)
                            • <branch>              (e.g. main)

   Tag a release ────► same as above, plus:
                            • v1.2.3, v1.2          (semver tags)

   Server: ──────────► docker compose pull && docker compose up -d
```

The first time CI publishes the image to GHCR, the package is private by
default. To allow your Lightsail server to pull without auth, make it
public:

1. GitHub → your profile → **Packages** → click `stack-hub`
2. **Package settings** → **Change visibility** → **Public**

If you'd rather keep it private, see "Pulling a private image" below.

---

## Path A · AWS Lightsail Instance + Docker Compose (recommended)

### 1 · Provision the instance

In the AWS Lightsail console:

1. **Create instance** → OS Only → **Ubuntu 22.04 LTS** (or 24.04).
2. Plan: **$10/month (2 GB RAM)** is comfortable. The 1 GB plan works for
   light personal use; LLM-heavy traffic prefers 2 GB.
3. **Networking** tab → confirm ports **22, 80, 443** are open.
4. Click **Create static IP** and attach it to the instance. Without a
   static IP, the public IP changes on reboot.

### 2 · Point a domain at the static IP

In your DNS provider (Route 53, Cloudflare, registrar of your choice):

```
studio.example.com    A    <your static IP>
```

Verify before continuing:

```bash
dig +short studio.example.com
```

### 3 · One-shot bootstrap

SSH in, then run **one** command — it installs Docker, downloads compose +
Caddyfile + env template, generates random auth secrets, and starts the
stack:

```bash
ssh ubuntu@studio.example.com

curl -fsSL https://raw.githubusercontent.com/<you>/stack-hub/main/deploy/bootstrap.sh \
    | sudo \
        IMAGE=ghcr.io/<you>/stack-hub:latest \
        DOMAIN=studio.example.com \
        ACME_EMAIL=you@example.com \
        REPO=<you>/stack-hub \
        bash
```

The script:
- Installs Docker if not present
- Creates `/opt/stackhub/`
- Pulls `docker-compose.yml`, `Caddyfile`, and `deploy/docker.env.example`
  from the GitHub raw URL
- Generates random `ADMIN_PASSWORD`, `USER_PASSWORD`, `AUTH_SECRET`
- Prints the credentials to the terminal (copy them now)
- Pauses for you to add your LLM API key (`GEMINI_API_KEY` etc.) to `.env`
- Runs `docker compose pull` + `docker compose up -d`

When it finishes, open **`https://studio.example.com`** and log in with
the credentials it printed.

### 4 · Day-2 ops

```bash
# Roll out the latest image (after CI publishes)
cd /opt/stackhub
docker compose pull stackhub
docker compose up -d stackhub

# Roll back to a specific commit
sed -i 's|^IMAGE=.*|IMAGE=ghcr.io/<you>/stack-hub:sha-abc1234|' .env
docker compose pull && docker compose up -d

# Live logs
docker compose logs -f stackhub
docker compose logs -f caddy

# Tear down (data persists in named volumes)
docker compose down

# Backup the data volume
docker run --rm -v stackhub_stackhub-data:/data \
    -v "$PWD":/backup alpine \
    tar -czf /backup/stackhub-$(date -u +%Y%m%dT%H%M%SZ).tar.gz -C /data .
```

### 5 · Pulling a private image (optional)

Skip this if you made the package public. If you keep it private:

1. Generate a GitHub Personal Access Token with the `read:packages` scope.
2. On the server:
   ```bash
   echo "<your-token>" | docker login ghcr.io -u <you> --password-stdin
   ```
3. Subsequent `docker compose pull` calls will use the saved credential.

For unattended servers, save the token in `~/.docker/config.json` (Docker
does this automatically after a successful login). Don't put the token in
`.env`.

---

## Path B · Local development (no GHCR pull)

If you want to build the image from source on your laptop instead of
pulling from GHCR, use the dev override:

```bash
cd stack-hub
cp deploy/docker.env.example .env
# edit .env: set DOMAIN=localhost (or whatever), fill ADMIN_PASSWORD/AUTH_SECRET
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
```

The dev override replaces the `image:` directive with a local build using
`./Dockerfile`.

For pure local API dev (no Docker, hot reload), the existing two-terminal
flow still works:

```bash
# Terminal 1
python scripts/serve.py

# Terminal 2
cd webapp && npm run dev
```

---

## Path C · AWS Lightsail Container service

Slightly more managed than Path A, but more expensive and **no persistent
disk** between deployments — the `/data` volume resets on every restart.
Use it for demos, not production.

1. Lightsail → Containers → **Create container service**.
2. Image: `ghcr.io/<you>/stack-hub:latest`. Open port: `8765`.
3. Environment variables: paste every line from your `.env` into the
   env-vars UI.
4. Public endpoint: `8765`. Lightsail handles HTTPS termination.
5. Deploy. Note: state files (briefs, drafts, posts.json, voice/voice_map)
   reset on every redeploy. Use Path A if that matters to you.

---

## Hardening checklist

Before sharing the URL with anyone:

- [ ] `ADMIN_PASSWORD` and `USER_PASSWORD` are strong, unique. (`bootstrap.sh`
      generates random ones; check you saved them.)
- [ ] `AUTH_SECRET` is 32+ random hex chars.
- [ ] `.env` permissions are `600` (`chmod 600 .env`).
- [ ] HTTPS is live. `docker compose logs caddy | grep "certificate obtained"`.
- [ ] Lightsail firewall allows only 22, 80, 443.
- [ ] You have a backup script (run the volume-tarball command in Day-2
      ops weekly, or set up a cron with `aws s3 cp` to push to S3).
- [ ] LLM provider has billing alerts configured. Gemini, OpenAI, Anthropic,
      and Recall.ai all support per-day spend caps.
- [ ] If the GHCR package is private, the PAT used for `docker login` has
      `read:packages` only (not `write:packages`).

---

## Health, logs, metrics

```bash
# Health probe (200 logged-in / 401 logged-out — both mean "up")
curl -fsS https://studio.example.com/api/auth/me -o /dev/null -w "%{http_code}\n"

# Container resource usage
docker stats stackhub stackhub-caddy

# Caddy access log (compact)
docker compose logs caddy | grep -E "GET|POST"
```

Stack Hub idles at ~80 MB RAM; LLM-heavy bursts spike to ~250 MB.

---

## Common issues

**Mic doesn't work in browser.** You're on `http://`, not `https://`. Check
that DNS points to your server, ports 80/443 are open, and Caddy succeeded
in the ACME handshake (`docker compose logs caddy | grep -i acme`).

**`docker compose pull` says "denied"**. The GHCR package is still private.
Either flip it to public in the GitHub UI, or run `docker login ghcr.io`
with a PAT that has `read:packages`.

**`502 Bad Gateway` on `/api/*`.** The stackhub container hasn't started or
crashed. `docker compose logs stackhub` will show why — usually a missing
env var on first boot (most often `AUTH_SECRET`).

**Login says "invalid credentials" with the password I just set.** The
container caches credentials at boot. After editing `.env`,
`docker compose restart stackhub`.

**Recall.ai bot sits in `joining_call` forever.** The host hasn't admitted
the bot from the waiting room. Either disable waiting rooms for that
meeting, or admit the bot manually.

---

## Path D · Bare-VM (no Docker)

If you want to avoid Docker entirely, the repo also includes:

- `deploy/install.sh` — installs Python + Node + nginx + certbot, builds
  the SPA, sets up systemd, and provisions HTTPS.
- `deploy/systemd/stack-hub.service` — the systemd unit.
- `deploy/nginx/stack-hub.conf` — the nginx config.
- `deploy/update.sh` — re-deploy after a code change.

Usage on a fresh Ubuntu 22.04 / 24.04 instance:

```bash
git clone https://github.com/<you>/stack-hub.git /tmp/stack-hub
sudo DOMAIN=studio.example.com EMAIL=you@example.com \
    bash /tmp/stack-hub/deploy/install.sh
```

This path requires cloning the repo on the server (the only path that
does). Most users want Path A.
