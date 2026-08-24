# Release images are Linux/amd64 only. Pin the exact platform manifest so the
# same Git commit cannot silently pick up a different Python or Debian base.
FROM python:3.13-slim@sha256:69e18bd8d831d88e0ef70239dc7771ab7c28bc296ae78ac75cde71e60aa4434f

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

RUN groupadd --gid 10001 inthub \
    && useradd --uid 10001 --gid inthub --no-create-home --shell /usr/sbin/nologin inthub \
    && mkdir -p /data \
    && chown inthub:inthub /data

# The pinned binary wheel carries libpq, eliminating a floating apt snapshot
# from the release recipe while retaining an exact application dependency.
RUN python -m pip install --no-cache-dir "psycopg[binary]==3.3.4"

COPY --chown=inthub:inthub . /app

# Keep revision-specific metadata after the dependency layer so a new release
# can reuse the already downloaded PostgreSQL driver.
ARG INTHUB_VERSION=0.0.0
ARG INTHUB_REVISION=unknown
ARG INTHUB_SCHEMA_VERSION=2
LABEL org.opencontainers.image.title="IntHub" \
    org.opencontainers.image.source="https://github.com/dozybot001/Intent" \
    org.opencontainers.image.version="${INTHUB_VERSION}" \
    org.opencontainers.image.revision="${INTHUB_REVISION}" \
    io.inthub.database-schema-version="${INTHUB_SCHEMA_VERSION}"

USER 10001:10001

EXPOSE 8000

ENV INTHUB_HOST=0.0.0.0 \
    INTHUB_PORT=8000 \
    INTHUB_DB_PATH=/data/inthub.db \
    INTHUB_SERVE_WEB=1

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=4 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/readyz', timeout=3).read()"]

CMD ["python", "-m", "apps.inthub_api"]
