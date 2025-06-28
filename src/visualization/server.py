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

    @visualization_router.get("/api/graph")
    async def api_graph():
        neo4j_uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
        neo4j_user = os.environ.get("NEO4J_USER", "neo4j")
        neo4j_password = os.environ.get("NEO4J_PASSWORD", "neo4j")
        print(f"[DEBUG] SPA /api/graph NEO4J_URI: {neo4j_uri}", flush=True)
        from src.graph_visualizer import GraphVisualizer
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
import os
# DEBUG: Print NEO4J_URI when /api/graph is called