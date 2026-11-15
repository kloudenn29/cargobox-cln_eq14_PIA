"""Data Transfer Objects (DTOs) para la API y Servicios de CargoBox."""

from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


# ----------------------------------------------------------------------------
# DTOs para Actores y Catálogo
# ----------------------------------------------------------------------------
class ActorDTO(BaseModel):
    actor_id: str
    nombre: str
    es_preferente: bool
    activo: bool
    ciudad: str


class RecursoDTO(BaseModel):
    recurso_id: str
    descripcion: str
    precio_mxn: Decimal
    capacidad_o_stock: int
    habilitado: bool


# ----------------------------------------------------------------------------
# DTOs para Operaciones
# ----------------------------------------------------------------------------
class DetalleOperacionDTO(BaseModel):
    recurso_id: str
    cantidad: int
    precio_unitario: Decimal = Decimal("0.00")
    subtotal: Decimal = Decimal("0.00")


class OperacionCreateDTO(BaseModel):
    operacion_id: str
    actor_id: str
    promocion_activa: bool = False
    autorizado: bool = True
    referencia: str = ""
    detalles: List[DetalleOperacionDTO] = []


class OperacionResponseDTO(BaseModel):
    operacion_id: str
    actor_id: str
    estado: str
    fecha_solicitud: str
    promocion_activa: bool
    autorizado: bool
    referencia: str
    total_mxn: Decimal
    detalles_count: int


class TransicionRequestDTO(BaseModel):
    accion: str = Field(..., description="Acción de la máquina de estados: aprobar, completar, cancelar, despachar, etc.")


class TransicionResponseDTO(BaseModel):
    operacion_id: str
    accion_ejecutada: str
    estado_anterior: str
    estado_nuevo: str
    mensaje: str


class EvaluacionReglaResponseDTO(BaseModel):
    operacion_id: str
    regla: str
    cumple: bool
    explicacion: str


# ----------------------------------------------------------------------------
# DTOs para Envíos y Rastreo
# ----------------------------------------------------------------------------
class DireccionDTO(BaseModel):
    calle: str
    numero: str
    colonia: str = ""
    ciudad: str
    codigo_postal: str
    referencias: str = ""


class EnvioCreateDTO(BaseModel):
    guia: str
    remitente_id: str
    destinatario_nombre: str
    direccion_origen: DireccionDTO
    direccion_destino: DireccionDTO
    peso_kg: Decimal
    largo_cm: Decimal = Decimal("30.0")
    ancho_cm: Decimal = Decimal("20.0")
    alto_cm: Decimal = Decimal("15.0")
    descripcion_paquete: str = "Paquete general"
    seguro_amparado: bool = False
    valor_declarado: Decimal = Decimal("0.00")
    flete_monto: Decimal = Decimal("350.00")


class EnvioResponseDTO(BaseModel):
    guia: str
    remitente_id: str
    destinatario_nombre: str
    estado: str
    intentos_entrega: int
    cedis_actual: str
    flete_mxn: Decimal
    seguro_amparado: bool
    valor_declarado_mxn: Decimal
    origen_resumen: str
    destino_resumen: str


class ActualizarDireccionDTO(BaseModel):
    nueva_direccion: DireccionDTO
    rol_solicitante: str = "ATENCION_CLIENTES"


class CancelarEnvioDTO(BaseModel):
    motivo: str = "Solicitud de cancelación por remitente en sucursal"


class IntentoFallidoDTO(BaseModel):
    motivo: str = "Destinatario no responde en domicilio"


class DictamenIndemnizacionDTO(BaseModel):
    monto_reclamado: Decimal
    rol_dictaminador: str = "ANALISTA_CALIDAD"


class DictamenIndemnizacionResponseDTO(BaseModel):
    guia: str
    monto_reclamado: Decimal
    monto_autorizado: Decimal
    tiene_seguro: bool
    dictaminado_por: str
    mensaje: str



# ----------------------------------------------------------------------------
# DTOs de avance, entrega, incidencias, rastreo y reportes (US5, US6, US9, US11, US13, US14, US15)
# ----------------------------------------------------------------------------
class AvanzarEnvioDTO(BaseModel):
    destino: str = Field(..., description="Siguiente estado: CLASIFICADO, EN_TRANSITO, DISTRIBUCION_LOCAL o EN_REPARTO.")
    cedis_id: Optional[str] = Field(default=None, description="CEDIS donde ocurre el movimiento (opcional).")


class EntregaDTO(BaseModel):
    receptor: str = Field(..., description="Nombre de quien recibe el paquete.")
    evidencia_id: str = Field(..., description="Identificador de la firma o foto de entrega.")


class IncidenciaDTO(BaseModel):
    tipo: str = Field(..., description="DIRECCION_INCORRECTA, PAQUETE_DANADO, EXTRAVIO o RECHAZO.")
    descripcion: str
    evidencia_id: str = ""


class IncidenciaResponseDTO(BaseModel):
    incidencia_id: str
    guia: str
    tipo: str
    descripcion: str
    evidencia_id: str
    estado_envio: str


class MovimientoDTO(BaseModel):
    estado: str
    detalle: str
    fecha: datetime


class RastreoResponseDTO(BaseModel):
    guia: str
    estado_actual: str
    cedis_actual: str
    intentos_entrega: int
    fecha_estimada_entrega: datetime
    historial: List[MovimientoDTO]


class AlertaRastreoDTO(BaseModel):
    guia: str
    estado: str
    horas_sin_movimiento: float
    notificado_a: str = "ATENCION_CLIENTES"


class ReporteEntregasATiempoDTO(BaseModel):
    total_entregados: int
    entregados_a_tiempo: int
    porcentaje_a_tiempo: float
    sla_horas: int


class ReporteIncidenciasDTO(BaseModel):
    total_incidencias: int
    por_tipo: Dict[str, int]
