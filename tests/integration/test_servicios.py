"""Pruebas de los casos de uso con adaptadores simulados (Mocks): CEDIS (US8) y notificaciones (US6, US11)."""

from datetime import datetime, timedelta, timezone

import pytest

from src.application.dtos import DireccionDTO, EnvioCreateDTO
from src.application.services import EnvioAppService
from src.domain.enums import EstadoEnvio
from src.infrastructure.external_services import (
    MockCentroDistribucionService,
    MockNotificacionService,
)


def _dto(guia: str, cp_destino: str = "44100") -> EnvioCreateDTO:
    return EnvioCreateDTO(
        guia=guia,
        remitente_id="CAR-C001",
        destinatario_nombre="Laura Méndez",
        direccion_origen=DireccionDTO(
            calle="Av. Constitución", numero="450", colonia="Centro",
            ciudad="Monterrey", codigo_postal="64000",
        ),
        direccion_destino=DireccionDTO(
            calle="Av. Vallarta", numero="1200", colonia="Americana",
            ciudad="Guadalajara", codigo_postal=cp_destino,
        ),
        peso_kg=4.5,
    )


class TestMockCentroDistribucion:
    """US8: asignación de CEDIS por código postal."""

    def test_cp_exacto(self):
        assert MockCentroDistribucionService().sugerir_cedis("44100") == "CEDIS-OCCIDENTE-GUADALAJARA"

    def test_prefijo_regional(self):
        assert MockCentroDistribucionService().sugerir_cedis("66450") == "CEDIS-REGIONAL-NORESTE"
        assert MockCentroDistribucionService().sugerir_cedis("03100") == "CEDIS-METROPOLITANO-CENTRO"

    def test_cp_desconocido_usa_hub_nacional(self):
        assert MockCentroDistribucionService().sugerir_cedis("99999") == "CEDIS-HUB-NACIONAL-MTY"

    def test_falla_de_red_lanza_error(self):
        with pytest.raises(ConnectionError):
            MockCentroDistribucionService(simular_falla_red=True).sugerir_cedis("44100")


class TestServicioEnvios:
    def test_si_cae_el_servicio_cedis_el_registro_continua(self, envio_repo):
        svc = EnvioAppService(envio_repo, cedis_service=MockCentroDistribucionService(simular_falla_red=True))
        res = svc.registrar_envio(_dto("CBX-CEDIS-001"))
        assert res.estado == "RECIBIDO"
        assert res.cedis_actual == "CEDIS-REGIONAL-DEFAULT"

    def test_danio_notifica_a_calidad_y_seguros(self, envio_repo):
        notif = MockNotificacionService()
        svc = EnvioAppService(envio_repo, notificacion_service=notif)
        svc.registrar_envio(_dto("CBX-NOTIF-001"))
        for destino in ("CLASIFICADO", "EN_TRANSITO", "DISTRIBUCION_LOCAL", "EN_REPARTO"):
            svc.avanzar_envio("CBX-NOTIF-001", destino)
        svc.reportar_incidencia("CBX-NOTIF-001", "PAQUETE_DANADO", "Rotura", "FOTO_ROTURA_01")
        assert notif.notificaciones_enviadas[0]["destinatario"] == "CALIDAD_Y_SEGUROS"

    def test_alerta_detenido_notifica_a_atencion_a_clientes(self, envio_repo):
        notif = MockNotificacionService()
        svc = EnvioAppService(envio_repo, notificacion_service=notif)
        svc.registrar_envio(_dto("CBX-NOTIF-002"))
        svc.avanzar_envio("CBX-NOTIF-002", "CLASIFICADO")
        svc.avanzar_envio("CBX-NOTIF-002", "EN_TRANSITO")
        en_30_horas = datetime.now(timezone.utc) + timedelta(hours=30)
        alertas = svc.alertas_rastreo_detenido(ahora=en_30_horas)
        assert [a.guia for a in alertas] == ["CBX-NOTIF-002"]
        assert notif.notificaciones_enviadas[0]["destinatario"] == "ATENCION_CLIENTES"

    def test_estado_persistido_tras_avanzar(self, envio_repo):
        svc = EnvioAppService(envio_repo)
        svc.registrar_envio(_dto("CBX-PERSIST-001"))
        svc.avanzar_envio("CBX-PERSIST-001", "CLASIFICADO")
        assert svc.get_envio("CBX-PERSIST-001").estado == EstadoEnvio.CLASIFICADO
