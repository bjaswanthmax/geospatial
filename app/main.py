"""FastAPI Application Entrypoint for Geospatial File Measurement API."""

import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router as api_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

app = FastAPI(
    title="Geospatial File Measurement API",
    description=(
        "Production-grade backend service built with FastAPI to process geospatial files "
        "(KML and Shapefiles in ZIP format), extract features, handle CRS transformations, "
        "and calculate accurate geodesic/projected measurements (Area for Polygons, Length for LineStrings)."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router)


@app.get("/", tags=["Health"])
def root():
    """Root health check and API overview."""
    return {
        "service": "Geospatial File Measurement API",
        "status": "ONLINE",
        "documentation": "/docs",
        "endpoints": {
            "upload_file": "POST /api/files/",
            "get_file_info": "GET /api/files/{id}/",
            "get_file_measurements": "GET /api/files/{id}/measurements/",
            "list_files": "GET /api/files/"
        }
    }


@app.get("/health", tags=["Health"])
def health_check():
    """Health check endpoint for monitoring."""
    return {"status": "HEALTHY"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
