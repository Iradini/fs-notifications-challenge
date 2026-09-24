# from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

# from fs_notifications_challenge.infrastructure import models # noqa: F401 (registers the table)
# from fs_notifications_challenge.infrastructure.database import Base, engine
from fs_notifications_challenge.interface.routes import router as notification_router


# @asynccontextmanager
# async def lifespan(_app: FastAPI):
#     async with engine.begin() as conn:
#         await conn.run_sync(Base.metadata.create_all)
#     yield
#     await engine.dispose()




app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/media", StaticFiles(directory="media"), name="media")


app.include_router(
    notification_router,
    prefix="/api/notifications",
    tags=["notifications"],
)