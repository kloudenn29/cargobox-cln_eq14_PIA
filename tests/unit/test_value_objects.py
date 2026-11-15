"""Pruebas unitarias para Value Objects del dominio de CargoBox."""

from decimal import Decimal

import pytest

from src.domain.exceptions import DomainException, SeguroInvalidoException
from src.domain.value_objects import Dimensiones, Dinero, Direccion, GuiaRastreo, Seguro


class TestDinero:
    def test_creacion_basica(self):
        d = Dinero(Decimal("100.50"))
        assert d.monto == Decimal("100.50")
        assert d.moneda == "MXN"

    def test_suma(self):
        a = Dinero(Decimal("100.00"))
        b = Dinero(Decimal("250.50"))
        c = a + b
        assert c.monto == Decimal("350.50")

    def test_resta(self):
        a = Dinero(Decimal("500.00"))
        b = Dinero(Decimal("150.00"))
        c = a - b
        assert c.monto == Decimal("350.00")

    def test_multiplicacion(self):
        a = Dinero(Decimal("100.00"))
        c = a * 3
        assert c.monto == Decimal("300.00")

    def test_comparaciones(self):
        a = Dinero(Decimal("100.00"))
        b = Dinero(Decimal("200.00"))
        assert a < b
        assert b > a
        assert a <= b
        assert b >= a

    def test_redondeo_dos_decimales(self):
        d = Dinero(Decimal("99.999"))
        assert d.monto == Decimal("100.00")

    def test_monedas_distintas_error(self):
        a = Dinero(Decimal("100.00"), "MXN")
        b = Dinero(Decimal("50.00"), "USD")
        with pytest.raises(DomainException):
            _ = a + b

    def test_str(self):
        d = Dinero(Decimal("1234.56"))
        assert "1,234.56" in str(d)


class TestDimensiones:
    def test_volumen(self):
        d = Dimensiones(largo_cm=30, ancho_cm=20, alto_cm=15)
        assert d.volumen_cm3 == Decimal("9000")

    def test_peso_volumetrico(self):
        d = Dimensiones(largo_cm=50, ancho_cm=40, alto_cm=30)
        # 50*40*30 = 60000 / 5000 = 12.00
        assert d.peso_volumetrico_kg == Decimal("12.00")

    def test_dimension_negativa_error(self):
        with pytest.raises(DomainException):
            Dimensiones(largo_cm=-1, ancho_cm=10, alto_cm=10)

    def test_dimension_cero_error(self):
        with pytest.raises(DomainException):
            Dimensiones(largo_cm=0, ancho_cm=10, alto_cm=10)


class TestDireccion:
    def test_creacion_valida(self):
        d = Direccion(
            calle="Av. Universidad", numero="1500",
            colonia="Centro", ciudad="Monterrey", codigo_postal="64000"
        )
        assert d.codigo_postal == "64000"
        assert "Monterrey" in d.resumen()

    def test_cp_invalido_4_digitos(self):
        with pytest.raises(DomainException):
            Direccion(calle="A", numero="1", colonia="B", ciudad="C", codigo_postal="1234")

    def test_calle_vacia(self):
        with pytest.raises(DomainException):
            Direccion(calle="", numero="1", colonia="B", ciudad="C", codigo_postal="64000")

    def test_ciudad_vacia(self):
        with pytest.raises(DomainException):
            Direccion(calle="A", numero="1", colonia="B", ciudad="", codigo_postal="64000")


class TestSeguro:
    def test_seguro_valido_con_valor(self):
        s = Seguro(amparado=True, valor_declarado=Decimal("5000.00"))
        assert s.amparado is True
        assert s.valor_declarado == Decimal("5000.00")

    def test_prima_seguro(self):
        s = Seguro(amparado=True, valor_declarado=Decimal("10000.00"))
        assert s.costo_prima_mxn == Decimal("150.00")  # 1.5%

    def test_seguro_sin_poliza(self):
        s = Seguro(amparado=False, valor_declarado=Decimal("0.00"))
        assert s.costo_prima_mxn == Decimal("0.00")

    def test_seguro_amparado_valor_cero_error(self):
        with pytest.raises(SeguroInvalidoException):
            Seguro(amparado=True, valor_declarado=Decimal("0.00"))

    def test_seguro_no_amparado_valor_negativo_error(self):
        with pytest.raises(SeguroInvalidoException):
            Seguro(amparado=False, valor_declarado=Decimal("-100.00"))


class TestGuiaRastreo:
    def test_guia_valida(self):
        g = GuiaRastreo("CBX-001")
        assert str(g) == "CBX-001"

    def test_guia_se_normaliza_mayusculas(self):
        g = GuiaRastreo("cbx-002-test")
        assert g.codigo == "CBX-002-TEST"

    def test_guia_corta_error(self):
        with pytest.raises(DomainException):
            GuiaRastreo("AB")

    def test_guia_vacia_error(self):
        with pytest.raises(DomainException):
            GuiaRastreo("")

