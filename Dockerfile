# =============================================================================
# Stack Hub Studio — single-image, multi-stage build.
#
# Stage 1: build the React app with Node.
# Stage 2: Python runtime, copy backend + built SPA.
# Volume:  /data — all mutable state (briefs, drafts, voice, posts.json, ...).
# Port:    8765
# =============================================================================

# ---------- Stage 1: webapp build ----------
FROM node:20-alpine AS webapp-builder
WORKDIR /webapp

# Cache npm install across rebuilds.
COPY webapp/package.json webapp/package-lock.json ./
RUN npm ci

COPY webapp/ ./
RUN npm run build


# ---------- Stage 2: Python runtime ----------
FROM python:3.11-slim AS runtime
WORKDIR /app

# Runtime helpers in one small layer (always needed).
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        ca-certificates \
        gosu \
        tini \
 && rm -rf /var/lib/apt/lists/*

# Build toolchain in a separate layer that we install + use + remove in one
# step so the final image stays small and peak memory stays low.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        gcc \
        python3-dev \
        libffi-dev \
 && rm -rf /var/lib/apt/lists/*

# Install Python deps first for better layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code (read-only at runtime — mutation happens on /data).
COPY scripts/ ./scripts/
COPY pyproject.toml ./pyproject.toml

# SPA build artifacts from stage 1.
COPY --from=webapp-builder /webapp/dist ./webapp/dist

# Default content seeded into /data on first start. Anything the admin
# panel can edit lives here; subsequent runs do NOT overwrite the volume.
RUN mkdir -p /seed
COPY corpus/        /seed/corpus/
COPY voice/         /seed/voice/
COPY prompts/       /seed/prompts/
COPY libraries/     /seed/libraries/
COPY rituals/       /seed/rituals/
COPY growth/        /seed/growth/
COPY briefs/_TEMPLATE.md /seed/briefs/_TEMPLATE.md
COPY data/config.json    /seed/data/config.json

# Entrypoint copies seeds → /data on first start, then drops to a non-root
# user. /data is the persistent volume.
COPY deploy/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Non-root user for the actual server process.
RUN groupadd --system --gid 1000 stackhub \
 && useradd  --system --uid 1000 --gid stackhub --home /app --shell /sbin/nologin stackhub

ENV PYTHONPATH=/app/scripts \
    PYTHONUNBUFFERED=1 \
    STACK_HUB_LOG_LEVEL=INFO \
    STACK_HUB_ROOT=/data

VOLUME ["/data"]
EXPOSE 8765

ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/docker-entrypoint.sh"]
CMD ["uvicorn", "pipeline.web.api:create_app", \
     "--factory", \
     "--host", "0.0.0.0", \
     "--port", "8765", \
     "--proxy-headers", \
     "--forwarded-allow-ips", "*"]
