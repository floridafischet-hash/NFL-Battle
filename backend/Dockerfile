FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

# Codex CLI: lets the result agent use a ChatGPT plan (Plus/Pro) instead of an API key.
# Pinned version, verified by SHA-256 before it is installed.
ARG CODEX_VERSION=0.160.1
ARG CODEX_SHA256_X86_64=9226581be592d18f7e7f740a352fdb63aa61e45e39f7eb9b09d3888c84bba33f
ARG CODEX_SHA256_AARCH64=f54dc5852042445bf41da3aa31156f3cb02f52c5a1a04074de73dc5598f7e1f7
ARG TARGETARCH
RUN if [ "$TARGETARCH" = "arm64" ]; then arch=aarch64; sum="$CODEX_SHA256_AARCH64"; \
    else arch=x86_64; sum="$CODEX_SHA256_X86_64"; fi \
    && python -c "import hashlib,io,sys,tarfile,urllib.request; \
v,a,want=sys.argv[1:4]; name=f'codex-{a}-unknown-linux-musl'; \
data=urllib.request.urlopen(f'https://github.com/openai/codex/releases/download/rust-v{v}/{name}.tar.gz', timeout=300).read(); \
got=hashlib.sha256(data).hexdigest(); \
sys.exit(f'codex checksum mismatch: {got}') if got != want else None; \
f=tarfile.open(fileobj=io.BytesIO(data)).extractfile(name); \
open('/usr/local/bin/codex','wb').write(f.read())" "$CODEX_VERSION" "$arch" "$sum" \
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
