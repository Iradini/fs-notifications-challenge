from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from fs_notifications_challenge.infrastructure import models # noqa: F401 (registers the table)
from fs_notifications_challenge.infrastructure.database import Base, engine
from fs_notifications_challenge.interface.error_handlers import register_exception_handlers
from fs_notifications_challenge.interface.pages import router as pages_router
from fs_notifications_challenge.interface.routes import router as api_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Create tables on startingup using the async engine.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


MEDIA_DIR = Path(__file__).parent / "media"
STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(lifespan=lifespan)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")

register_exception_handlers(app)

app.include_router(pages_router)

app.include_router(
    api_router,
    prefix="/api/notifications",
    tags=["notifications"],
)