import os
import sys
import logging

# Ensure 'app' package directory is in sys.path
app_dir = os.path.dirname(os.path.abspath(__file__))
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.study_routes import router as study_router
from app.api.protocol_routes import router as protocol_router
from app.api.vector_store_routes import router as vector_store_router
from app.api.search_routes import router as search_router
from app.api.rag_routes import router as rag_router
from app.api.analysis_routes import router as analysis_router
from app.api.icf_routes import router as icf_router
from app.api.validation_routes import router as validation_router
from app.api.review_routes import router as review_router
from app.api.template_routes import router as template_router
from app.api.workflow_routes import router as workflow_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("icf_generator")

app = FastAPI(
    title="AI-Assisted ICF Generator API",
    description="Backend service for generating and validating Informed Consent Forms from clinical trial protocols.",
    version="1.0.0"
)

# Enable CORS for local development (Vite dev server)
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routes
app.include_router(study_router, prefix="/api")
app.include_router(protocol_router, prefix="/api")
app.include_router(vector_store_router, prefix="/api")
app.include_router(search_router, prefix="/api")
app.include_router(rag_router, prefix="/api")
app.include_router(analysis_router, prefix="/api")
app.include_router(icf_router, prefix="/api")
app.include_router(validation_router, prefix="/api")
app.include_router(review_router, prefix="/api")
app.include_router(template_router, prefix="/api")
app.include_router(workflow_router, prefix="/api")


@app.get("/health")
def get_health_status():
    """
    Phase 1 Health Check Endpoint.
    Returns service health status to verify frontend-backend communication.
    """
    logger.info("Health check endpoint pinged")
    return {
        "status": "ok",
        "service": "ICF Generator API"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8001, reload=True)
