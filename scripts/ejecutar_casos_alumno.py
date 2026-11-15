"""Script para ejecutar todos los casos y transiciones de prueba oficiales del PIA.

Genera los archivos CSV resueltos con los resultados y evidencias correspondientes.
"""

import csv
import os
import sys
from decimal import Decimal

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

from src.domain.entities import Actor, DetalleOperacion, Operacion, Recurso  # noqa: E402
from src.domain.enums import EstadoOperacion  # noqa: E402
from src.domain.exceptions import TransicionInvalidaException  # noqa: E402
from src.domain.specifications import (  # noqa: E402
    BeneficioReferenciaSpecification,
    PuedeProcesarseSpecification,
)
from src.domain.state_machine import OperacionStateMachine  # noqa: E402


def resolver_casos_y_transiciones():
    base_dir = RAIZ
    datos_dir = os.path.join(base_dir, "datos")

    print("[*] Leyendo datos para resolver casos y transiciones oficiales...")

    # Cargar Actores
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

    # Cargar Catálogo
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

    # Cargar Detalles
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

    # Cargar Operaciones
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

    # 1. Resolver casos_prueba.csv (120 casos)
    casos_resueltos = []
    spec_puede = PuedeProcesarseSpecification()
    spec_ben = BeneficioReferenciaSpecification()

    with open(os.path.join(datos_dir, "casos_prueba.csv"), encoding="utf-8-sig") as f:
        casos = list(csv.DictReader(f))

    for c in casos:
        op = operaciones[c["operacion_id"]]
        tipo = c["tipo_prueba"]
        if tipo == "validar_operacion":
            cumple = spec_puede.is_satisfied_by(op)
            exp = spec_puede.explain(op)
            resultado = "VALIDA" if cumple else "INVALIDA"
        elif tipo == "evaluar_beneficio":
            cumple = spec_ben.is_satisfied_by(op)
            exp = spec_ben.explain(op)
            resultado = "APLICA_BENEFICIO" if cumple else "NO_APLICA"
        else:
            resultado = "DESCONOCIDO"
            exp = ""

        c_copia = dict(c)
        c_copia["resultado_alumno"] = resultado
        c_copia["evidencia_explicacion"] = exp
        casos_resueltos.append(c_copia)

    out_casos = os.path.join(datos_dir, "casos_prueba_RESUELTO.csv")
    with open(out_casos, "w", newline="", encoding="utf-8-sig") as f:
        fieldnames = [
            "caso_id",
            "operacion_id",
            "tipo_prueba",
            "regla_a_verificar",
            "resultado_alumno",
            "evidencia_explicacion",
            "instrucciones",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(casos_resueltos)
    print(f"   [+] Generado: {out_casos} (120 casos resueltos)")

    # 2. Resolver transiciones_prueba.csv (20 casos)
    trans_resueltas = []
    with open(os.path.join(datos_dir, "transiciones_prueba.csv"), encoding="utf-8-sig") as f:
        trans = list(csv.DictReader(f))

    for t in trans:
        op_id = t["operacion_id"]
        accion = t["accion_sugerida"]
        estado_ini = EstadoOperacion(t["estado_inicial"])

        try:
            nuevo_est = OperacionStateMachine.ejecutar_transicion(op_id, estado_ini, accion)
            res = f"EXITO: {nuevo_est.value}"
            detalle = f"Transición a {nuevo_est.value} ejecutada con emisión de evento de dominio"
        except TransicionInvalidaException as ex:
            res = "RECHAZADA: TransicionInvalidaException"
            detalle = ex.mensaje

        t_copia = dict(t)
        t_copia["resultado_alumno"] = res
        t_copia["evidencia_evento_excepcion"] = detalle
        trans_resueltas.append(t_copia)

    out_trans = os.path.join(datos_dir, "transiciones_prueba_RESUELTO.csv")
    with open(out_trans, "w", newline="", encoding="utf-8-sig") as f:
        fieldnames = [
            "caso_id",
            "operacion_id",
            "accion_sugerida",
            "estado_inicial",
            "resultado_alumno",
            "evidencia_evento_excepcion",
            "instrucciones",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(trans_resueltas)
    print(f"   [+] Generado: {out_trans} (20 transiciones resueltas)")

    print("[OK] Proceso de resolución completado con éxito.")


if __name__ == "__main__":
    resolver_casos_y_transiciones()

