# ──────────────────────────────────────────────────────────────────────────────
#  Stage 1 — Builder
#  Compiles packages that need system headers (Pillow, psycopg2-binary, etc.)
#  Nothing from this stage lands in the final image except /install.
# ──────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Build-time system deps only (compiler, headers)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        libjpeg-dev \
        zlib1g-dev \
        libmagic1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install --prefix=/install --no-cache-dir -r requirements.txt


# ──────────────────────────────────────────────────────────────────────────────
#  Stage 2 — Runtime
#  Lean image: only runtime libs, no compilers.
# ──────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Runtime system deps
# redis-tools  → redis-cli used in entrypoint to wait for Redis
# libpq-dev    → psycopg2 runtime (if Postgres is ever added)
# libjpeg-dev  → Pillow JPEG support
# libmagic1    → python-magic (file type detection)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq-dev \
        libjpeg-dev \
        zlib1g-dev \
        libmagic1 \
        redis-tools \
    && rm -rf /var/lib/apt/lists/*

# Copy compiled Python packages from builder
COPY --from=builder /install /usr/local

# Copy project source
COPY . .

# ── Entrypoint setup ──────────────────────────────────────────────────────────
# Copy to /entrypoint.sh at container root so the .:/app bind-mount
# (which overlays /app at runtime) cannot shadow it.
# sed strips Windows CRLF just in case the file was edited on Windows.
RUN sed -i 's/\r//' /app/entrypoint.sh \
    && cp /app/entrypoint.sh /entrypoint.sh \
    && chmod +x /entrypoint.sh

# ── Runtime directories ───────────────────────────────────────────────────────
# db_volume : SQLite database (mounted as named Docker volume)
# staticfiles: collectstatic output (mounted as named Docker volume)
# media      : user uploads       (mounted as named Docker volume)
RUN mkdir -p /app/db_volume /app/staticfiles /app/media

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
