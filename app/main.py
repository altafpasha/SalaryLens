"""
SalaryLens AI by CodeSec — Main FastAPI Application
"""
import uuid
import time
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging import setup_logging
from app.api.routes import admin, auth, dashboard, health, statements
from app.db.session import init_db

# Configure application logging
setup_logging(log_level=settings.LOG_LEVEL, log_format=settings.LOG_FORMAT)
logger = logging.getLogger("salarylens.app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup actions
    logger.info("Initializing SalaryLens AI application...")
    settings.validate_production_configuration()
    settings.ensure_directories()

    # Initialize database tables
    try:
        await init_db()
        logger.info("Database tables verified/initialized.")
    except Exception as e:
        logger.warning(f"Database table verification/initialization warning: {e}")

    logger.info(
        f"SalaryLens AI ready. Environment: {settings.ENVIRONMENT}, Demo Mode: {settings.DEMO_MODE}"
    )
    yield
    # Shutdown actions
    logger.info("Shutting down SalaryLens AI application...")


app = FastAPI(
    title="SalaryLens AI by CodeSec",
    description="Automated AI-powered bank statement salary detection, financial verification, and evidence auditing API.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_request_id_and_timing(request: Request, call_next):
    """Injects a unique X-Request-ID and measures request latency."""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    start_time = time.time()
    
    response = await call_next(request)
    
    process_time = time.time() - start_time
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = f"{process_time:.4f}s"
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler to prevent leaking stack traces and secrets."""
    logger.error(f"Unhandled exception during request {request.url.path}: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred while processing your request. Please contact support.",
            "request_id": request.headers.get("X-Request-ID", "unknown")
        }
    )


# Mount API Routers
app.include_router(health.router, prefix=settings.API_V1_STR)
app.include_router(auth.router, prefix=settings.API_V1_STR)
app.include_router(statements.router, prefix=settings.API_V1_STR)
app.include_router(admin.router, prefix=settings.API_V1_STR)
app.include_router(dashboard.router, prefix=settings.API_V1_STR)


@app.get("/", include_in_schema=False)
async def root():
    return {
        "service": "SalaryLens AI by CodeSec",
        "documentation": "/docs",
        "health": f"{settings.API_V1_STR}/health"
    }
