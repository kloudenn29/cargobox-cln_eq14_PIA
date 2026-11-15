"""Pruebas unitarias para el patrón Specification y sus composiciones AND/OR/NOT."""

from decimal import Decimal

from src.domain.entities import Actor, DetalleOperacion, Operacion
from src.domain.enums import EstadoOperacion
from src.domain.specifications import (
    BeneficioReferenciaSpecification,
    ClienteActivoSpecification,
    ClientePreferenteSpecification,
    DetalleNoVacioSpecification,
    OperacionAutorizadaSpecification,
    PromocionActivaSpecification,
    PuedeProcesarseSpecification,
)


def _make_operacion(
    actor_activo=True,
    actor_pref=False,
    autorizado=True,
    promo=False,
    detalles=None,
    precio=Decimal("543.00"),
    cantidad=3,
):
    actor = Actor(
        actor_id="TEST-A", nombre="Test", es_preferente=actor_pref,
        activo=actor_activo, ciudad="MTY",
    )
    if detalles is None:
        detalles = [
            DetalleOperacion(
                operacion_id="TEST-O", recurso_id="TEST-P",
                cantidad=cantidad, precio_unitario=precio,
            )
        ]
    return Operacion(
        operacion_id="TEST-O", actor_id="TEST-A",
        estado=EstadoOperacion.RECIBIDO,
        promocion_activa=promo, autorizado=autorizado,
        actor=actor, detalles=detalles,
    )


class TestClienteActivoSpec:
    def test_activo_cumple(self):
        op = _make_operacion(actor_activo=True)
        assert ClienteActivoSpecification().is_satisfied_by(op) is True

    def test_inactivo_no_cumple(self):
        op = _make_operacion(actor_activo=False)
        assert ClienteActivoSpecification().is_satisfied_by(op) is False


class TestDetalleNoVacioSpec:
    def test_con_detalles_cumple(self):
        op = _make_operacion()
        assert DetalleNoVacioSpecification().is_satisfied_by(op) is True

    def test_sin_detalles_no_cumple(self):
        op = _make_operacion(detalles=[])
        assert DetalleNoVacioSpecification().is_satisfied_by(op) is False


class TestOperacionAutorizadaSpec:
    def test_autorizada_cumple(self):
        op = _make_operacion(autorizado=True)
        assert OperacionAutorizadaSpecification().is_satisfied_by(op) is True

    def test_no_autorizada(self):
        op = _make_operacion(autorizado=False)
        assert OperacionAutorizadaSpecification().is_satisfied_by(op) is False


class TestPuedeProcesarseSpec:
    """Composición: activo AND detalle_no_vacio AND autorizado."""

    def test_todo_ok_cumple(self):
        op = _make_operacion(actor_activo=True, autorizado=True)
        spec = PuedeProcesarseSpecification()
        assert spec.is_satisfied_by(op) is True
        assert "CUMPLE" in spec.explain(op)

    def test_inactivo_no_cumple(self):
        op = _make_operacion(actor_activo=False, autorizado=True)
        assert PuedeProcesarseSpecification().is_satisfied_by(op) is False

    def test_sin_detalle_no_cumple(self):
        op = _make_operacion(actor_activo=True, autorizado=True, detalles=[])
        assert PuedeProcesarseSpecification().is_satisfied_by(op) is False

    def test_no_autorizado_no_cumple(self):
        op = _make_operacion(actor_activo=True, autorizado=False)
        assert PuedeProcesarseSpecification().is_satisfied_by(op) is False


class TestBeneficioReferenciaSpec:
    """Composición: VIP AND total >= 1500 AND NOT promocion_activa."""

    def test_vip_alto_sin_promo_cumple(self):
        op = _make_operacion(actor_pref=True, promo=False, precio=Decimal("600.00"), cantidad=3)
        # total = 600 * 3 = 1800 >= 1500
        spec = BeneficioReferenciaSpecification()
        assert spec.is_satisfied_by(op) is True

    def test_no_vip_no_cumple(self):
        op = _make_operacion(actor_pref=False, promo=False, precio=Decimal("600.00"), cantidad=3)
        assert BeneficioReferenciaSpecification().is_satisfied_by(op) is False

    def test_vip_monto_bajo_no_cumple(self):
        op = _make_operacion(actor_pref=True, promo=False, precio=Decimal("100.00"), cantidad=1)
        # total = 100 < 1500
        assert BeneficioReferenciaSpecification().is_satisfied_by(op) is False

    def test_vip_con_promo_no_cumple(self):
        op = _make_operacion(actor_pref=True, promo=True, precio=Decimal("600.00"), cantidad=3)
        assert BeneficioReferenciaSpecification().is_satisfied_by(op) is False

    def test_justo_1500_cumple(self):
        op = _make_operacion(actor_pref=True, promo=False, precio=Decimal("500.00"), cantidad=3)
        # total = 500 * 3 = 1500 exacto
        assert BeneficioReferenciaSpecification().is_satisfied_by(op) is True


class TestComposicionOrNot:
    """Verifica las composiciones OR y NOT directamente."""

    def test_or_una_verdadera(self):
        spec = ClienteActivoSpecification() | ClientePreferenteSpecification()
        op = _make_operacion(actor_activo=True, actor_pref=False)
        assert spec.is_satisfied_by(op) is True

    def test_or_ambas_falsas(self):
        spec = ClienteActivoSpecification() | ClientePreferenteSpecification()
        op = _make_operacion(actor_activo=False, actor_pref=False)
        assert spec.is_satisfied_by(op) is False

    def test_not_invierte(self):
        spec = ~PromocionActivaSpecification()
        op = _make_operacion(promo=False)
        assert spec.is_satisfied_by(op) is True  # NOT False = True

    def test_not_promo_activa(self):
        spec = ~PromocionActivaSpecification()
        op = _make_operacion(promo=True)
        assert spec.is_satisfied_by(op) is False  # NOT True = False

    def test_explain_or(self):
        spec = ClienteActivoSpecification() | ClientePreferenteSpecification()
        op = _make_operacion(actor_activo=True)
        exp = spec.explain(op)
        assert "CUMPLE" in exp

    def test_explain_not(self):
        spec = ~PromocionActivaSpecification()
        op = _make_operacion(promo=False)
        exp = spec.explain(op)
        assert "CUMPLE" in exp

