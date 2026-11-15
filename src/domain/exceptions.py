"""Excepciones de Dominio de CargoBox."""


class DomainException(Exception):
    """Excepción base para violaciones de invariantes de dominio."""
    def __init__(self, mensaje: str, codigo: str = "ERROR_DOMINIO"):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.codigo = codigo


class TransicionInvalidaException(DomainException):
    """Lanzada cuando se intenta una transición de estado prohibida en la máquina de estados."""
    def __init__(self, estado_actual: str, accion_o_destino: str, detalle: str = ""):
        msg = f"Transición inválida desde '{estado_actual}' mediante acción/destino '{accion_o_destino}'."
        if detalle:
            msg += f" Motivo: {detalle}"
        super().__init__(msg, codigo="TRANSICION_INVALIDA")
        self.estado_actual = estado_actual
        self.accion_o_destino = accion_o_destino


class ReglaNegocioException(DomainException):
    """Lanzada ante la violación de una regla de negocio explícita."""
    def __init__(self, regla: str, detalle: str):
        super().__init__(f"Violación de regla [{regla}]: {detalle}", codigo="REGLA_NEGOCIO_VIOLADA")
        self.regla = regla


class EntidadNoEncontradaException(DomainException):
    """Lanzada cuando un agregado o entidad no existe en el repositorio."""
    def __init__(self, entidad: str, identificador: str):
        super().__init__(f"No se encontró {entidad} con identificador '{identificador}'.", codigo="ENTIDAD_NO_ENCONTRADA")
        self.entidad = entidad
        self.identificador = identificador


class CancelacionNoPermitidaException(DomainException):
    """Lanzada cuando un envío u operación ya no puede ser cancelada."""
    def __init__(self, estado: str, motivo: str = "Solo se permite cancelar en estado RECIBIDO"):
        super().__init__(f"No se puede cancelar en estado '{estado}'. {motivo}.", codigo="CANCELACION_NO_PERMITIDA")
        self.estado = estado


class IntentoEntregaAgotadoException(DomainException):
    """Lanzada cuando se superan los 2 intentos permitidos de entrega a domicilio."""
    def __init__(self, intentos: int):
        super().__init__(f"Se superó el límite de {intentos} intentos de entrega. El paquete debe retornar a origen.", codigo="INTENTOS_AGOTADOS")
        self.intentos = intentos


class ModificacionDireccionNoPermitidaException(DomainException):
    """Lanzada cuando se intenta modificar la dirección de entrega habiendo arribado a distribución local."""
    def __init__(self, estado: str):
        super().__init__(f"No es posible modificar la dirección de entrega en estado '{estado}'. Paquete ya en CEDIS destino.", codigo="DIRECCION_BLOQUEADA")
        self.estado = estado


class SeguroInvalidoException(DomainException):
    """Lanzada cuando la configuración del seguro o valor declarado es inválida."""
    def __init__(self, detalle: str):
        super().__init__(f"Póliza de seguro inválida: {detalle}", codigo="SEGURO_INVALIDO")


class AutorizacionRequeridaException(DomainException):
    """Lanzada cuando la operación no cuenta con la autorización o el rol adecuado."""
    def __init__(self, detalle: str):
        super().__init__(f"Autorización denegada: {detalle}", codigo="NO_AUTORIZADO")



class GuiaDuplicadaException(DomainException):
    """Lanzada cuando se intenta registrar un envío con una guía de rastreo ya existente (US3)."""
    def __init__(self, guia: str):
        super().__init__(f"La guía de rastreo '{guia}' ya existe. Cada envío debe tener una guía única.", codigo="GUIA_DUPLICADA")
        self.guia = guia
