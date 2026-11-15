"""Pruebas automatizadas sobre las 20 transiciones de prueba del dataset CargoBox."""

import csv
import os

import pytest

from src.domain.enums import EstadoOperacion
from src.domain.exceptions import TransicionInvalidaException
from src.domain.state_machine import OperacionStateMachine


def _cargar_transiciones(datos_dir: str):
    transiciones = []
    with open(os.path.join(datos_dir, "transiciones_prueba.csv"), encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            transiciones.append(r)
    return transiciones


_DATOS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "datos"
)
_TRANSICIONES = _cargar_transiciones(_DATOS_DIR)


@pytest.mark.parametrize("t", _TRANSICIONES, ids=[c["caso_id"] for c in _TRANSICIONES])
def test_ejecutar_transicion_dataset(t):
    """Ejecuta cada caso de transición en la máquina de estados y verifica coherencia."""
    op_id = t["operacion_id"]
    accion = t["accion_sugerida"]
    estado_ini = EstadoOperacion(t["estado_inicial"])

    if accion in ["saltar_estado", "repetir_aprobacion"]:
        # Debe fallar con TransicionInvalidaException
        with pytest.raises(TransicionInvalidaException):
            OperacionStateMachine.ejecutar_transicion(op_id, estado_ini, accion)
    elif accion == "aprobar":
        nuevo = OperacionStateMachine.ejecutar_transicion(op_id, estado_ini, accion)
        assert nuevo == EstadoOperacion.CLASIFICADO
    elif accion == "cancelar":
        nuevo = OperacionStateMachine.ejecutar_transicion(op_id, estado_ini, accion)
        assert nuevo == EstadoOperacion.CANCELADO
    elif accion == "completar":
        nuevo = OperacionStateMachine.ejecutar_transicion(op_id, estado_ini, accion)
        assert nuevo == EstadoOperacion.ENTREGADO
    else:
        pytest.fail(f"Acción no reconocida en prueba: {accion}")
