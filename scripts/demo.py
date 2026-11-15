"""Demo real de CargoBox: ejecuta las reglas de negocio contra la API y verifica cada resultado.

No imprime resultados "de adorno": cada paso hace una petición HTTP real, compara el código de
estado (y el contenido clave) con lo que exige el BRD y marca [OK] o [FALLO]. Termina con código
de salida 1 si algún paso no coincide.

Uso (desde la raíz del proyecto):
    python scripts/demo.py                          # API en memoria + base SQLite temporal con el dataset
    python scripts/demo.py --url http://localhost:8000   # contra un servidor ya levantado
    python scripts/demo.py --url https://TU-SERVICIO.onrender.com   # contra el despliegue
"""

import argparse
import os
import sys
import tempfile
from datetime import datetime
from decimal import Decimal

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)


def _direccion(ciudad, cp, calle, numero, colonia):
    return {"calle": calle, "numero": numero, "colonia": colonia, "ciudad": ciudad, "codigo_postal": cp}


def _cuerpo_envio(guia, seguro=False, valor=0):
    return {
        "guia": guia,
        "remitente_id": "CAR-C001",
        "destinatario_nombre": "Laura Méndez",
        "direccion_origen": _direccion("Monterrey", "64000", "Av. Constitución", "450", "Centro"),
        "direccion_destino": _direccion("Guadalajara", "44100", "Av. Vallarta", "1200", "Americana"),
        "peso_kg": 4.5,
        "seguro_amparado": seguro,
        "valor_declarado": valor,
        "flete_monto": 350,
    }


class Demo:
    """Ejecuta pasos contra un cliente HTTP (TestClient o httpx) y acumula los resultados."""

    def __init__(self, client, imprimir=print):
        self.client = client
        self.imprimir = imprimir
        self.resultados = []
        self.sufijo = datetime.now().strftime("%H%M%S")

    def guia(self, nombre):
        return f"CBX-{self.sufijo}-{nombre}"

    def paso(self, descripcion, metodo, url, esperado, cuerpo=None, verificar=None):
        res = self.client.request(metodo, url, json=cuerpo)
        try:
            datos = res.json()
        except ValueError:
            datos = {}
        ok = res.status_code == esperado
        detalle = ""
        if ok and verificar is not None:
            ok = bool(verificar(datos))
            detalle = " (el contenido no coincide)" if not ok else ""
        marca = "[OK]   " if ok else "[FALLO]"
        resumen = datos.get("detail") if isinstance(datos, dict) and "detail" in datos else ""
        self.imprimir(f"{marca} {descripcion:<58} {metodo:<4} {url:<44} -> {res.status_code}{detalle} {str(resumen)[:60]}")
        self.resultados.append((descripcion, ok))
        return datos

    def titulo(self, texto):
        self.imprimir(f"\n--- {texto}")

    def avanzar(self, guia, hasta="EN_REPARTO"):
        for destino in ("CLASIFICADO", "EN_TRANSITO", "DISTRIBUCION_LOCAL", "EN_REPARTO"):
            self.paso(f"Avanzar a {destino}", "POST", f"/envios/{guia}/avanzar", 200,
                      {"destino": destino}, lambda d, x=destino: d["estado"] == x)
            if destino == hasta:
                break

    def crear(self, nombre, **kw):
        guia = self.guia(nombre)
        self.paso(f"Registrar envío {nombre}", "POST", "/envios/", 201, _cuerpo_envio(guia, **kw),
                  lambda d: d["estado"] == "RECIBIDO")
        return guia


