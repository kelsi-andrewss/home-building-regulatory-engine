import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.endpoints import router
from backend.app.db.session import async_session, engine

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Seed rule fragments on startup
    async with async_session() as session:
        try:
            from backend.app.db.seed_data import seed_all

            await seed_all(session)
            await session.commit()
        except Exception:
            logger.exception("Seed data failed (DB may not be ready)")
            await session.rollback()

    yield

    # Shutdown: dispose engine
    await engine.dispose()


app = FastAPI(title="Home Building Regulatory Engine", lifespan=lifespan)

# CORS
allowed_origins = ["http://localhost:5173"]
frontend_origin = os.environ.get("FRONTEND_ORIGIN")
if frontend_origin:
    allowed_origins.append(frontend_origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    allow_credentials=True,
)

app.include_router(router)


@app.get("/health")
async def health():
    return {"status": "ok"}
