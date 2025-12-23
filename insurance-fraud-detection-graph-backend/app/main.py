from fastapi import FastAPI
from app.logging_conf import setup_logging
from fastapi.middleware.cors import CORSMiddleware
from app.middleware import RequestContextMiddleware
from app.routes.extract import router as extract_router
from app.routes.fraud import router as fraud_router
from app.routes.pipeline import router as pipeline_router
from app.routes.dashboard import router as dashboard_router
from app.routes.monitoring import router as monitoring_router
from app.routes.rag import router as rag_router
from app.routes.graph_chat import router as graph_chat_router
from app.routes.evaluation import router as evaluation_router

def create_app() -> FastAPI:
    setup_logging()
    app = FastAPI(title="Claims Extractor API", version="0.1.0")

    app.include_router(evaluation_router)
    
    # CORS for local dev
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:8501",  # Streamlit
            "http://127.0.0.1:8501",
            "http://localhost:3000",  # if you ever proxy through another UI
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    app.add_middleware(RequestContextMiddleware)

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    app.include_router(extract_router, prefix="/v1")
    app.include_router(fraud_router)
    app.include_router(pipeline_router, prefix="/v1")
    app.include_router(dashboard_router, prefix="/v1")
    app.include_router(monitoring_router, prefix="/v1")
    app.include_router(rag_router)
    app.include_router(graph_chat_router)  # New: Graph Chat for natural language Neo4j queries
    app.include_router(evaluation_router)  # New: Evaluation endpoint
    return app

app = create_app()