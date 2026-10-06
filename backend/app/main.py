import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from app.api import admin, agent, auth, game, public, social
from app.core.config import get_settings
from app.core.db import dispose_engine
from app.realtime.hub import listen_forever
from app.services.scheduler import scheduler_loop


def configure_logging() -> None:
    logging.basicConfig(
        level=get_settings().log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)  # noqa: ASYNC240 - once at startup
    if settings.has_placeholder_db_password:
        logging.getLogger("app").warning(
            "POSTGRES_PASSWORD is still a CHANGE_ME placeholder – run scripts/generate-secrets.sh for real deployments"
        )
    stop = asyncio.Event()
    tasks = [asyncio.create_task(listen_forever(stop))]
    if settings.scheduler_enabled:
        tasks.append(asyncio.create_task(scheduler_loop(stop)))
    try:
        yield
    finally:
        stop.set()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await dispose_engine()


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()
    app = FastAPI(
        title="NFL Bracket Battle API",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        if request.url.path.startswith("/media/"):
            response.headers["Content-Security-Policy"] = "default-src 'none'; img-src 'self'; sandbox"
            if response.status_code == 200:
                response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        elif request.url.path.startswith("/api/") and not request.url.path.startswith("/api/docs"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    for module in (public, auth, game, social, admin, agent):
        app.include_router(module.router)
    app.include_router(social.ws_router)
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    app.mount("/media", StaticFiles(directory=settings.upload_dir, check_dir=False), name="media")
    return app


app = create_app()
