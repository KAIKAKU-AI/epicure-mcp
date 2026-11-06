# syntax=docker/dockerfile:1.7

# --- Stage 1: install the sealed runtime dependency tree --------------------
FROM python:3.12-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /build

COPY reproducibility/runtime-linux-x86_64-cp312.lock ./runtime.lock

RUN pip install \
    --prefix /install \
    --no-warn-script-location \
    --require-hashes \
    -r runtime.lock

# --- Stage 2: minimal runtime image ----------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    HOST=0.0.0.0 \
    PORT=8080 \
    EPICURE_DATA_DIR=/app/data \
    EPICURE_RELEASE_ID=exploratory-unmatched-1790-runtime

WORKDIR /app

COPY --from=builder /install /usr/local

COPY src /app/src
COPY data /app/data
COPY assets /app/assets

RUN useradd -r -u 10001 epicure \
    && chown -R epicure:epicure /app

USER epicure

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; \
sys.exit(0 if urllib.request.urlopen('http://localhost:8080/healthz', timeout=2).status == 200 else 1)" \
    || exit 1

CMD ["python", "-m", "epicure_mcp.server"]
