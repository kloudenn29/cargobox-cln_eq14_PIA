"""Pruebas unitarias del ciclo logístico del agregado Envio (US5, US6, US9, US11, US13, US14)."""

from datetime import datetime, timedelta, timezone

import pytest

from src.domain.entities import SLA_ENTREGA_HORAS
from src.domain.enums import EstadoEnvio, TipoIncidencia
from src.domain.events import (
    AlertaRastreoDetenido,
    EnvioClasificado,
    EnvioEnTransito,
    EnvioEntregado,
    EventDispatcher,
    IncidenciaRegistrada,
)
from src.domain.exceptions import DomainException, TransicionInvalidaException


class TestAvanceYHistorial:
    """El envío solo avanza paso a paso y cada cambio queda en el historial (US5)."""

    def test_ruta_completa_registra_historial(self, envio_en_reparto):
        estados = [m.estado for m in envio_en_reparto.historial]
        assert estados == [
            EstadoEnvio.CLASIFICADO,
            EstadoEnvio.EN_TRANSITO,
            EstadoEnvio.DISTRIBUCION_LOCAL,
            EstadoEnvio.EN_REPARTO,
        ]

    def test_no_permite_saltar_estados(self, envio_basico):
        with pytest.raises(TransicionInvalidaException):
            envio_basico.avanzar(EstadoEnvio.EN_TRANSITO)

    def test_no_permite_retroceder(self, envio_en_reparto):
        with pytest.raises(TransicionInvalidaException):
            envio_en_reparto.avanzar(EstadoEnvio.CLASIFICADO)

    def test_no_se_avanza_a_entregado_directamente(self, envio_en_reparto):
        with pytest.raises(TransicionInvalidaException):
            envio_en_reparto.avanzar(EstadoEnvio.ENTREGADO)

    def test_avanzar_actualiza_cedis_y_emite_eventos(self, envio_basico):
        envio_basico.avanzar(EstadoEnvio.CLASIFICADO, "CEDIS-TEST-MTY")
        envio_basico.avanzar(EstadoEnvio.EN_TRANSITO)
        assert envio_basico.cedis_actual == "CEDIS-TEST-MTY"
        nombres = [e.event_name for e in EventDispatcher.get_history()]
        assert EnvioClasificado.__name__ in nombres
        assert EnvioEnTransito.__name__ in nombres

    def test_cancelar_queda_en_historial(self, envio_basico):
        envio_basico.cancelar("Cliente desistió")
        assert envio_basico.historial[-1].estado == EstadoEnvio.CANCELADO


class TestEntrega:
    """Regla 5 (US13): entrega solo EN_REPARTO y con evidencia."""

    def test_entrega_exitosa(self, envio_en_reparto):
        envio_en_reparto.entregar("Laura Méndez", "FIRMA_DIGITAL_09")
        assert envio_en_reparto.estado == EstadoEnvio.ENTREGADO
        assert EnvioEntregado.__name__ in [e.event_name for e in EventDispatcher.get_history()]

    def test_entrega_fuera_de_reparto_rechazada(self, envio_basico):
        with pytest.raises(DomainException):
            envio_basico.entregar("Laura", "FIRMA_01")

    def test_entrega_sin_evidencia_rechazada(self, envio_en_reparto):
        with pytest.raises(DomainException):
            envio_en_reparto.entregar("Laura", "  ")


class TestIncidencias:
    """Reglas de US9 (dirección incorrecta) y US11 (daño con evidencia)."""

    def test_danio_requiere_evidencia(self, envio_en_reparto):
        with pytest.raises(DomainException):
            envio_en_reparto.reportar_incidencia(TipoIncidencia.PAQUETE_DANADO, "Caja rota")

    def test_danio_con_evidencia_se_asocia_a_la_guia(self, envio_en_reparto):
        inc = envio_en_reparto.reportar_incidencia(
            TipoIncidencia.PAQUETE_DANADO, "Rotura en maniobras", "FOTO_ROTURA_01"
        )
        assert inc.guia == envio_en_reparto.guia.codigo
        assert inc.evidencia_id == "FOTO_ROTURA_01"
        assert envio_en_reparto.estado == EstadoEnvio.EN_REPARTO
        assert IncidenciaRegistrada.__name__ in [e.event_name for e in EventDispatcher.get_history()]

    def test_direccion_incorrecta_regresa_a_distribucion_local(self, envio_en_reparto):
        envio_en_reparto.reportar_incidencia(TipoIncidencia.DIRECCION_INCORRECTA, "No existe el número")
        assert envio_en_reparto.estado == EstadoEnvio.DISTRIBUCION_LOCAL
        assert len(envio_en_reparto.incidencias) == 1

    def test_direccion_incorrecta_solo_en_reparto(self, envio_basico):
        with pytest.raises(TransicionInvalidaException):
            envio_basico.reportar_incidencia(TipoIncidencia.DIRECCION_INCORRECTA, "No existe")

    def test_incidencia_en_cancelado_rechazada(self, envio_basico):
        envio_basico.cancelar("Cancelado")
        with pytest.raises(DomainException):
            envio_basico.reportar_incidencia(TipoIncidencia.EXTRAVIO, "Perdido")

    def test_incidencia_sin_descripcion_rechazada(self, envio_en_reparto):
        with pytest.raises(DomainException):
            envio_en_reparto.reportar_incidencia(TipoIncidencia.RECHAZO, "   ")

    def test_intento_fallido_genera_incidencia_de_ausencia(self, envio_en_reparto):
        envio_en_reparto.registrar_intento_fallido("Nadie en casa")
        assert envio_en_reparto.incidencias[0].tipo == TipoIncidencia.DESTINATARIO_AUSENTE


class TestTiempos:
    """US6 (rastreo detenido >24 h) y US14 (entregas a tiempo)."""

    def test_envio_detenido_mas_de_24h(self, envio_basico):
        envio_basico.avanzar(EstadoEnvio.CLASIFICADO)
        envio_basico.avanzar(EstadoEnvio.EN_TRANSITO)
        envio_basico.historial[-1].fecha = datetime.now(timezone.utc) - timedelta(hours=30)
        assert envio_basico.esta_detenido() is True
        assert envio_basico.emitir_alerta_si_detenido() is True
        assert AlertaRastreoDetenido.__name__ in [e.event_name for e in EventDispatcher.get_history()]

    def test_envio_reciente_no_genera_alerta(self, envio_basico):
        envio_basico.avanzar(EstadoEnvio.CLASIFICADO)
        envio_basico.avanzar(EstadoEnvio.EN_TRANSITO)
        assert envio_basico.esta_detenido() is False
        assert envio_basico.emitir_alerta_si_detenido() is False

    def test_solo_en_transito_puede_estar_detenido(self, envio_basico):
        envio_basico.historial.clear()
        envio_basico.fecha_creacion = datetime.now(timezone.utc) - timedelta(hours=100)
        assert envio_basico.esta_detenido() is False  # sigue RECIBIDO

    def test_entrega_a_tiempo_y_tardia(self, envio_en_reparto):
        envio_en_reparto.entregar("Laura", "FIRMA_01")
        assert envio_en_reparto.entregado_a_tiempo() is True
        envio_en_reparto.fecha_creacion = datetime.now(timezone.utc) - timedelta(hours=SLA_ENTREGA_HORAS + 10)
        assert envio_en_reparto.entregado_a_tiempo() is False

    def test_no_entregado_no_cuenta_como_a_tiempo(self, envio_basico):
        assert envio_basico.entregado_a_tiempo() is False
