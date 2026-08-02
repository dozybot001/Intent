FROM python:3.13-slim

ARG INTHUB_VERSION=0.0.0

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    SETUPTOOLS_SCM_PRETEND_VERSION=${INTHUB_VERSION}

WORKDIR /app

RUN groupadd --gid 10001 inthub \
    && useradd --uid 10001 --gid inthub --no-create-home --shell /usr/sbin/nologin inthub \
    && mkdir -p /data \
    && chown inthub:inthub /data

COPY --chown=inthub:inthub . /app

RUN python -m pip install --no-cache-dir ".[server]"

USER 10001:10001

EXPOSE 8000

ENV INTHUB_HOST=0.0.0.0 \
    INTHUB_PORT=8000 \
    INTHUB_DB_PATH=/data/inthub.db \
    INTHUB_SERVE_WEB=1

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=4 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/readyz', timeout=3).read()"]

CMD ["python", "-m", "apps.inthub_api"]
