import asyncio
import contextlib
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from fs_notifications_challenge.infrastructure import models # noqa: F401 (registers the tables)
from fs_notifications_challenge.infrastructure.database import Base, engine
from fs_notifications_challenge.infrastructure.worker import run_outbox_worker
from fs_notifications_challenge.interface.error_handlers import register_exception_handlers
from fs_notifications_challenge.interface.pages import router as pages_router
from fs_notifications_challenge.interface.routes import router as api_router
from fs_notifications_challenge.interface.user_routes import router as users_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    worker_task = asyncio.create_task(run_outbox_worker())

    yield

    # Stop the worker cleanly on shutdown.
    worker_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await worker_task
    await engine.dispose()


MEDIA_DIR = Path(__file__).parent / "media"
STATIC_DIR = Path(__file__).parent / "static"
MEDIA_DIR.mkdir(exist_ok=True)  # media/ is gitignored: a fresh clone wouldn't have it

app = FastAPI(lifespan=lifespan)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")

register_exception_handlers(app)

app.include_router(pages_router.router)
app.include_router(api_router.router, prefix="/api/notifications", tags=["notifications"])
app.include_router(users_router.router, prefix="/api/users", tags=["users"])
