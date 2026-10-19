"""
SalaryLens AI by CodeSec — Health Check Route
"""
from datetime import datetime, timezone
import os
from pathlib import Path
from fastapi import APIRouter, Depends, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db_session
from app.core.config import settings
from app.schemas.health import ConfiguredModels, HealthResponse

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="System Health & Readiness Check",
    description="Returns detailed health metrics, database readiness, storage availability, and model configuration."
)
async def health_check(db: AsyncSession = Depends(get_db_session)) -> HealthResponse:
    # 1. Database connectivity
    db_connected = False
    try:
        result = await db.execute(text("SELECT 1"))
        if result.scalar() == 1:
            db_connected = True
    except Exception:
        db_connected = False

    # 2. Storage readiness
    storage_ready = False
    try:
        upload_path = Path(settings.UPLOAD_DIR)
        render_path = Path(settings.RENDER_DIR)
        upload_path.mkdir(parents=True, exist_ok=True)
        render_path.mkdir(parents=True, exist_ok=True)
        test_file = upload_path / ".health_probe"
        test_file.write_text("ok")
        test_file.unlink()
        storage_ready = True
    except Exception:
        storage_ready = False

    overall_status = "healthy" if (db_connected and storage_ready) else "degraded"

    return HealthResponse(
        status=overall_status,
        environment=settings.ENVIRONMENT,
        demo_mode=settings.DEMO_MODE,
        database_connected=db_connected,
        storage_ready=storage_ready,
        version="1.0.0",
        timestamp=datetime.now(timezone.utc),
        models=ConfiguredModels(
            salary_finder=settings.SALARY_FINDER_MODEL,
            decision_engine=settings.DECISION_MODEL,
            embedding=settings.EMBEDDING_MODEL,
        ),
    )
