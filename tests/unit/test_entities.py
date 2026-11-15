"""Pruebas unitarias para las Entidades y Agregados del dominio de CargoBox."""

from decimal import Decimal

import pytest

from src.domain.entities import Actor, DetalleOperacion, Operacion, Paquete
from src.domain.enums import EstadoEnvio, EstadoOperacion, RolUsuario
from src.domain.exceptions import (
    AutorizacionRequeridaException,
    CancelacionNoPermitidaException,
    DomainException,
    IntentoEntregaAgotadoException,
    ModificacionDireccionNoPermitidaException,
    TransicionInvalidaException,
)
from src.domain.value_objects import Direccion


class TestActor:
    def test_creacion(self, actor_activo):
        assert actor_activo.actor_id == "CAR-C001"
        assert actor_activo.activo is True

    def test_actor_id_vacio_error(self):
        with pytest.raises(DomainException):
            Actor(actor_id="", nombre="X")


class TestRecurso:
    def test_creacion(self, recurso_paquete):
        assert recurso_paquete.precio_mxn == Decimal("543.00")
        assert recurso_paquete.habilitado is True


class TestDetalleOperacion:
    def test_subtotal(self):
        d = DetalleOperacion(
            operacion_id="OP-1", recurso_id="P-1",
            cantidad=3, precio_unitario=Decimal("100.00"),
        )
        assert d.subtotal == Decimal("300.00")

    def test_cantidad_cero_error(self):
        with pytest.raises(DomainException):
            DetalleOperacion(operacion_id="OP-1", recurso_id="P-1", cantidad=0)


class TestOperacion:
    def test_calcular_total(self, actor_activo):
        d1 = DetalleOperacion(
            operacion_id="OP-T", recurso_id="P-1",
            cantidad=2, precio_unitario=Decimal("500.00"),
        )
        d2 = DetalleOperacion(
            operacion_id="OP-T", recurso_id="P-2",
            cantidad=1, precio_unitario=Decimal("250.00"),
        )
        op = Operacion(
            operacion_id="OP-T", actor_id="CAR-C001",
            actor=actor_activo, detalles=[d1, d2],
        )
        assert op.calcular_total() == Decimal("1250.00")

    def test_transicionar_aprobar(self):
        op = Operacion(operacion_id="OP-X", actor_id="A")
        nuevo = op.transicionar("aprobar")
        assert nuevo == EstadoOperacion.CLASIFICADO
        assert op.estado == EstadoOperacion.CLASIFICADO

    def test_transicionar_cancelar(self):
        op = Operacion(operacion_id="OP-X", actor_id="A")
        nuevo = op.transicionar("cancelar")
        assert nuevo == EstadoOperacion.CANCELADO


class TestPaquete:
    def test_peso_facturable(self, dimensiones_estandar):
        p = Paquete(peso_kg=Decimal("5.0"), dimensiones=dimensiones_estandar)
        assert p.peso_facturable_kg == max(Decimal("5.0"), dimensiones_estandar.peso_volumetrico_kg)

    def test_peso_cero_error(self, dimensiones_estandar):
        with pytest.raises(DomainException):
            Paquete(peso_kg=Decimal("0.0"), dimensiones=dimensiones_estandar)

    def test_peso_excedido_error(self, dimensiones_estandar):
        with pytest.raises(DomainException):
            Paquete(peso_kg=Decimal("71.0"), dimensiones=dimensiones_estandar)


class TestEnvioCancelacion:
    """Regla 1 (US2): Cancelación solo en RECIBIDO."""

    def test_cancelar_en_recibido_exito(self, envio_basico):
        envio_basico.cancelar("Solicitud del remitente")
        assert envio_basico.estado == EstadoEnvio.CANCELADO

    def test_cancelar_en_transito_error(self, envio_en_transito):
        with pytest.raises(CancelacionNoPermitidaException):
            envio_en_transito.cancelar("Quiero cancelar")

    def test_cancelar_sin_motivo_error(self, envio_basico):
        with pytest.raises(DomainException):
            envio_basico.cancelar("   ")


