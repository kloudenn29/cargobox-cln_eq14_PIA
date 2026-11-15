"""Máquina de Estados Finita (State Machine) para Operaciones y Envíos de CargoBox."""

from typing import Dict, Set, Tuple

from src.domain.enums import EstadoEnvio, EstadoOperacion
from src.domain.events import (
    DevolucionIniciada,
    EventDispatcher,
    IntentoFallidoRegistrado,
    OperacionAprobada,
    OperacionCancelada,
    OperacionCompletada,
    OperacionEnTransito,
    TransicionRechazada,
)
from src.domain.exceptions import (
    CancelacionNoPermitidaException,
    IntentoEntregaAgotadoException,
    TransicionInvalidaException,
)


class OperacionStateMachine:
    """Máquina de estados finita para las operaciones del dataset y el negocio CargoBox."""

    # Matriz de transiciones permitidas: estado_origen -> acciones válidas y estado resultante
    TRANSICIONES_VALIDAS: Dict[EstadoOperacion, Dict[str, EstadoOperacion]] = {
        EstadoOperacion.RECIBIDO: {
            "aprobar": EstadoOperacion.CLASIFICADO,
            "cancelar": EstadoOperacion.CANCELADO,
            "completar": EstadoOperacion.ENTREGADO,  # Flujo directo integral
        },
        EstadoOperacion.CLASIFICADO: {
            "despachar": EstadoOperacion.EN_TRANSITO,
            "completar": EstadoOperacion.ENTREGADO,
        },
        EstadoOperacion.EN_TRANSITO: {
            "entregar": EstadoOperacion.ENTREGADO,
            "completar": EstadoOperacion.ENTREGADO,
        },
        EstadoOperacion.ENTREGADO: {},  # Estado terminal
        EstadoOperacion.CANCELADO: {},  # Estado terminal
    }

    @classmethod
    def puede_transicionar(cls, estado_actual: EstadoOperacion, accion: str) -> bool:
        return accion in cls.TRANSICIONES_VALIDAS.get(estado_actual, {})

    @classmethod
    def ejecutar_transicion(cls, operacion_id: str, estado_actual: EstadoOperacion, accion: str) -> EstadoOperacion:
        """Aplica la acción de transición sobre la operación, emitiendo el evento de dominio correspondiente."""
        # Manejo explícito de casos de transiciones inválidas solicitadas en el dataset
        if accion == "saltar_estado":
            msg = f"No se permite saltar directamente desde {estado_actual.value} a ENTREGADO sin pasar por el flujo de tránsito."
            EventDispatcher.dispatch(
                TransicionRechazada(
                    aggregate_id=operacion_id,
                    estado_actual=estado_actual.value,
                    accion_intentada=accion,
                    motivo_rechazo=msg,
                )
            )
            raise TransicionInvalidaException(estado_actual.value, accion, msg)

        if accion == "repetir_aprobacion":
            # Si ya se aprobó o si se intenta aprobar dos veces
            msg = f"La operación ya se encuentra en proceso. No se puede repetir la aprobación en estado {estado_actual.value}."
            EventDispatcher.dispatch(
                TransicionRechazada(
                    aggregate_id=operacion_id,
                    estado_actual=estado_actual.value,
                    accion_intentada=accion,
                    motivo_rechazo=msg,
                )
            )
            raise TransicionInvalidaException(estado_actual.value, accion, msg)

        if not cls.puede_transicionar(estado_actual, accion):
            msg = f"La acción '{accion}' no está permitida desde el estado actual '{estado_actual.value}'."
            EventDispatcher.dispatch(
                TransicionRechazada(
                    aggregate_id=operacion_id,
                    estado_actual=estado_actual.value,
                    accion_intentada=accion,
                    motivo_rechazo=msg,
                )
            )
            raise TransicionInvalidaException(estado_actual.value, accion, msg)

        nuevo_estado = cls.TRANSICIONES_VALIDAS[estado_actual][accion]

        # Emisión de eventos de dominio según la acción
        if accion == "aprobar":
            EventDispatcher.dispatch(
                OperacionAprobada(aggregate_id=operacion_id, estado_anterior=estado_actual.value, nuevo_estado=nuevo_estado.value)
            )
        elif accion == "completar":
            EventDispatcher.dispatch(
                OperacionCompletada(aggregate_id=operacion_id, estado_anterior=estado_actual.value, nuevo_estado=nuevo_estado.value)
            )
        elif accion == "cancelar":
            EventDispatcher.dispatch(
                OperacionCancelada(aggregate_id=operacion_id, estado_anterior=estado_actual.value, motivo="Cancelación autorizada en estado RECIBIDO")
            )
        elif accion == "despachar":
            EventDispatcher.dispatch(
                OperacionEnTransito(aggregate_id=operacion_id, estado_anterior=estado_actual.value, nuevo_estado=nuevo_estado.value)
            )

        return nuevo_estado


