"""Pruebas de integración de los endpoints de logística, incidencias, rastreo, alertas y reportes."""

from datetime import datetime, timedelta, timezone

from src.infrastructure.models import HistorialEnvioModel


def _payload(guia: str, **extra):
    base = {
        "guia": guia,
        "remitente_id": "CAR-C001",
        "destinatario_nombre": "Laura Méndez",
        "direccion_origen": {
            "calle": "Av. Constitución", "numero": "450", "colonia": "Centro",
            "ciudad": "Monterrey", "codigo_postal": "64000",
        },
        "direccion_destino": {
            "calle": "Av. Vallarta", "numero": "1200", "colonia": "Americana",
            "ciudad": "Guadalajara", "codigo_postal": "44100",
        },
        "peso_kg": 4.5,
        "seguro_amparado": True,
        "valor_declarado": 3500.00,
        "flete_monto": 420.00,
    }
    base.update(extra)
    return base


def _crear_en_reparto(client, guia: str):
    assert client.post("/envios/", json=_payload(guia)).status_code == 201
    for destino in ("CLASIFICADO", "EN_TRANSITO", "DISTRIBUCION_LOCAL", "EN_REPARTO"):
        assert client.post(f"/envios/{guia}/avanzar", json={"destino": destino}).status_code == 200


class TestGuiaUnica:
    """US3: no se permiten dos envíos con la misma guía."""

    def test_guia_duplicada_devuelve_409(self, client):
        assert client.post("/envios/", json=_payload("CBX-DUP-001")).status_code == 201
        res = client.post("/envios/", json=_payload("cbx-dup-001"))
        assert res.status_code == 409


class TestAvanceYEntrega:
    def test_ciclo_completo_hasta_entregado(self, client):
        _crear_en_reparto(client, "CBX-FLOW-001")
        res = client.post(
            "/envios/CBX-FLOW-001/entregar",
            json={"receptor": "Laura Méndez", "evidencia_id": "FIRMA_DIGITAL_09"},
        )
        assert res.status_code == 200
        assert res.json()["estado"] == "ENTREGADO"

    def test_saltar_estado_devuelve_409(self, client):
        client.post("/envios/", json=_payload("CBX-SKIP-001"))
        res = client.post("/envios/CBX-SKIP-001/avanzar", json={"destino": "EN_REPARTO"})
        assert res.status_code == 409

    def test_estado_desconocido_devuelve_422(self, client):
        client.post("/envios/", json=_payload("CBX-UNK-001"))
        res = client.post("/envios/CBX-UNK-001/avanzar", json={"destino": "VOLANDO"})
        assert res.status_code == 422

    def test_entregar_fuera_de_reparto_devuelve_409(self, client):
        client.post("/envios/", json=_payload("CBX-EARLY-001"))
        res = client.post(
            "/envios/CBX-EARLY-001/entregar", json={"receptor": "X", "evidencia_id": "F1"}
        )
        assert res.status_code == 409

    def test_guia_inexistente_devuelve_404(self, client):
        assert client.post("/envios/NO-EXISTE/avanzar", json={"destino": "CLASIFICADO"}).status_code == 404
        assert client.post("/envios/NO-EXISTE/entregar", json={"receptor": "X", "evidencia_id": "F"}).status_code == 404
        assert client.get("/envios/NO-EXISTE/rastreo").status_code == 404
        assert client.post(
            "/envios/NO-EXISTE/incidencias", json={"tipo": "EXTRAVIO", "descripcion": "x"}
        ).status_code == 404


class TestRastreo:
    """US5: historial de movimientos y fecha estimada."""

    def test_rastreo_muestra_historial(self, client):
        _crear_en_reparto(client, "CBX-TRK-001")
        res = client.get("/envios/CBX-TRK-001/rastreo")
        assert res.status_code == 200
        data = res.json()
        assert data["estado_actual"] == "EN_REPARTO"
        assert [m["estado"] for m in data["historial"]] == [
            "RECIBIDO", "CLASIFICADO", "EN_TRANSITO", "DISTRIBUCION_LOCAL", "EN_REPARTO",
        ]
        assert data["fecha_estimada_entrega"]


