from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import get_settings
from app.db import Base, engine
from app.routers import auth, clients, dashboard, surveys, template, users


@asynccontextmanager
async def lifespan(app: FastAPI):
    # The schema is small and versioned with the code; create it on boot if missing.
    Base.metadata.create_all(bind=engine)
    yield


# Docs live under /api so a single reverse proxy rule covers the whole backend.
app = FastAPI(
    title="BIA questionnaire",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(clients.router)
app.include_router(clients.systems_router)
app.include_router(surveys.router)
app.include_router(template.router)
app.include_router(dashboard.router)


@app.get("/api/health")
def health() -> dict:
    with engine.connect() as conn:
        conn.execute(text("select 1"))
    return {"status": "ok"}
