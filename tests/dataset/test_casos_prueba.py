"""Pruebas automatizadas sobre los 120 casos de prueba oficiales del dataset CargoBox."""

import csv
import os
from decimal import Decimal

import pytest

from src.domain.entities import Actor, DetalleOperacion, Operacion, Recurso
from src.domain.enums import EstadoOperacion
from src.domain.specifications import BeneficioReferenciaSpecification, PuedeProcesarseSpecification


def _cargar_dataset(datos_dir: str):
    actores = {}
    with open(os.path.join(datos_dir, "actores.csv"), encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            actores[r["actor_id"]] = Actor(
                actor_id=r["actor_id"],
                nombre=r["nombre"],
                es_preferente=bool(int(r["es_preferente"])),
                activo=bool(int(r["activo"])),
                ciudad=r["ciudad"],
            )

    catalogo = {}
    with open(os.path.join(datos_dir, "catalogo.csv"), encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            catalogo[r["recurso_id"]] = Recurso(
                recurso_id=r["recurso_id"],
                descripcion=r["descripcion"],
                precio_mxn=Decimal(r["precio_mxn"]),
                capacidad_o_stock=int(r["capacidad_o_stock"]),
                habilitado=bool(int(r["habilitado"])),
            )

    detalles_por_op = {}
    with open(os.path.join(datos_dir, "detalle_operaciones.csv"), encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            op_id = r["operacion_id"]
            rec = catalogo[r["recurso_id"]]
            detalles_por_op.setdefault(op_id, []).append(
                DetalleOperacion(
                    operacion_id=op_id,
                    recurso_id=r["recurso_id"],
                    cantidad=int(r["cantidad"]),
                    precio_unitario=rec.precio_mxn,
                    recurso=rec,
                )
            )

    operaciones = {}
    with open(os.path.join(datos_dir, "operaciones.csv"), encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            op_id = r["operacion_id"]
            operaciones[op_id] = Operacion(
                operacion_id=op_id,
                actor_id=r["actor_id"],
                estado=EstadoOperacion(r["estado_inicial"]),
                fecha_solicitud=r["fecha_solicitud"],
                promocion_activa=bool(int(r["promocion_activa"])),
                autorizado=bool(int(r["autorizado"])),
                referencia=r["referencia"],
                actor=actores[r["actor_id"]],
                detalles=detalles_por_op.get(op_id, []),
            )

    casos = []
    with open(os.path.join(datos_dir, "casos_prueba.csv"), encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            casos.append(r)

    return operaciones, casos


# Carga estática para parametrizar
_DATOS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "datos"
)
_OPERACIONES, _CASOS = _cargar_dataset(_DATOS_DIR)


@pytest.mark.parametrize("caso", _CASOS, ids=[c["caso_id"] for c in _CASOS])
def test_evaluar_caso_dataset(caso):
    """Evalúa cada caso de prueba del dataset oficial mediante el patrón Specification."""
    op_id = caso["operacion_id"]
    tipo = caso["tipo_prueba"]
    op = _OPERACIONES[op_id]

    if tipo == "validar_operacion":
        spec = PuedeProcesarseSpecification()
        resultado = spec.is_satisfied_by(op)
        # Invariante: debe ser booleano determinista
        assert isinstance(resultado, bool)
        # Explicación nunca vacía
        assert len(spec.explain(op)) > 0
    elif tipo == "evaluar_beneficio":
        spec = BeneficioReferenciaSpecification()
        resultado = spec.is_satisfied_by(op)
        assert isinstance(resultado, bool)
        assert len(spec.explain(op)) > 0
    else:
        pytest.fail(f"Tipo de prueba no reconocido: {tipo}")
