"""Pruebas de integración para la API REST de CargoBox usando TestClient."""

from src.infrastructure.models import ActorModel, RecursoModel


class TestHealthEndpoint:
    def test_healthcheck(self, client):
        res = client.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "UP"
        assert data["service"] == "CargoBox API"


class TestOperacionesAPI:
    def test_crear_y_consultar_operacion(self, client, test_db):
        actor = ActorModel(
            actor_id="ACT-API-01",
            nombre="Cliente API",
            es_preferente=True,
            activo=True,
            ciudad="Monterrey",
        )
        rec = RecursoModel(
            recurso_id="REC-API-01",
            descripcion="Caja Mediana",
            precio_mxn=600.00,
            capacidad_o_stock=20,
            habilitado=True,
        )
        test_db.add(actor)
        test_db.add(rec)
        test_db.commit()

        payload = {
            "operacion_id": "OP-API-100",
            "actor_id": "ACT-API-01",
            "promocion_activa": False,
            "autorizado": True,
            "referencia": "REF-TEST-API",
            "detalles": [
                {"recurso_id": "REC-API-01", "cantidad": 3, "precio_unitario": 600.00}
            ],
        }
        res_post = client.post("/operaciones/", json=payload)
        assert res_post.status_code == 201
        data = res_post.json()
        assert data["operacion_id"] == "OP-API-100"
        assert float(data["total_mxn"]) == 1800.00

        # Consultar
        res_get = client.get("/operaciones/OP-API-100")
        assert res_get.status_code == 200
        assert res_get.json()["actor_id"] == "ACT-API-01"

    def test_evaluar_precondiciones_y_beneficio(self, client, test_db):
        actor = ActorModel(
            actor_id="ACT-VIP-02",
            nombre="VIP",
            es_preferente=True,
            activo=True,
            ciudad="Monterrey",
        )
        rec = RecursoModel(
            recurso_id="REC-VIP-02",
            descripcion="Paquete VIP",
            precio_mxn=1000.00,
            capacidad_o_stock=10,
            habilitado=True,
        )
        test_db.add(actor)
        test_db.add(rec)
        test_db.commit()

        client.post(
            "/operaciones/",
            json={
                "operacion_id": "OP-VIP-200",
                "actor_id": "ACT-VIP-02",
                "promocion_activa": False,
                "autorizado": True,
                "detalles": [{"recurso_id": "REC-VIP-02", "cantidad": 2}],
            },
        )

        res_val = client.get("/operaciones/OP-VIP-200/validar")
        assert res_val.status_code == 200
        assert res_val.json()["cumple"] is True

        res_ben = client.get("/operaciones/OP-VIP-200/beneficio")
        assert res_ben.status_code == 200
        assert res_ben.json()["cumple"] is True

    def test_transicion_estado_valida_e_invalida(self, client, test_db):
        actor = ActorModel(
            actor_id="ACT-TR-01",
            nombre="Cliente TR",
            es_preferente=False,
            activo=True,
            ciudad="Monterrey",
        )
        test_db.add(actor)
        test_db.commit()

        client.post(
            "/operaciones/",
            json={
                "operacion_id": "OP-TR-300",
                "actor_id": "ACT-TR-01",
                "detalles": [],
            },
        )

        # Transición válida: RECIBIDO -> CLASIFICADO (aprobar)
        res_ap = client.post("/operaciones/OP-TR-300/transicion", json={"accion": "aprobar"})
        assert res_ap.status_code == 200
        assert res_ap.json()["estado_nuevo"] == "CLASIFICADO"

        # Transición inválida: saltar_estado
        res_inv = client.post(
            "/operaciones/OP-TR-300/transicion", json={"accion": "saltar_estado"}
        )
        assert res_inv.status_code == 409


class TestEnviosAPI:
    def test_ciclo_completo_envio_api(self, client, test_db):
        payload = {
            "guia": "CBX-API-888",
            "remitente_id": "CAR-C001",
            "destinatario_nombre": "Carlos Gómez",
            "direccion_origen": {
                "calle": "Av. Constitución",
                "numero": "450",
                "colonia": "Centro",
                "ciudad": "Monterrey",
                "codigo_postal": "64000",
            },
            "direccion_destino": {
                "calle": "Av. Vallarta",
                "numero": "1200",
                "colonia": "Americana",
                "ciudad": "Guadalajara",
                "codigo_postal": "44100",
            },
            "peso_kg": 4.5,
            "seguro_amparado": True,
            "valor_declarado": 3500.00,
            "flete_monto": 420.00,
        }
        res = client.post("/envios/", json=payload)
        assert res.status_code == 201
        data = res.json()
        assert data["guia"] == "CBX-API-888"
        assert data["estado"] == "RECIBIDO"
        assert data["cedis_actual"] == "CEDIS-OCCIDENTE-GUADALAJARA"

        # Consultar
        res_get = client.get("/envios/CBX-API-888")
        assert res_get.status_code == 200
        assert res_get.json()["destinatario_nombre"] == "Carlos Gómez"

        # El envío avanza por la ruta logística hasta salir a reparto
        for destino in ("CLASIFICADO", "EN_TRANSITO", "DISTRIBUCION_LOCAL", "EN_REPARTO"):
            res_av = client.post("/envios/CBX-API-888/avanzar", json={"destino": destino})
            assert res_av.status_code == 200
            assert res_av.json()["estado"] == destino

        # Intentos de entrega
        res_int1 = client.post(
            "/envios/CBX-API-888/intento-fallido", json={"motivo": "Ausente"}
        )
        assert res_int1.status_code == 200
        assert res_int1.json()["intentos_entrega"] == 1
        assert res_int1.json()["estado"] == "DISTRIBUCION_LOCAL"

        client.post("/envios/CBX-API-888/avanzar", json={"destino": "EN_REPARTO"})
        res_int2 = client.post(
            "/envios/CBX-API-888/intento-fallido", json={"motivo": "Ausente"}
        )
        assert res_int2.status_code == 200
        assert res_int2.json()["intentos_entrega"] == 2
        assert res_int2.json()["estado"] == "DEVOLUCION_ORIGEN"

        # Indemnización
        res_ind = client.post(
            "/envios/CBX-API-888/indemnizacion",
            json={
                "monto_reclamado": 2000.00,
                "rol_dictaminador": "ANALISTA_CALIDAD",
            },
        )
        assert res_ind.status_code == 200
        assert float(res_ind.json()["monto_autorizado"]) == 2000.00