class TestIncidencias:
    def test_direccion_incorrecta_regresa_a_distribucion_local(self, client):
        _crear_en_reparto(client, "CBX-ADDR-001")
        res = client.post(
            "/envios/CBX-ADDR-001/incidencias",
            json={"tipo": "DIRECCION_INCORRECTA", "descripcion": "El número no existe"},
        )
        assert res.status_code == 201
        assert res.json()["estado_envio"] == "DISTRIBUCION_LOCAL"

    def test_direccion_incorrecta_fuera_de_reparto_devuelve_409(self, client):
        client.post("/envios/", json=_payload("CBX-ADDR-002"))
        res = client.post(
            "/envios/CBX-ADDR-002/incidencias",
            json={"tipo": "DIRECCION_INCORRECTA", "descripcion": "No existe"},
        )
        assert res.status_code == 409

    def test_danio_sin_evidencia_devuelve_422(self, client):
        _crear_en_reparto(client, "CBX-DMG-001")
        res = client.post(
            "/envios/CBX-DMG-001/incidencias",
            json={"tipo": "PAQUETE_DANADO", "descripcion": "Caja rota"},
        )
        assert res.status_code == 422

    def test_danio_con_evidencia_se_registra(self, client):
        _crear_en_reparto(client, "CBX-DMG-002")
        res = client.post(
            "/envios/CBX-DMG-002/incidencias",
            json={"tipo": "PAQUETE_DANADO", "descripcion": "Rotura", "evidencia_id": "FOTO_ROTURA_01"},
        )
        assert res.status_code == 201
        assert res.json()["evidencia_id"] == "FOTO_ROTURA_01"

    def test_tipo_desconocido_y_ausencia_se_rechazan(self, client):
        _crear_en_reparto(client, "CBX-TYPE-001")
        r1 = client.post("/envios/CBX-TYPE-001/incidencias", json={"tipo": "OVNI", "descripcion": "x"})
        r2 = client.post(
            "/envios/CBX-TYPE-001/incidencias",
            json={"tipo": "DESTINATARIO_AUSENTE", "descripcion": "x"},
        )
        assert r1.status_code == 422
        assert r2.status_code == 422


class TestAlertasYReportes:
    def test_alerta_rastreo_detenido(self, client, test_db):
        client.post("/envios/", json=_payload("CBX-ALERT-001"))
        client.post("/envios/CBX-ALERT-001/avanzar", json={"destino": "CLASIFICADO"})
        client.post("/envios/CBX-ALERT-001/avanzar", json={"destino": "EN_TRANSITO"})
        # Simula que la última lectura fue hace 30 horas
        ultimo = (
            test_db.query(HistorialEnvioModel)
            .filter_by(guia="CBX-ALERT-001")
            .order_by(HistorialEnvioModel.id.desc())
            .first()
        )
        ultimo.fecha = datetime.now(timezone.utc) - timedelta(hours=30)
        test_db.commit()

        res = client.get("/envios/alertas/rastreo-detenido")
        assert res.status_code == 200
        alertas = res.json()
        assert [a["guia"] for a in alertas] == ["CBX-ALERT-001"]
        assert alertas[0]["horas_sin_movimiento"] >= 30
        assert alertas[0]["notificado_a"] == "ATENCION_CLIENTES"

    def test_sin_alertas_cuando_hay_movimiento_reciente(self, client):
        client.post("/envios/", json=_payload("CBX-ALERT-002"))
        assert client.get("/envios/alertas/rastreo-detenido").json() == []

    def test_reporte_entregas_a_tiempo(self, client):
        for guia in ("CBX-REP-001", "CBX-REP-002"):
            _crear_en_reparto(client, guia)
            client.post(f"/envios/{guia}/entregar", json={"receptor": "Laura", "evidencia_id": "F1"})
        res = client.get("/reportes/entregas-a-tiempo")
        assert res.status_code == 200
        data = res.json()
        assert data["total_entregados"] == 2
        assert data["porcentaje_a_tiempo"] == 100.0
        assert data["sla_horas"] == 72

    def test_reporte_entregas_sin_datos(self, client):
        data = client.get("/reportes/entregas-a-tiempo").json()
        assert data == {
            "total_entregados": 0, "entregados_a_tiempo": 0,
            "porcentaje_a_tiempo": 0.0, "sla_horas": 72,
        }

    def test_reporte_incidencias_por_tipo(self, client):
        _crear_en_reparto(client, "CBX-REP-010")
        client.post(
            "/envios/CBX-REP-010/incidencias",
            json={"tipo": "PAQUETE_DANADO", "descripcion": "Rotura", "evidencia_id": "F1"},
        )
        client.post("/envios/CBX-REP-010/intento-fallido", json={"motivo": "Ausente"})
        data = client.get("/reportes/incidencias").json()
        assert data["total_incidencias"] == 2
        assert data["por_tipo"] == {"PAQUETE_DANADO": 1, "DESTINATARIO_AUSENTE": 1}


class TestSaludYConfiguracion:
    def test_health_verifica_base_de_datos(self, client):
        data = client.get("/health").json()
        assert data["status"] == "UP"
        assert data["database"] == "connected"

    def test_url_postgres_se_normaliza(self):
        from src.infrastructure.database import _normalizar_url

        assert _normalizar_url("postgres://u:p@h/db") == "postgresql+psycopg2://u:p@h/db"
        assert _normalizar_url("postgresql://u:p@h/db") == "postgresql+psycopg2://u:p@h/db"
        assert _normalizar_url("postgresql+psycopg2://u:p@h/db").endswith("u:p@h/db")
        assert _normalizar_url("sqlite:///x.db") == "sqlite:///x.db"
