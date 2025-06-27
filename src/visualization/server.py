def create_app():
    """ASGI app factory for uvicorn --factory."""
    from fastapi import FastAPI, APIRouter
    from fastapi.staticfiles import StaticFiles
    import os

    app = FastAPI(
        title="Visualization Server",
        description="Serves graph visualizations and related endpoints.",
        version="0.1.0"
    )

    visualization_router = APIRouter()

    app.include_router(visualization_router)
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    print("[DEBUG] create_app: routers and static mounted.", flush=True)
    return app

app = create_app()