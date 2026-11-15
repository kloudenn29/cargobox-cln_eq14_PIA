"""Pruebas de integración: persistencia de historial e incidencias del Envio."""

from datetime import timezone

from src.domain.enums import EstadoEnvio, TipoIncidencia


class TestPersistenciaEnvio:
    def test_historial_se_guarda_y_recupera(self, envio_repo, envio_en_reparto):
        envio_repo.save(envio_en_reparto)
        envio_repo.commit()

        recuperado = envio_repo.get_by_guia(envio_en_reparto.guia.codigo)
        assert [m.estado for m in recuperado.historial] == [
            EstadoEnvio.CLASIFICADO,
            EstadoEnvio.EN_TRANSITO,
            EstadoEnvio.DISTRIBUCION_LOCAL,
            EstadoEnvio.EN_REPARTO,
        ]
        assert recuperado.fecha_creacion.tzinfo == timezone.utc

    def test_guardar_dos_veces_no_duplica_historial(self, envio_repo, envio_en_reparto):
        envio_repo.save(envio_en_reparto)
        envio_repo.commit()
        envio_repo.save(envio_en_reparto)
        envio_repo.commit()
        recuperado = envio_repo.get_by_guia(envio_en_reparto.guia.codigo)
        assert len(recuperado.historial) == 4

    def test_incidencias_se_guardan_y_se_agrupan_por_tipo(self, envio_repo, envio_en_reparto):
        envio_en_reparto.reportar_incidencia(TipoIncidencia.PAQUETE_DANADO, "Rotura", "FOTO_01")
        envio_en_reparto.registrar_intento_fallido("Ausente")
        envio_repo.save(envio_en_reparto)
        envio_repo.commit()

        recuperado = envio_repo.get_by_guia(envio_en_reparto.guia.codigo)
        assert len(recuperado.incidencias) == 2
        assert recuperado.incidencias[0].evidencia_id == "FOTO_01"
        assert envio_repo.contar_incidencias_por_tipo() == {
            "PAQUETE_DANADO": 1,
            "DESTINATARIO_AUSENTE": 1,
        }

    def test_existe_y_listar(self, envio_repo, envio_basico):
        assert envio_repo.existe(envio_basico.guia.codigo) is False
        envio_repo.save(envio_basico)
        envio_repo.commit()
        assert envio_repo.existe(envio_basico.guia.codigo) is True
        assert len(envio_repo.list_all()) == 1
