"""Enumeraciones del Dominio de CargoBox."""

from enum import Enum


class EstadoOperacion(str, Enum):
    """Estados del ciclo de vida de una operación del dataset y del negocio."""
    RECIBIDO = "RECIBIDO"
    CLASIFICADO = "CLASIFICADO"
    EN_TRANSITO = "EN_TRANSITO"
    ENTREGADO = "ENTREGADO"
    CANCELADO = "CANCELADO"


class EstadoEnvio(str, Enum):
    """Estados detallados del envío en la red logística de CargoBox."""
    RECIBIDO = "RECIBIDO"
    CLASIFICADO = "CLASIFICADO"
    EN_TRANSITO = "EN_TRANSITO"
    DISTRIBUCION_LOCAL = "DISTRIBUCION_LOCAL"
    EN_REPARTO = "EN_REPARTO"
    ENTREGADO = "ENTREGADO"
    CANCELADO = "CANCELADO"
    DEVOLUCION_ORIGEN = "DEVOLUCION_ORIGEN"


class TipoIncidencia(str, Enum):
    """Tipos de incidencias operativas en CargoBox."""
    DESTINATARIO_AUSENTE = "DESTINATARIO_AUSENTE"
    DIRECCION_INCORRECTA = "DIRECCION_INCORRECTA"
    PAQUETE_DANADO = "PAQUETE_DANADO"
    EXTRAVIO = "EXTRAVIO"
    RECHAZO = "RECHAZO"


class RolUsuario(str, Enum):
    """Roles de acceso y autorización del sistema CargoBox (RBAC)."""
    REMITENTE = "REMITENTE"
    EMPLEADO_SUCURSAL = "EMPLEADO_SUCURSAL"
    OPERADOR_CEDIS = "OPERADOR_CEDIS"
    REPARTIDOR = "REPARTIDOR"
    ATENCION_CLIENTES = "ATENCION_CLIENTES"
    ANALISTA_CALIDAD = "ANALISTA_CALIDAD"
    ADMINISTRADOR = "ADMINISTRADOR"


class NivelServicio(str, Enum):
    """Niveles de servicio logístico."""
    ESTANDAR = "ESTANDAR"
    EXPRESS = "EXPRESS"
    PRIORITARIO = "PRIORITARIO"

