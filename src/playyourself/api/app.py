"""FastAPI app: thin layer over the decision and data layers."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from playyourself.api import envelope
from playyourself.api.routes import analysis, connect, dashboard, friends, health, spending

STATIC_DIR = Path(__file__).resolve().parents[1] / "static"

app = FastAPI(
    title="Play Yourself API",
    version="0.1.0",
    description=(
        "Replay your own saving and investing habits through past market shocks. "
        "All forward-looking outputs are modelled scenarios from similar past periods. "
        "They are not forecasts, not financial advice. Every response uses one envelope."
    ),
)
envelope.register(app)
for r in (
    health.router,
    dashboard.router,
    analysis.router,
    friends.router,
    connect.router,
    spending.router,
):
    app.include_router(r, prefix="/v1")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
