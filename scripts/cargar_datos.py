"""Carga inicial de datos desde los CSV a la base de datos configurada en DATABASE_URL (PostgreSQL o SQLite).

Es idempotente: si los registros ya existen no se duplican."""

import csv
import os
import sys
from decimal import Decimal

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

from src.infrastructure.database import Base, SessionLocal, engine  # noqa: E402
from src.infrastructure.models import (  # noqa: E402
    ActorModel,
    DetalleOperacionModel,
    OperacionModel,
    RecursoModel,
)


def poblar_base_datos():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()

    base_dir = RAIZ
    datos_dir = os.path.join(base_dir, "datos")

    print("[*] Iniciando carga de datos...")

    # 1. Cargar Actores
    with open(os.path.join(datos_dir, "actores.csv"), encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            existing = session.query(ActorModel).filter_by(actor_id=r["actor_id"]).first()
            if not existing:
                session.add(
                    ActorModel(
                        actor_id=r["actor_id"],
                        nombre=r["nombre"],
                        es_preferente=bool(int(r["es_preferente"])),
                        activo=bool(int(r["activo"])),
                        ciudad=r["ciudad"],
                    )
                )
    session.commit()
    print("   [+] Actores cargados con éxito.")

    # 2. Cargar Catálogo
    precios = {}
    with open(os.path.join(datos_dir, "catalogo.csv"), encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            existing = session.query(RecursoModel).filter_by(recurso_id=r["recurso_id"]).first()
            precios[r["recurso_id"]] = Decimal(r["precio_mxn"])
            if not existing:
                session.add(
                    RecursoModel(
                        recurso_id=r["recurso_id"],
                        descripcion=r["descripcion"],
                        precio_mxn=Decimal(r["precio_mxn"]),
                        capacidad_o_stock=int(r["capacidad_o_stock"]),
                        habilitado=bool(int(r["habilitado"])),
                    )
                )
    session.commit()
    print("   [+] Catálogo de recursos cargado con éxito.")

    # 3. Cargar Operaciones
    with open(os.path.join(datos_dir, "operaciones.csv"), encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            existing = session.query(OperacionModel).filter_by(operacion_id=r["operacion_id"]).first()
            if not existing:
                session.add(
                    OperacionModel(
                        operacion_id=r["operacion_id"],
                        actor_id=r["actor_id"],
                        estado=r["estado_inicial"],
                        fecha_solicitud=r["fecha_solicitud"],
                        promocion_activa=bool(int(r["promocion_activa"])),
                        autorizado=bool(int(r["autorizado"])),
                        referencia=r["referencia"],
                        total=Decimal("0.00"),
                    )
                )
    session.commit()
    print("   [+] Operaciones cargadas con éxito.")

    # 4. Cargar Detalles y calcular totales (solo si aún no existen: evita duplicar al reiniciar)
    if session.query(DetalleOperacionModel).count() > 0:
        print("   [=] Detalles de operación ya cargados; se omite para no duplicar.")
        session.close()
        print("[OK] Carga de base de datos finalizada exitosamente.")
        return

    totales_por_op = {}
    with open(os.path.join(datos_dir, "detalle_operaciones.csv"), encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            op_id = r["operacion_id"]
            rec_id = r["recurso_id"]
            cant = int(r["cantidad"])
            p_unit = precios.get(rec_id, Decimal("0.00"))
            subtotal = p_unit * Decimal(cant)
            totales_por_op[op_id] = totales_por_op.get(op_id, Decimal("0.00")) + subtotal

            session.add(
                DetalleOperacionModel(
                    operacion_id=op_id,
                    recurso_id=rec_id,
                    cantidad=cant,
                    precio_unitario=p_unit,
                )
            )
    session.commit()

    # Actualizar totales en tabla operaciones
    for op_id, total in totales_por_op.items():
        op = session.query(OperacionModel).filter_by(operacion_id=op_id).first()
        if op:
            op.total = total
    session.commit()
    print("   [+] Detalles de operación cargados y totales calculados con Decimal.")

    session.close()
    print("[OK] Carga de base de datos finalizada exitosamente.")


if __name__ == "__main__":
    poblar_base_datos()