def ejecutar(client, incluir_operaciones=True, imprimir=print):
    """Recorre los escenarios principales del negocio. Devuelve la lista (descripcion, ok)."""
    d = Demo(client, imprimir)

    d.titulo("Salud del servicio")
    d.paso("Health check con base de datos", "GET", "/health", 200, verificar=lambda r: r["database"] == "connected")

    d.titulo("US1, US3, US8: registro, guía única y CEDIS por código postal")
    g_a = d.guia("A01")
    d.paso("Registrar envío (CP 44100 -> CEDIS Guadalajara)", "POST", "/envios/", 201, _cuerpo_envio(g_a),
           lambda r: r["estado"] == "RECIBIDO" and r["cedis_actual"] == "CEDIS-OCCIDENTE-GUADALAJARA")
    d.paso("Guía duplicada se rechaza", "POST", "/envios/", 409, _cuerpo_envio(g_a))
    d.paso("Guía menor a 6 caracteres se rechaza", "POST", "/envios/", 422, _cuerpo_envio("A1"))

    d.titulo("RN-07: avance secuencial (sin saltos)")
    d.paso("Saltar RECIBIDO -> EN_REPARTO se rechaza", "POST", f"/envios/{g_a}/avanzar", 409, {"destino": "EN_REPARTO"})

    d.titulo("US2 / RN-01: cancelación solo en sucursal")
    g_b1 = d.crear("B01")
    d.paso("Cancelar en RECIBIDO", "POST", f"/envios/{g_b1}/cancelar", 200, {"motivo": "Error en datos"},
           lambda r: r["estado"] == "CANCELADO")
    g_b2 = d.crear("B02")
    d.avanzar(g_b2, "EN_TRANSITO")
    d.paso("Cancelar en EN_TRANSITO se rechaza", "POST", f"/envios/{g_b2}/cancelar", 409, {"motivo": "Tarde"})

    d.titulo("US7 / RN-03: cambio de dirección")
    nueva = _direccion("Guadalajara", "44100", "Av. López Mateos", "2375", "Chapalita")
    d.paso("EN_TRANSITO + ATENCION_CLIENTES", "POST", f"/envios/{g_b2}/direccion", 200,
           {"nueva_direccion": nueva, "rol_solicitante": "ATENCION_CLIENTES"})
    d.paso("EN_TRANSITO + REPARTIDOR (sin permiso)", "POST", f"/envios/{g_b2}/direccion", 409,
           {"nueva_direccion": nueva, "rol_solicitante": "REPARTIDOR"})
    d.paso("Avanzar a DISTRIBUCION_LOCAL", "POST", f"/envios/{g_b2}/avanzar", 200, {"destino": "DISTRIBUCION_LOCAL"})
    d.paso("DISTRIBUCION_LOCAL: ya no se puede cambiar", "POST", f"/envios/{g_b2}/direccion", 409,
           {"nueva_direccion": nueva, "rol_solicitante": "ATENCION_CLIENTES"})

    d.titulo("US10 / RN-02: máximo 2 intentos de entrega")
    g_e = d.crear("E01")
    d.avanzar(g_e)
    d.paso("Intento fallido #1 -> DISTRIBUCION_LOCAL", "POST", f"/envios/{g_e}/intento-fallido", 200, {"motivo": "Ausente"},
           lambda r: r["estado"] == "DISTRIBUCION_LOCAL" and r["intentos_entrega"] == 1)
    d.paso("Volver a EN_REPARTO", "POST", f"/envios/{g_e}/avanzar", 200, {"destino": "EN_REPARTO"})
    d.paso("Intento fallido #2 -> DEVOLUCION_ORIGEN", "POST", f"/envios/{g_e}/intento-fallido", 200, {"motivo": "Ausente"},
           lambda r: r["estado"] == "DEVOLUCION_ORIGEN" and r["intentos_entrega"] == 2)
    d.paso("Intento fallido #3 se rechaza", "POST", f"/envios/{g_e}/intento-fallido", 409, {"motivo": "Ausente"})

    d.titulo("US13 / RN-07: entrega solo con evidencia")
    g_f = d.crear("F01")
    d.paso("Entregar sin estar EN_REPARTO se rechaza", "POST", f"/envios/{g_f}/entregar", 409,
           {"receptor": "Laura", "evidencia_id": "FIRMA_01"})
    d.avanzar(g_f)
    d.paso("Entregar sin nombre de receptor se rechaza", "POST", f"/envios/{g_f}/entregar", 409,
           {"receptor": "", "evidencia_id": "FIRMA_01"})
    d.paso("Entregar con receptor y evidencia", "POST", f"/envios/{g_f}/entregar", 200,
           {"receptor": "Laura Méndez", "evidencia_id": "FIRMA_DIGITAL_09"}, lambda r: r["estado"] == "ENTREGADO")

    d.titulo("US9 y US11 / RN-09: incidencias")
    g_g = d.crear("G01")
    d.avanzar(g_g)
    d.paso("Daño sin evidencia se rechaza", "POST", f"/envios/{g_g}/incidencias", 422,
           {"tipo": "PAQUETE_DANADO", "descripcion": "Rotura"})
    d.paso("Daño con evidencia FOTO_ROTURA_01", "POST", f"/envios/{g_g}/incidencias", 201,
           {"tipo": "PAQUETE_DANADO", "descripcion": "Rotura", "evidencia_id": "FOTO_ROTURA_01"},
           lambda r: r["evidencia_id"] == "FOTO_ROTURA_01")
    d.paso("Dirección incorrecta -> DISTRIBUCION_LOCAL", "POST", f"/envios/{g_g}/incidencias", 201,
           {"tipo": "DIRECCION_INCORRECTA", "descripcion": "El número no existe"},
           lambda r: r["estado_envio"] == "DISTRIBUCION_LOCAL")

    d.titulo("US12 / RN-04: indemnización")
    g_h1 = d.crear("H01", seguro=True, valor=5000)
    d.paso("CON seguro: reclamo 3,000 -> autoriza 3,000", "POST", f"/envios/{g_h1}/indemnizacion", 200,
           {"monto_reclamado": 3000, "rol_dictaminador": "ANALISTA_CALIDAD"},
           lambda r: Decimal(str(r["monto_autorizado"])) == Decimal("3000"))
    g_h2 = d.crear("H02")
    d.paso("SIN seguro: reclamo 4,000 -> tope flete 350", "POST", f"/envios/{g_h2}/indemnizacion", 200,
           {"monto_reclamado": 4000, "rol_dictaminador": "ANALISTA_CALIDAD"},
           lambda r: Decimal(str(r["monto_autorizado"])) == Decimal("350"))
    d.paso("Rol REPARTIDOR no puede dictaminar", "POST", f"/envios/{g_h2}/indemnizacion", 422,
           {"monto_reclamado": 4000, "rol_dictaminador": "REPARTIDOR"})

    d.titulo("US5, US6, US14, US15: rastreo, alertas y reportes")
    d.paso("Rastreo con historial completo", "GET", f"/envios/{g_f}/rastreo", 200,
           verificar=lambda r: [m["estado"] for m in r["historial"]][-1] == "ENTREGADO" and len(r["historial"]) == 6)
    d.paso("Alertas de rastreo detenido", "GET", "/envios/alertas/rastreo-detenido", 200)
    d.paso("Reporte de entregas a tiempo", "GET", "/reportes/entregas-a-tiempo", 200,
           verificar=lambda r: r["total_entregados"] >= 1 and r["sla_horas"] == 72)
    d.paso("Reporte de incidencias por tipo", "GET", "/reportes/incidencias", 200,
           verificar=lambda r: r["total_incidencias"] >= 3)
    d.paso("Envío inexistente", "GET", "/envios/NO-EXISTE", 404)

    if incluir_operaciones:
        d.titulo("RN-05 y RN-06 (Specification) y State Machine de operaciones")
        d.paso("CAR-O001 cumple PuedeProcesarse", "GET", "/operaciones/CAR-O001/validar", 200, verificar=lambda r: r["cumple"] is True)
        d.paso("CAR-O008 NO cumple PuedeProcesarse", "GET", "/operaciones/CAR-O008/validar", 200, verificar=lambda r: r["cumple"] is False)
        d.paso("CAR-O001 NO aplica beneficio VIP", "GET", "/operaciones/CAR-O001/beneficio", 200, verificar=lambda r: r["cumple"] is False)
        d.paso("CAR-O005 SÍ aplica beneficio VIP", "GET", "/operaciones/CAR-O005/beneficio", 200, verificar=lambda r: r["cumple"] is True)
        d.paso("CAR-O005 aprobar -> CLASIFICADO", "POST", "/operaciones/CAR-O005/transicion", 200, {"accion": "aprobar"},
               lambda r: r["estado_nuevo"] == "CLASIFICADO")
        d.paso("CAR-O004 saltar_estado se rechaza", "POST", "/operaciones/CAR-O004/transicion", 409, {"accion": "saltar_estado"})
        d.paso("CAR-O003 repetir_aprobacion se rechaza", "POST", "/operaciones/CAR-O003/transicion", 409, {"accion": "repetir_aprobacion"})

    return d.resultados


def main():
    parser = argparse.ArgumentParser(description="Demo real de la API de CargoBox")
    parser.add_argument("--url", help="URL base de un servidor ya levantado (por defecto usa la API en memoria)")
    args = parser.parse_args()

    if args.url:
        import httpx

        with httpx.Client(base_url=args.url.rstrip("/"), timeout=90) as cliente:
            resultados = ejecutar(cliente)
    else:
        os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(tempfile.mkdtemp(), "demo.sqlite3")
        import cargar_datos  # scripts/cargar_datos.py: crea tablas y carga el dataset
        from fastapi.testclient import TestClient

        from src.api.main import app

        cargar_datos.poblar_base_datos()
        with TestClient(app) as cliente:
            resultados = ejecutar(cliente)

    correctos = sum(1 for _, ok in resultados if ok)
    print(f"\nResultado: {correctos}/{len(resultados)} pasos correctos")
    sys.exit(0 if correctos == len(resultados) else 1)


if __name__ == "__main__":
    main()
