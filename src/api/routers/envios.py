"""Endpoints REST para Envíos de Paquetería de CargoBox."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies import get_envio_service
from src.application.dtos import (
    ActualizarDireccionDTO,
    AlertaRastreoDTO,
    AvanzarEnvioDTO,
    CancelarEnvioDTO,
    DictamenIndemnizacionDTO,
    DictamenIndemnizacionResponseDTO,
    EntregaDTO,
    EnvioCreateDTO,
    EnvioResponseDTO,
    IncidenciaDTO,
    IncidenciaResponseDTO,
    IntentoFallidoDTO,
    RastreoResponseDTO,
)
from src.application.services import EnvioAppService
from src.domain.enums import RolUsuario
from src.domain.exceptions import (
    DomainException,
    EntidadNoEncontradaException,
    GuiaDuplicadaException,
    TransicionInvalidaException,
)
from src.domain.value_objects import Direccion

router = APIRouter(prefix="/envios", tags=["Envíos y Logística"])


@router.post("/", response_model=EnvioResponseDTO, status_code=201)
def registrar_envio(
    dto: EnvioCreateDTO,
    svc: EnvioAppService = Depends(get_envio_service),
):
    """Registra un nuevo envío de paquetería en sucursal."""
    try:
        return svc.registrar_envio(dto)
    except GuiaDuplicadaException as e:
        raise HTTPException(status_code=409, detail=e.mensaje)
    except DomainException as e:
        raise HTTPException(status_code=422, detail=e.mensaje)


@router.get("/alertas/rastreo-detenido", response_model=List[AlertaRastreoDTO])
def alertas_rastreo_detenido(svc: EnvioAppService = Depends(get_envio_service)):
    """US6: envíos EN_TRANSITO con más de 24 h sin movimiento (notifica a Atención a Clientes)."""
    return svc.alertas_rastreo_detenido()


@router.get("/{guia}", response_model=EnvioResponseDTO)
def consultar_envio(
    guia: str,
    svc: EnvioAppService = Depends(get_envio_service),
):
    """Consulta estado y detalle de un envío por su guía de rastreo."""
    try:
        envio = svc.get_envio(guia)
        return svc._to_response_dto(envio)
    except EntidadNoEncontradaException as e:
        raise HTTPException(status_code=404, detail=e.mensaje)


@router.post("/{guia}/cancelar", response_model=EnvioResponseDTO)
def cancelar_envio(
    guia: str,
    body: CancelarEnvioDTO,
    svc: EnvioAppService = Depends(get_envio_service),
):
    """Cancela un envío (solo permitido en estado RECIBIDO)."""
    try:
        return svc.cancelar_envio(guia, body.motivo)
    except EntidadNoEncontradaException as e:
        raise HTTPException(status_code=404, detail=e.mensaje)
    except DomainException as e:
        raise HTTPException(status_code=409, detail=e.mensaje)


@router.post("/{guia}/direccion", response_model=EnvioResponseDTO)
def actualizar_direccion(
    guia: str,
    body: ActualizarDireccionDTO,
    svc: EnvioAppService = Depends(get_envio_service),
):
    """Actualiza la dirección de destino del envío."""
    try:
        nueva_dir = Direccion(
            calle=body.nueva_direccion.calle,
            numero=body.nueva_direccion.numero,
            colonia=body.nueva_direccion.colonia,
            ciudad=body.nueva_direccion.ciudad,
            codigo_postal=body.nueva_direccion.codigo_postal,
            referencias=body.nueva_direccion.referencias,
        )
        rol = RolUsuario(body.rol_solicitante)
        return svc.actualizar_direccion_destino(guia, nueva_dir, rol)
    except EntidadNoEncontradaException as e:
        raise HTTPException(status_code=404, detail=e.mensaje)
    except DomainException as e:
        raise HTTPException(status_code=409, detail=e.mensaje)


@router.post("/{guia}/intento-fallido", response_model=EnvioResponseDTO)
def registrar_intento_fallido(
    guia: str,
    body: IntentoFallidoDTO,
    svc: EnvioAppService = Depends(get_envio_service),
):
    """Registra un intento fallido de entrega domiciliaria."""
    try:
        return svc.registrar_intento_fallido(guia, body.motivo)
    except EntidadNoEncontradaException as e:
        raise HTTPException(status_code=404, detail=e.mensaje)
    except DomainException as e:
        raise HTTPException(status_code=409, detail=e.mensaje)


@router.post(
    "/{guia}/indemnizacion",
    response_model=DictamenIndemnizacionResponseDTO,
)
def dictaminar_indemnizacion(
    guia: str,
    body: DictamenIndemnizacionDTO,
    svc: EnvioAppService = Depends(get_envio_service),
):
    """Dictamina indemnización por daño, extravío o reclamación de seguro."""
    try:
        rol = RolUsuario(body.rol_dictaminador)
        return svc.dictaminar_indemnizacion(guia, body.monto_reclamado, rol)
    except EntidadNoEncontradaException as e:
        raise HTTPException(status_code=404, detail=e.mensaje)
    except DomainException as e:
        raise HTTPException(status_code=422, detail=e.mensaje)



@router.get("/{guia}/rastreo", response_model=RastreoResponseDTO)
def consultar_rastreo(
    guia: str,
    svc: EnvioAppService = Depends(get_envio_service),
):
    """US5: estado actual, historial de movimientos y fecha estimada de entrega."""
    try:
        return svc.obtener_rastreo(guia)
    except EntidadNoEncontradaException as e:
        raise HTTPException(status_code=404, detail=e.mensaje)


@router.post("/{guia}/avanzar", response_model=EnvioResponseDTO)
def avanzar_envio(
    guia: str,
    body: AvanzarEnvioDTO,
    svc: EnvioAppService = Depends(get_envio_service),
):
    """Avanza el envío al siguiente estado de la ruta (sin saltos): RECIBIDO -> CLASIFICADO -> EN_TRANSITO -> DISTRIBUCION_LOCAL -> EN_REPARTO."""
    try:
        return svc.avanzar_envio(guia, body.destino, body.cedis_id)
    except EntidadNoEncontradaException as e:
        raise HTTPException(status_code=404, detail=e.mensaje)
    except TransicionInvalidaException as e:
        raise HTTPException(status_code=409, detail=e.mensaje)
    except DomainException as e:
        raise HTTPException(status_code=422, detail=e.mensaje)


@router.post("/{guia}/entregar", response_model=EnvioResponseDTO)
def entregar_envio(
    guia: str,
    body: EntregaDTO,
    svc: EnvioAppService = Depends(get_envio_service),
):
    """US13: entrega final con nombre del receptor y evidencia (solo si está EN_REPARTO)."""
    try:
        return svc.entregar_envio(guia, body.receptor, body.evidencia_id)
    except EntidadNoEncontradaException as e:
        raise HTTPException(status_code=404, detail=e.mensaje)
    except DomainException as e:
        raise HTTPException(status_code=409, detail=e.mensaje)


@router.post("/{guia}/incidencias", response_model=IncidenciaResponseDTO, status_code=201)
def reportar_incidencia(
    guia: str,
    body: IncidenciaDTO,
    svc: EnvioAppService = Depends(get_envio_service),
):
    """US9/US11: dirección incorrecta (regresa a DISTRIBUCION_LOCAL) o paquete dañado (requiere evidencia)."""
    try:
        return svc.reportar_incidencia(guia, body.tipo, body.descripcion, body.evidencia_id)
    except EntidadNoEncontradaException as e:
        raise HTTPException(status_code=404, detail=e.mensaje)
    except TransicionInvalidaException as e:
        raise HTTPException(status_code=409, detail=e.mensaje)
    except DomainException as e:
        raise HTTPException(status_code=422, detail=e.mensaje)
