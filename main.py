"""
RMS Billing API - Main Application
Multi-tenant SaaS billing system
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging

from app.core.config import settings
from app.api.v1.router import api_router

# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="Multi-tenant SaaS billing and invoicing system",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.on_event("startup")
async def startup_event():
    """Run on application startup - with graceful error handling"""
    logger.info("=" * 60)
    logger.info("🚀 Starting RMS Billing API")
    logger.info("=" * 60)
    logger.info(f"📦 Version: {settings.VERSION}")
    logger.info(f"🔧 Environment: {'Development' if settings.DEBUG else 'Production'}")
    
    # Import here to avoid blocking app startup
    try:
        from app.core.database import init_db, test_connection
        
        logger.info("🔍 Testing database connection...")
        if test_connection():
            logger.info("✅ Database connection successful")
            try:
                init_db()
                logger.info("✅ Database initialized successfully")
            except Exception as e:
                logger.error(f"⚠️ Database initialization failed: {str(e)}")
                logger.warning("⚠️ App will continue but database operations may fail")
        else:
            logger.error("❌ Database connection failed")
            logger.warning("=" * 60)
            logger.warning("⚠️ APP STARTED IN DEGRADED MODE")
            logger.warning("⚠️ Database is not accessible")
            logger.warning("💡 Solutions:")
            logger.warning("   1. Check Render database status")
            logger.warning("   2. Use local PostgreSQL instead")
            logger.warning("   3. Check DATABASE_URL in .env")
            logger.warning("=" * 60)
    
    except Exception as e:
        logger.error(f"❌ Startup error: {str(e)}")
        logger.warning("⚠️ App will continue but some features may not work")
    
    logger.info("=" * 60)
    logger.info("✅ Application ready!")
    logger.info(f"📝 API Docs: http://localhost:8000/docs")
    logger.info("=" * 60)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": settings.APP_NAME,
        "version": settings.VERSION,
        "status": "running",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint with database status"""
    try:
        from app.core.database import test_connection
        db_status = "connected" if test_connection() else "disconnected"
    except Exception:
        db_status = "error"
    
    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "version": settings.VERSION,
        "database": db_status,
        "message": "API is running" if db_status == "connected" else "API running but database unavailable"
    }


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred"
            }
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )