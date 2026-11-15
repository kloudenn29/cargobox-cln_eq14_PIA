"""Endpoints de reportes analíticos de CargoBox (US14 y US15)."""

from fastapi import APIRouter, Depends

from src.api.dependencies import get_reporte_service
from src.application.dtos import ReporteEntregasATiempoDTO, ReporteIncidenciasDTO
from src.application.services import ReporteAppService

router = APIRouter(prefix="/reportes", tags=["Reportes Analíticos"])


@router.get("/entregas-a-tiempo", response_model=ReporteEntregasATiempoDTO)
def reporte_entregas_a_tiempo(svc: ReporteAppService = Depends(get_reporte_service)):
    """US14: porcentaje de envíos entregados dentro de la promesa de servicio (72 h)."""
    return svc.entregas_a_tiempo()


@router.get("/incidencias", response_model=ReporteIncidenciasDTO)
def reporte_incidencias(svc: ReporteAppService = Depends(get_reporte_service)):
    """US15: conteo de incidencias agrupadas por tipo."""
    return svc.incidencias_por_tipo()
