"""Endpoints REST para Operaciones Comerciales de CargoBox."""

from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies import get_operacion_service
from src.application.dtos import (
    EvaluacionReglaResponseDTO,
    OperacionCreateDTO,
    OperacionResponseDTO,
    TransicionRequestDTO,
    TransicionResponseDTO,
)
from src.application.services import OperacionAppService
from src.domain.exceptions import DomainException, EntidadNoEncontradaException

router = APIRouter(prefix="/operaciones", tags=["Operaciones"])


@router.post("/", response_model=OperacionResponseDTO, status_code=201)
def crear_operacion(
    dto: OperacionCreateDTO,
    svc: OperacionAppService = Depends(get_operacion_service),
):
    """Registra una nueva operación comercial."""
    try:
        return svc.crear_operacion(dto)
    except EntidadNoEncontradaException as e:
        raise HTTPException(status_code=404, detail=e.mensaje)
    except DomainException as e:
        raise HTTPException(status_code=422, detail=e.mensaje)


@router.get("/{operacion_id}", response_model=OperacionResponseDTO)
def obtener_operacion(
    operacion_id: str,
    svc: OperacionAppService = Depends(get_operacion_service),
):
    """Consulta una operación por su ID."""
    try:
        op = svc.get_operacion(operacion_id)
        return svc._to_response_dto(op)
    except EntidadNoEncontradaException as e:
        raise HTTPException(status_code=404, detail=e.mensaje)


@router.post("/{operacion_id}/transicion", response_model=TransicionResponseDTO)
def ejecutar_transicion(
    operacion_id: str,
    body: TransicionRequestDTO,
    svc: OperacionAppService = Depends(get_operacion_service),
):
    """Ejecuta una transición de estado sobre la operación."""
    try:
        return svc.ejecutar_transicion(operacion_id, body.accion)
    except EntidadNoEncontradaException as e:
        raise HTTPException(status_code=404, detail=e.mensaje)
    except DomainException as e:
        raise HTTPException(status_code=409, detail=e.mensaje)


@router.get(
    "/{operacion_id}/validar",
    response_model=EvaluacionReglaResponseDTO,
)
def validar_precondiciones(
    operacion_id: str,
    svc: OperacionAppService = Depends(get_operacion_service),
):
    """Evalúa la regla puede_procesarse sobre la operación."""
    try:
        return svc.evaluar_precondiciones(operacion_id)
    except EntidadNoEncontradaException as e:
        raise HTTPException(status_code=404, detail=e.mensaje)


@router.get(
    "/{operacion_id}/beneficio",
    response_model=EvaluacionReglaResponseDTO,
)
def evaluar_beneficio(
    operacion_id: str,
    svc: OperacionAppService = Depends(get_operacion_service),
):
    """Evalúa la regla beneficio_referencia sobre la operación."""
    try:
        return svc.evaluar_beneficio(operacion_id)
    except EntidadNoEncontradaException as e:
        raise HTTPException(status_code=404, detail=e.mensaje)

