import os

# Fail fast at import/app startup if NEO4J_URI is not set
if not os.environ.get("NEO4J_URI"):
    raise RuntimeError(
        "NEO4J_URI environment variable must be set. Refusing to default to localhost:7687. "
        "Set NEO4J_URI to the correct Neo4j connection string."
    )

def create_app():
    """ASGI app factory for uvicorn --factory."""
    from fastapi import FastAPI, APIRouter
    from fastapi.staticfiles import StaticFiles

    app = FastAPI(
        title="Visualization Server",
        description="Serves graph visualizations and related endpoints.",
        version="0.1.0"
    )

    visualization_router = APIRouter()

    # Only load .env if NEO4J_URI is not already set (redundant now, but kept for clarity)
    if "NEO4J_URI" not in os.environ:
        from dotenv import load_dotenv
        load_dotenv()

    @visualization_router.get("/")
    async def root():
        static_dir = os.path.join(os.path.dirname(__file__), "static")
        index_path = os.path.join(static_dir, "index.html")
        with open(index_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content=html_content, status_code=200)

    @visualization_router.get("/api/graph")
    async def api_graph():
        neo4j_uri = os.environ.get("NEO4J_URI")
        neo4j_user = os.environ.get("NEO4J_USER", "neo4j")
        neo4j_password = os.environ.get("NEO4J_PASSWORD", "neo4j")
        print(f"[DEBUG] SPA /api/graph NEO4J_URI: {neo4j_uri}", flush=True)
        import sys
        print(f"[DEBUG] SPA server process environment: {dict(os.environ)}", file=sys.stderr, flush=True)
        from src.graph_visualizer import GraphVisualizer
        # If NEO4J_AUTH is "none" or password is empty, connect without auth
        if os.environ.get("NEO4J_AUTH") == "none" or not neo4j_password:
            from neo4j import GraphDatabase
            visualizer = GraphVisualizer(neo4j_uri, "", "")
            visualizer.driver = GraphDatabase.driver(neo4j_uri, auth=("", ""))
        else:
            visualizer = GraphVisualizer(neo4j_uri, neo4j_user, neo4j_password)
        try:
            visualizer.connect()
            data = visualizer.extract_graph_data(link_to_hierarchy=True)
            return {
                "nodes": data.get("nodes", []),
                "links": data.get("links", []),
                "node_types": data.get("node_types", []),
                "relationship_types": data.get("relationship_types", []),
            }
        finally:
            if hasattr(visualizer, "driver") and visualizer.driver:
                visualizer.driver.close()

    app.include_router(visualization_router)
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    print("[DEBUG] create_app: routers and static mounted.", flush=True)
    return app

app = create_app()