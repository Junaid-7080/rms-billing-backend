from fastapi import FastAPI
from app.api.v1.router import api_router
from app.core.config import settings
from app.middleware.tenant import TenantMiddleware
from fastapi.middleware.cors import CORSMiddleware
import logging

# -------------------------------------------------
# 🧠 Logging Configuration
# -------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)
logger = logging.getLogger(__name__)

# -------------------------------------------------
# 🚀 Create the FastAPI app
# -------------------------------------------------
app = FastAPI(
    title="Invoice App Backend",
    version="1.0.0",
    description="Multi-tenant billing and invoice management API"
)

# -------------------------------------------------
# 🧩 Middleware
# -------------------------------------------------
# ✅ Tenant Middleware (make sure call_next is used inside it)
app.add_middleware(TenantMiddleware)

# ✅ CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ⚠️ Change to frontend domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------
# 🔗 Include API Routes
# -------------------------------------------------
app.include_router(api_router, prefix="/api/v1")

# -------------------------------------------------
# 🏠 Root Endpoint
# -------------------------------------------------
@app.get("/")
def root():
    logger.info("Root endpoint hit ✅")
    return {"message": "Invoice App Backend is running 🚀"}

# -------------------------------------------------
# ⚡ Application Lifecycle Events
# -------------------------------------------------
@app.on_event("startup")
async def startup_event():
    logger.info("🚀 Application startup...")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("🛑 Application shutdown...")


