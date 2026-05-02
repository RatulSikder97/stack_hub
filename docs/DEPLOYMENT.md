# Deployment

Stack Hub Studio ships as a single Docker image. Two recommended hosts:

1. **AWS Lightsail Instance + Docker Compose** (recommended, $5–10/month) — you
   get a real VPS, full control, automated HTTPS via Caddy, one command to
   upgrade. This guide covers it end-to-end.
2. **AWS Lightsail Containers** ($7+ minimum) — managed runtime, no server
   to maintain, but more expensive and you push images to ECR or DockerHub.
3. **Self-hosted on any Docker host** (your own VPS, Hetzner, etc.) — same
   compose stack, just point your domain at the box.

> **Browser mic access requires HTTPS.** A real domain + cert is mandatory if
> you want the voice recorder to work for users other than yourself.

---

## Recommended path: Lightsail Instance + Docker

### 1 · Provision the instance

In the AWS Lightsail console:

1. **Create instance** → OS Only → **Ubuntu 22.04 LTS** (or 24.04).
2. Plan: **$10/month (2 GB RAM)** is comfortable. $5/mo (1 GB) works for
   light personal use; LLM-heavy traffic prefers 2 GB.
3. Launch.
4. Open the instance → **Networking** tab → ensure ports 22 (TCP), 80 (TCP),
   and 443 (TCP) are allowed.
5. Click **Create static IP** and attach it to your instance. Without a
   static IP, the public IP changes on reboot.

### 2 · Point a domain at the instance

You can use Lightsail's domain feature, Route 53, Cloudflare, or any
registrar. Add a single **A record**:

```
studio.example.com    A    <your static IP>
```

DNS propagation typically takes a few minutes. Verify with:

```bash
dig +short studio.example.com
```

### 3 · SSH in and install Docker

```bash
ssh ubuntu@studio.example.com
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker ubuntu
exit                # log out and back in so the group takes effect
ssh ubuntu@studio.example.com
docker --version    # confirm
```

### 4 · Clone the repo and configure secrets

```bash
sudo mkdir -p /opt/stackhub && sudo chown ubuntu /opt/stackhub
cd /opt/stackhub
git clone https://github.com/<you>/stack-hub.git .

# Generate a secure .env in place. Edit the values you care about.
cat > .env <<'EOF'
DOMAIN=studio.example.com
ACME_EMAIL=you@example.com

# --- LLM provider (pick one) ---
LLM_PROVIDER=gemini
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash-lite

OPENAI_API_KEY=
OPENAI_MODEL=gpt-4.1
ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=claude-opus-4-7
NOVITA_API_KEY=
NOVITA_MODEL=meta-llama/llama-3.3-70b-instruct
NOVITA_BASE_URL=https://api.novita.ai/v3/openai

LLM_MAX_TOKENS_DRAFT=8000
LLM_MAX_TOKENS_DETECTOR=8000
LLM_MAX_TOKENS_VOICE=4000
LLM_TEMPERATURE=0.7

# --- Auth (CHANGE THESE) ---
ADMIN_USERNAME=admin
ADMIN_PASSWORD=
USER_USERNAME=user
USER_PASSWORD=
AUTH_SECRET=
AUTH_SESSION_DAYS=30

# Optional: real-time meeting bot
RECALL_API_KEY=
EOF

# Fill in random values for the auth fields. Don't skip this.
ADMIN_PASS=$(openssl rand -base64 18 | tr -d '/+=' | head -c 20)
USER_PASS=$(openssl rand -base64 18 | tr -d '/+=' | head -c 20)
AUTH_SECRET=$(openssl rand -hex 32)
sed -i "s/^ADMIN_PASSWORD=.*/ADMIN_PASSWORD=${ADMIN_PASS}/" .env
sed -i "s/^USER_PASSWORD=.*/USER_PASSWORD=${USER_PASS}/"   .env
sed -i "s/^AUTH_SECRET=.*/AUTH_SECRET=${AUTH_SECRET}/"     .env

# Show the credentials ONCE — copy them to a password manager now.
echo
echo "ADMIN: admin / $ADMIN_PASS"
echo "USER : user  / $USER_PASS"
echo
chmod 600 .env
```

Open `.env` in `nano` and paste your real LLM API key and (optionally)
`RECALL_API_KEY` for the meeting bot.

### 5 · Bring it up

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f stackhub
```

The first `up -d --build` builds the image and starts both services. Caddy
provisions a Let's Encrypt cert for `$DOMAIN` automatically — watch
`docker compose logs caddy` for the cert acquisition.

Open **`https://studio.example.com`** in your browser. You'll be redirected
to `/login`. Use the `admin` credentials from step 4.

### 6 · Day-2 ops

```bash
# Roll out new code
cd /opt/stackhub
git pull
docker compose up -d --build

# View live logs
docker compose logs -f stackhub
docker compose logs -f caddy

# Restart just the API after a config change
docker compose restart stackhub

# Tear it down (data persists in named volumes)
docker compose down

# Inspect the data volume
docker volume ls
docker run --rm -v stackhub_stackhub-data:/data alpine ls /data

# Back up the data volume to a tarball
docker run --rm -v stackhub_stackhub-data:/data \
    -v "$PWD":/backup alpine \
    tar -czf /backup/stackhub-data-$(date -u +%Y%m%dT%H%M%SZ).tar.gz -C /data .
```