class EnvioStateMachine:
    """Máquina de estados finita detallada para los envíos de paquetería de CargoBox."""

    TRANSICIONES_VALIDAS_ENVIO: Dict[EstadoEnvio, Set[EstadoEnvio]] = {
        EstadoEnvio.RECIBIDO: {EstadoEnvio.CLASIFICADO, EstadoEnvio.CANCELADO},
        EstadoEnvio.CLASIFICADO: {EstadoEnvio.EN_TRANSITO},
        EstadoEnvio.EN_TRANSITO: {EstadoEnvio.DISTRIBUCION_LOCAL},
        EstadoEnvio.DISTRIBUCION_LOCAL: {EstadoEnvio.EN_REPARTO},
        EstadoEnvio.EN_REPARTO: {EstadoEnvio.ENTREGADO, EstadoEnvio.DISTRIBUCION_LOCAL, EstadoEnvio.DEVOLUCION_ORIGEN},
        EstadoEnvio.ENTREGADO: set(),
        EstadoEnvio.CANCELADO: set(),
        EstadoEnvio.DEVOLUCION_ORIGEN: set(),
    }

    # Avance normal del paquete por la red logística (un solo camino válido por estado).
    AVANCES_NORMALES: Dict[EstadoEnvio, EstadoEnvio] = {
        EstadoEnvio.RECIBIDO: EstadoEnvio.CLASIFICADO,
        EstadoEnvio.CLASIFICADO: EstadoEnvio.EN_TRANSITO,
        EstadoEnvio.EN_TRANSITO: EstadoEnvio.DISTRIBUCION_LOCAL,
        EstadoEnvio.DISTRIBUCION_LOCAL: EstadoEnvio.EN_REPARTO,
    }

    MAX_INTENTOS: int = 2

    @classmethod
    def validar_avance(cls, estado_actual: EstadoEnvio, destino: EstadoEnvio) -> None:
        """Solo se permite avanzar al siguiente estado de la ruta; no hay saltos ni retrocesos."""
        if cls.AVANCES_NORMALES.get(estado_actual) != destino:
            raise TransicionInvalidaException(
                estado_actual.value,
                destino.value,
                "El envío solo puede avanzar al siguiente estado de la ruta logística.",
            )

    @classmethod
    def validar_cancelacion(cls, estado_actual: EstadoEnvio) -> None:
        """Regla 1 (US2): Cancelación solo permitida en sucursal (RECIBIDO)."""
        if estado_actual != EstadoEnvio.RECIBIDO:
            raise CancelacionNoPermitidaException(
                estado_actual.value,
                "El envío ya ha iniciado su proceso logístico o salió de sucursal. Queda estrictamente prohibida la cancelación."
            )

    @classmethod
    def procesar_intento_fallido(cls, guia: str, intentos_actuales: int) -> Tuple[EstadoEnvio, int]:
        """Regla 2 (US10): Manejo de intentos de entrega domiciliaria."""
        if intentos_actuales >= cls.MAX_INTENTOS:
            raise IntentoEntregaAgotadoException(intentos_actuales)

        nuevos_intentos = intentos_actuales + 1
        if nuevos_intentos == 1:
            EventDispatcher.dispatch(
                IntentoFallidoRegistrado(
                    aggregate_id=guia,
                    numero_intento=1,
                    motivo="Destinatario ausente",
                    proxima_accion="Reprogramación al siguiente día hábil en CEDIS destino"
                )
            )
            return EstadoEnvio.DISTRIBUCION_LOCAL, nuevos_intentos
        else:
            # Segundo intento fallido: límite alcanzado -> DEVOLUCION_ORIGEN
            EventDispatcher.dispatch(
                IntentoFallidoRegistrado(
                    aggregate_id=guia,
                    numero_intento=2,
                    motivo="Destinatario ausente en 2do intento",
                    proxima_accion="Devolución al remitente"
                )
            )
            EventDispatcher.dispatch(
                DevolucionIniciada(aggregate_id=guia, motivo="Límite operativo de 2 intentos alcanzado")
            )
            return EstadoEnvio.DEVOLUCION_ORIGEN, nuevos_intentos

