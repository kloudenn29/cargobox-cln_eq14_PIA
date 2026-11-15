"""Pruebas unitarias para la Máquina de Estados de Operaciones y Envíos."""

import pytest

from src.domain.enums import EstadoEnvio, EstadoOperacion
from src.domain.exceptions import (
    CancelacionNoPermitidaException,
    IntentoEntregaAgotadoException,
    TransicionInvalidaException,
)
from src.domain.state_machine import EnvioStateMachine, OperacionStateMachine


class TestOperacionStateMachine:
    def test_aprobar_desde_recibido(self):
        r = OperacionStateMachine.ejecutar_transicion(
            "OP-1", EstadoOperacion.RECIBIDO, "aprobar"
        )
        assert r == EstadoOperacion.CLASIFICADO

    def test_cancelar_desde_recibido(self):
        r = OperacionStateMachine.ejecutar_transicion(
            "OP-2", EstadoOperacion.RECIBIDO, "cancelar"
        )
        assert r == EstadoOperacion.CANCELADO

    def test_completar_desde_recibido(self):
        r = OperacionStateMachine.ejecutar_transicion(
            "OP-3", EstadoOperacion.RECIBIDO, "completar"
        )
        assert r == EstadoOperacion.ENTREGADO

    def test_completar_desde_en_transito(self):
        r = OperacionStateMachine.ejecutar_transicion(
            "OP-4", EstadoOperacion.EN_TRANSITO, "completar"
        )
        assert r == EstadoOperacion.ENTREGADO

    def test_saltar_estado_rechazado(self):
        with pytest.raises(TransicionInvalidaException) as exc_info:
            OperacionStateMachine.ejecutar_transicion(
                "OP-5", EstadoOperacion.RECIBIDO, "saltar_estado"
            )
        assert "saltar" in str(exc_info.value).lower()

    def test_repetir_aprobacion_rechazada(self):
        with pytest.raises(TransicionInvalidaException):
            OperacionStateMachine.ejecutar_transicion(
                "OP-6", EstadoOperacion.RECIBIDO, "repetir_aprobacion"
            )

    def test_cancelar_desde_entregado_imposible(self):
        with pytest.raises(TransicionInvalidaException):
            OperacionStateMachine.ejecutar_transicion(
                "OP-7", EstadoOperacion.ENTREGADO, "cancelar"
            )

    def test_cancelar_desde_clasificado_imposible(self):
        with pytest.raises(TransicionInvalidaException):
            OperacionStateMachine.ejecutar_transicion(
                "OP-8", EstadoOperacion.CLASIFICADO, "cancelar"
            )

    def test_puede_transicionar_verdadero(self):
        assert OperacionStateMachine.puede_transicionar(EstadoOperacion.RECIBIDO, "aprobar")

    def test_puede_transicionar_falso(self):
        assert not OperacionStateMachine.puede_transicionar(EstadoOperacion.ENTREGADO, "cancelar")


class TestEnvioStateMachine:
    def test_cancelacion_en_recibido_valida(self):
        # No debe lanzar excepción
        EnvioStateMachine.validar_cancelacion(EstadoEnvio.RECIBIDO)

    def test_cancelacion_en_transito_invalida(self):
        with pytest.raises(CancelacionNoPermitidaException):
            EnvioStateMachine.validar_cancelacion(EstadoEnvio.EN_TRANSITO)

    def test_cancelacion_en_entregado_invalida(self):
        with pytest.raises(CancelacionNoPermitidaException):
            EnvioStateMachine.validar_cancelacion(EstadoEnvio.ENTREGADO)

    def test_primer_intento_fallido_reprograma(self):
        estado, intentos = EnvioStateMachine.procesar_intento_fallido("G-1", 0)
        assert estado == EstadoEnvio.DISTRIBUCION_LOCAL
        assert intentos == 1

    def test_segundo_intento_devolucion(self):
        estado, intentos = EnvioStateMachine.procesar_intento_fallido("G-2", 1)
        assert estado == EstadoEnvio.DEVOLUCION_ORIGEN
        assert intentos == 2

    def test_tercer_intento_rechazado(self):
        with pytest.raises(IntentoEntregaAgotadoException):
            EnvioStateMachine.procesar_intento_fallido("G-3", 2)

