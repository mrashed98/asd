"""Main FastAPI application."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.routers import search, tracked, downloads, settings as settings_router, tasks

# Create FastAPI app
app = FastAPI(
    title="ArabSeed Downloader API",
    description="API for tracking and downloading content from ArabSeed",
    version="0.1.0",
)

# Add CORS middleware - Allow all origins for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=False,  # Cannot be True when allow_origins is ["*"]
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(search.router)
# tracked module now exports series_router and tracked_router
app.include_router(tracked.series_router)
app.include_router(tracked.tracked_router)
app.include_router(downloads.router)
app.include_router(settings_router.router)
app.include_router(tasks.router)


@app.on_event("startup")
def startup_event():
    """Initialize database on startup."""
    init_db()


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "ArabSeed Downloader API",
        "version": "0.1.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

