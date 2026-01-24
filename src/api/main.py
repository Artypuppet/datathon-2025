"""
RegAlpha FastAPI Application

Main FastAPI app with CORS, startup, and router registration.
"""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from .routers import filings, risk, graph, polymarket

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown."""
    # Startup
    logger.info("[INFO] Starting RegAlpha API")
    yield
    # Shutdown
    logger.info("[INFO] Shutting down RegAlpha API")


app = FastAPI(
    title="RegAlpha Legislative Risk Engine API",
    description="API for analyzing regulatory risk using SEC filings, legislation, and Polymarket probabilities",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(filings.router, prefix="/api/filings", tags=["filings"])
app.include_router(risk.router, prefix="/api/risk", tags=["risk"])
app.include_router(graph.router, prefix="/api/graph", tags=["graph"])
app.include_router(polymarket.router, prefix="/api/polymarket", tags=["polymarket"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "RegAlpha Legislative Risk Engine API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}
