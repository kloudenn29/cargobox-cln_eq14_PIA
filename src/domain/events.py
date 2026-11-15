"""Eventos de Dominio (Domain Events) de CargoBox."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List


@dataclass(frozen=True)
class DomainEvent:
    """Clase base inmutable para todos los eventos del dominio."""
    aggregate_id: str
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    occurred_on: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def event_name(self) -> str:
        return self.__class__.__name__


@dataclass(frozen=True)
class OperacionCreada(DomainEvent):
    actor_id: str = ""
    referencia: str = ""
    total: str = "0.00"


@dataclass(frozen=True)
class OperacionAprobada(DomainEvent):
    estado_anterior: str = "RECIBIDO"
    nuevo_estado: str = "CLASIFICADO"


@dataclass(frozen=True)
class OperacionEnTransito(DomainEvent):
    estado_anterior: str = "CLASIFICADO"
    nuevo_estado: str = "EN_TRANSITO"


@dataclass(frozen=True)
class OperacionCompletada(DomainEvent):
    estado_anterior: str = ""
    nuevo_estado: str = "ENTREGADO"


@dataclass(frozen=True)
class OperacionCancelada(DomainEvent):
    estado_anterior: str = ""
    motivo: str = ""


@dataclass(frozen=True)
class TransicionRechazada(DomainEvent):
    estado_actual: str = ""
    accion_intentada: str = ""
    motivo_rechazo: str = ""


@dataclass(frozen=True)
class EnvioRegistrado(DomainEvent):
    guia: str = ""
    remitente_id: str = ""
    peso_kg: float = 0.0


@dataclass(frozen=True)
class EnvioClasificado(DomainEvent):
    cedis_id: str = ""


@dataclass(frozen=True)
class EnvioEnTransito(DomainEvent):
    cedis_origen: str = ""
    cedis_destino: str = ""


@dataclass(frozen=True)
class IntentoFallidoRegistrado(DomainEvent):
    numero_intento: int = 1
    motivo: str = ""
    proxima_accion: str = ""


@dataclass(frozen=True)
class DevolucionIniciada(DomainEvent):
    motivo: str = ""


@dataclass(frozen=True)
class DireccionActualizada(DomainEvent):
    nueva_direccion: str = ""
    autorizado_por: str = ""


@dataclass(frozen=True)
class EnvioEntregado(DomainEvent):
    receptor: str = ""
    evidencia_id: str = ""


@dataclass(frozen=True)
class EnvioCancelado(DomainEvent):
    motivo: str = ""


@dataclass(frozen=True)
class IndemnizacionDictaminada(DomainEvent):
    monto_autorizado: str = "0.00"
    tiene_seguro: bool = False
    dictaminado_por: str = ""


@dataclass(frozen=True)
class IncidenciaRegistrada(DomainEvent):
    tipo: str = ""
    evidencia_id: str = ""


@dataclass(frozen=True)
class AlertaRastreoDetenido(DomainEvent):
    horas_sin_movimiento: float = 0.0
    destinatario_alerta: str = "ATENCION_CLIENTES"


class EventDispatcher:
    """Despachador en memoria para registrar manejadores y publicar eventos de dominio."""
    _subscribers: Dict[str, List[Callable[[DomainEvent], None]]] = {}
    _event_history: List[DomainEvent] = []

    @classmethod
    def subscribe(cls, event_type: type, handler: Callable[[Any], None]) -> None:
        key = event_type.__name__
        if key not in cls._subscribers:
            cls._subscribers[key] = []
        cls._subscribers[key].append(handler)

    @classmethod
    def dispatch(cls, event: DomainEvent) -> None:
        cls._event_history.append(event)
        handlers = cls._subscribers.get(event.event_name, [])
        for handler in handlers:
            handler(event)

    @classmethod
    def get_history(cls) -> List[DomainEvent]:
        return list(cls._event_history)

    @classmethod
    def clear(cls) -> None:
        cls._subscribers.clear()
        cls._event_history.clear()

