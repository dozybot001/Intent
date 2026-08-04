FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

RUN groupadd --gid 10001 inthub \
    && useradd --uid 10001 --gid inthub --no-create-home --shell /usr/sbin/nologin inthub \
    && mkdir -p /data \
    && chown inthub:inthub /data

RUN apt-get update \
    && apt-get install --yes --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

# The pure-Python package uses Debian's libpq. Keeping runtime dependencies
# before COPY makes this layer reusable for every application-only release.
RUN python -m pip install --no-cache-dir "psycopg==3.3.4"

COPY --chown=inthub:inthub . /app

# Keep revision-specific metadata after the dependency layer so a new release
# can reuse the already downloaded PostgreSQL driver.
ARG INTHUB_VERSION=0.0.0
ARG INTHUB_REVISION=unknown
LABEL org.opencontainers.image.title="IntHub" \
    org.opencontainers.image.source="https://github.com/dozybot001/Intent" \
    org.opencontainers.image.version="${INTHUB_VERSION}" \
    org.opencontainers.image.revision="${INTHUB_REVISION}"

USER 10001:10001

EXPOSE 8000

ENV INTHUB_HOST=0.0.0.0 \
    INTHUB_PORT=8000 \
    INTHUB_DB_PATH=/data/inthub.db \
    INTHUB_SERVE_WEB=1

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=4 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/readyz', timeout=3).read()"]

CMD ["python", "-m", "apps.inthub_api"]
