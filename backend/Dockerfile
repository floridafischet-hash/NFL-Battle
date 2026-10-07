FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

# Codex CLI: lets the result agent use a ChatGPT plan (Plus/Pro) instead of an API key
ARG CODEX_VERSION=0.160.1
ARG TARGETARCH
RUN arch="$([ "$TARGETARCH" = "arm64" ] && echo aarch64 || echo x86_64)" \
    && python -c "import io,sys,tarfile,urllib.request; \
url=f'https://github.com/openai/codex/releases/download/rust-v{sys.argv[1]}/codex-{sys.argv[2]}-unknown-linux-musl.tar.gz'; \
t=tarfile.open(fileobj=io.BytesIO(urllib.request.urlopen(url, timeout=300).read())); \
m=t.getmembers()[0]; f=t.extractfile(m); open('/usr/local/bin/codex','wb').write(f.read())" "$CODEX_VERSION" "$arch" \
    && chmod 755 /usr/local/bin/codex \
    && codex --version

RUN useradd --create-home --uid 10001 app \
    && mkdir -p /data/uploads /data/codex \
    && chown -R app:app /data \
    && chmod 700 /data/codex
COPY --chown=app:app alembic.ini ./
COPY --chown=app:app alembic ./alembic
COPY --chown=app:app app ./app

USER app
EXPOSE 8000
VOLUME ["/data"]

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/public/ready', timeout=4).status == 200 else 1)"

# One worker per container: scale horizontally with more replicas (realtime uses PostgreSQL LISTEN/NOTIFY).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
