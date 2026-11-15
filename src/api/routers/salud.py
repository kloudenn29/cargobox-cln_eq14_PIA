"""Endpoint de Salud / Healthcheck."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.infrastructure.database import get_db

router = APIRouter(tags=["Salud y Monitoreo"])


@router.get("/health", summary="Estado del Servicio")
def healthcheck(db: Session = Depends(get_db)):
    """Verifica que la API responde y que la base de datos acepta consultas."""
    try:
        db.execute(text("SELECT 1"))
        estado_db = "connected"
    except Exception:
        estado_db = "unavailable"
    return {
        "status": "UP" if estado_db == "connected" else "DEGRADED",
        "service": "CargoBox API",
        "version": "1.1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database": estado_db,
    }