class TestEnvioIntentosEntrega:
    """Regla 2 (US10): Máximo 2 intentos de entrega."""

    def test_primer_intento_reprograma(self, envio_en_reparto):
        estado = envio_en_reparto.registrar_intento_fallido("Ausente")
        assert estado == EstadoEnvio.DISTRIBUCION_LOCAL
        assert envio_en_reparto.intentos_entrega == 1

    def test_segundo_intento_devolucion(self, envio_en_reparto):
        envio_en_reparto.registrar_intento_fallido("Ausente 1er vez")
        envio_en_reparto.avanzar(EstadoEnvio.EN_REPARTO)
        estado = envio_en_reparto.registrar_intento_fallido("Ausente 2da vez")
        assert estado == EstadoEnvio.DEVOLUCION_ORIGEN
        assert envio_en_reparto.intentos_entrega == 2

    def test_tercer_intento_rechazado(self, envio_en_reparto):
        envio_en_reparto.registrar_intento_fallido("1")
        envio_en_reparto.avanzar(EstadoEnvio.EN_REPARTO)
        envio_en_reparto.registrar_intento_fallido("2")
        with pytest.raises(IntentoEntregaAgotadoException):
            envio_en_reparto.registrar_intento_fallido("3")

    def test_intento_fallido_fuera_de_reparto_rechazado(self, envio_basico):
        with pytest.raises(TransicionInvalidaException):
            envio_basico.registrar_intento_fallido("Ausente")


class TestEnvioDireccion:
    """Regla 3 (US7): Cambio de dirección antes de CEDIS destino."""

    def test_cambio_en_transito_exito(self, envio_en_transito, dir_destino):
        nueva = Direccion(
            calle="Nueva Calle", numero="99",
            colonia="Nueva Col", ciudad="Querétaro", codigo_postal="76000",
        )
        envio_en_transito.actualizar_direccion(nueva, RolUsuario.ATENCION_CLIENTES)
        assert envio_en_transito.direccion_destino.ciudad == "Querétaro"

    def test_cambio_en_distribucion_local_error(self, envio_en_distribucion_local):
        nueva = Direccion(
            calle="Otra", numero="1",
            colonia="X", ciudad="Y", codigo_postal="76000",
        )
        with pytest.raises(ModificacionDireccionNoPermitidaException):
            envio_en_distribucion_local.actualizar_direccion(nueva, RolUsuario.ATENCION_CLIENTES)

    def test_repartidor_no_puede_cambiar(self, envio_en_transito):
        nueva = Direccion(
            calle="Otra", numero="1",
            colonia="X", ciudad="Y", codigo_postal="76000",
        )
        with pytest.raises(AutorizacionRequeridaException):
            envio_en_transito.actualizar_direccion(nueva, RolUsuario.REPARTIDOR)


class TestEnvioIndemnizacion:
    """Regla 4 (US4/US12): Indemnización con seguro vs sin seguro."""

    def test_con_seguro_cubre_valor_declarado(self, envio_asegurado):
        resultado = envio_asegurado.dictaminar_indemnizacion(
            Decimal("3000.00"), RolUsuario.ANALISTA_CALIDAD
        )
        assert resultado.monto == Decimal("3000.00")

    def test_con_seguro_tope_valor_declarado(self, envio_asegurado):
        resultado = envio_asegurado.dictaminar_indemnizacion(
            Decimal("10000.00"), RolUsuario.ANALISTA_CALIDAD
        )
        assert resultado.monto == Decimal("5000.00")

    def test_sin_seguro_tope_flete(self, envio_basico):
        resultado = envio_basico.dictaminar_indemnizacion(
            Decimal("3000.00"), RolUsuario.ANALISTA_CALIDAD
        )
        assert resultado.monto == Decimal("350.00")

    def test_rol_no_autorizado_error(self, envio_basico):
        with pytest.raises(AutorizacionRequeridaException):
            envio_basico.dictaminar_indemnizacion(
                Decimal("100.00"), RolUsuario.REPARTIDOR
            )

    def test_monto_cero_error(self, envio_basico):
        with pytest.raises(DomainException):
            envio_basico.dictaminar_indemnizacion(
                Decimal("0.00"), RolUsuario.ANALISTA_CALIDAD
            )


class TestEnvioEntrega:
    """Regla 5 (US13): Entrega con evidencia."""

    def test_entregar_en_reparto_exito(self, envio_basico):
        envio_basico.estado = EstadoEnvio.EN_REPARTO
        envio_basico.entregar("Juan Pérez", "FOTO-001")
        assert envio_basico.estado == EstadoEnvio.ENTREGADO

    def test_entregar_sin_evidencia_error(self, envio_basico):
        envio_basico.estado = EstadoEnvio.EN_REPARTO
        with pytest.raises(DomainException):
            envio_basico.entregar("Juan", "")

    def test_entregar_no_en_reparto_error(self, envio_basico):
        with pytest.raises(DomainException):
            envio_basico.entregar("Juan", "FOTO-001")

