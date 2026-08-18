FROM python:3.12-slim@sha256:2c941e860699f878900b0edc2403613c234d4b32eda3cc9fa7036991a2a63c4a AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VIRTUAL_ENV=/opt/venv

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libssl-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv "${VIRTUAL_ENV}"
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"

WORKDIR /build
COPY requirements-lock.txt ./
RUN python -m pip install --no-cache-dir pip==25.3 setuptools==82.0.1 wheel==0.48.0 && \
    python -m pip install --no-cache-dir -r requirements-lock.txt


FROM python:3.12-slim@sha256:2c941e860699f878900b0edc2403613c234d4b32eda3cc9fa7036991a2a63c4a AS runtime

ENV HOME=/home/appuser \
    PATH="/opt/venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    REFLEX_STATES_WORKDIR=/app/.reflex_states

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 appuser \
    && useradd --uid 10001 --gid appuser --create-home --shell /usr/sbin/nologin appuser

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY --chown=appuser:appuser . /app
RUN mkdir -p /app/.web /app/.states /app/.reflex_states /app/data \
    && chown appuser:appuser /app \
    && chown -R appuser:appuser /app/.web /app/.states /app/.reflex_states /app/data

USER appuser

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7860/_health', timeout=5)" || exit 1

CMD ["reflex", "run", "--env", "prod", "--backend-port", "7860"]
