from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.db import Base, engine
from app.routers import admin, auth_router, review

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Data Ingestion + Correction Rules POC")

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SESSION_SECRET_KEY,
    session_cookie="poc_session",
    same_site="lax",
    max_age=8 * 3600,
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(auth_router.router)
app.include_router(admin.router)
app.include_router(review.router)


@app.get("/")
def index():
    return RedirectResponse(url="/login")