### 7 · Hardening checklist

Before sharing the URL with anyone:

- [ ] `ADMIN_PASSWORD` and `USER_PASSWORD` are strong, unique, and not the
      defaults.
- [ ] `AUTH_SECRET` is 32+ random hex chars (the snippet above does this).
- [ ] `.env` permissions are `600` (`chmod 600 .env`).
- [ ] HTTPS is live (Caddy's logs say "certificate obtained successfully").
- [ ] Lightsail firewall allows only 22, 80, 443.
- [ ] You have a backup (run the volume-tarball command in step 6 weekly,
      or set up a cron with `aws s3 cp` to push to S3).
- [ ] LLM provider has billing alerts set (Gemini, OpenAI, Anthropic, and
      Recall.ai all support this).

---

## Alternative: Lightsail Container Service

Skip if Docker Compose on an instance feels right; this path is more
managed but more expensive.

1. Build and tag the image locally:
   ```bash
   docker build -t stackhub:1.0.0 .
   ```
2. Push to a registry (Docker Hub, ECR, or GHCR):
   ```bash
   docker tag stackhub:1.0.0 ghcr.io/<you>/stackhub:1.0.0
   docker push ghcr.io/<you>/stackhub:1.0.0
   ```
3. In Lightsail → Containers → **Create container service** → Power: small,
   Scale: 1, Public domain: enable.
4. Image: `ghcr.io/<you>/stackhub:1.0.0`. Open port: `8765`.
5. Public endpoint: `8765`. Lightsail Containers handles HTTPS termination
   for you with their generated `.cs.amazonlightsail.com` URL, or attach
   your own domain.
6. Environment variables: copy every line from `.env` into the env-vars UI.
7. Persistent storage: Lightsail Container service does **not** persist disk
   between deployments — the `/data` volume resets on every container
   restart. For real persistence, switch to the Compose-on-Instance path
   above, or mount Lightsail Block Storage in EC2 / ECS instead.

> **Heads-up:** because of the persistence limitation, the Container
> Service path is best for *demos* and *evaluation*, not production. Most
> users want the Compose-on-Instance path.

---

## Alternative: bare-VM (no Docker)

If you want to avoid Docker entirely, the repo also includes:

* `deploy/install.sh` — installs Python + Node + nginx + certbot, builds
  the SPA, sets up systemd, and provisions HTTPS.
* `deploy/systemd/stack-hub.service` — the systemd unit.
* `deploy/nginx/stack-hub.conf` — the nginx config.
* `deploy/update.sh` — re-deploy after a code change.

Usage on a fresh Ubuntu 22.04 / 24.04 instance:

```bash
git clone https://github.com/<you>/stack-hub.git /tmp/stack-hub
sudo DOMAIN=studio.example.com EMAIL=you@example.com \
    bash /tmp/stack-hub/deploy/install.sh
```

The script copies the source to `/opt/stack-hub`, builds the SPA, registers
a systemd service, configures nginx, and runs certbot. Re-deploy after a
code change with:

```bash
sudo REPO_LOCAL=/tmp/stack-hub bash /opt/stack-hub/deploy/update.sh
```

---

## Health, logs, and metrics

### Health endpoint
The `/api/auth/me` route returns `200` if you have a valid session and
`401` otherwise — either response means the server is up. Use it for
external uptime probes (UptimeRobot, BetterStack, etc.):

```bash
curl -fsS https://studio.example.com/api/auth/me
# 401 → server up but you're not logged in (expected)
```

### Logs
```bash
docker compose logs --tail=200 -f stackhub   # API logs
docker compose logs --tail=200 -f caddy      # HTTPS / access logs
```

### Resource usage
```bash
docker stats stackhub
```

Stack Hub idles at ~80 MB RAM. LLM-heavy bursts can spike to ~250 MB.

---

## Common issues

**Mic doesn't work in the browser.** You're on `http://`, not `https://`.
Fix DNS, then `docker compose restart caddy` so Caddy can complete the
ACME handshake.

**Caddy keeps retrying the certificate.** DNS isn't pointing at this
server yet, or port 80/443 is closed. Verify: `dig studio.example.com`
returns the static IP, and `nc -zv studio.example.com 80` succeeds from
another host.

**`502 Bad Gateway` on `/api/*`.** The stackhub container hasn't started
or crashed. `docker compose logs stackhub` will show why — almost always
a missing env var (`AUTH_SECRET`, an LLM key) on first boot.

**Login says "invalid credentials" with the password I just set.** The
container caches credentials at boot. After editing `.env`,
`docker compose restart stackhub`.

**Recall.ai bot sits in `joining_call` forever.** The host hasn't admitted
the bot from the waiting room. Either disable waiting rooms for the
meeting, or admit it manually in Zoom/Meet.
